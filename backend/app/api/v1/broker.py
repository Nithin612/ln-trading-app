"""Broker endpoints — Phase 7.

Endpoints:
  GET  /broker/kite/login            → returns Zerodha OAuth login URL
  GET  /broker/kite/callback         → receives request_token, stores access_token
  GET  /broker/kite/status           → current token validity for the caller
  POST /broker/kite/instruments/sync → download instruments CSV and upsert to DB
  POST /broker/kite/consumer/start   → manually (re)start the tick consumer (admin)
  POST /broker/kite/consumer/stop    → stop the tick consumer (admin)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.kite_client import exchange_token, get_active_token, get_login_url, sync_instruments
from app.broker.tick_consumer import get_consumer, start_consumer, stop_consumer
from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_admin
from app.models.user import User

# Frontend origin to redirect to after Zerodha OAuth
# CORS_ORIGINS is a list; use the first entry as the frontend base URL
_FRONTEND_ORIGIN = settings.cors_origins[0] if settings.cors_origins else "http://localhost:5173"

router = APIRouter(prefix="/broker", tags=["broker"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class LoginUrlResponse(BaseModel):
    login_url: str


class TokenStatusResponse(BaseModel):
    connected: bool
    expires_at: datetime | None
    consumer_running: bool


class InstrumentSyncResponse(BaseModel):
    synced: int


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/kite/login", response_model=LoginUrlResponse)
async def kite_login(current_user: User = Depends(get_current_user)) -> LoginUrlResponse:
    """Return the Zerodha login URL.  Frontend opens this in a popup or redirect."""
    return LoginUrlResponse(login_url=get_login_url())


@router.get("/kite/callback")
async def kite_callback(
    request_token: str = Query(..., description="Token from Zerodha OAuth redirect"),
    action: str = Query(default=""),
    type_: str = Query(default="", alias="type"),
    status_: str = Query(default="", alias="status"),
) -> RedirectResponse:
    """Public endpoint — Zerodha redirects here after login.

    This endpoint cannot require auth because the browser hits it with no JWT header.
    It simply redirects the browser to the frontend's /broker/kite page, passing
    the request_token as a query param.  The frontend (which already has the JWT in
    memory) then calls /broker/kite/exchange to do the actual token exchange.
    """
    frontend_url = (
        f"{_FRONTEND_ORIGIN}/broker/kite"
        f"?request_token={request_token}"
        f"&action={action}"
        f"&status={status_}"
    )
    return RedirectResponse(url=frontend_url, status_code=302)


@router.get("/kite/exchange")
async def kite_exchange(
    request_token: str = Query(..., description="request_token obtained from Zerodha callback"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Exchange request_token for access_token.  Called by the frontend after callback redirect."""
    try:
        token = await exchange_token(db, current_user.id, request_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kite token exchange failed: {exc}",
        ) from exc
    return {"detail": "Connected to Zerodha Kite", "expires_at": token.expires_at.isoformat()}


@router.get("/kite/status", response_model=TokenStatusResponse)
async def kite_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenStatusResponse:
    """Return connection status and whether the tick consumer is running."""
    token = await get_active_token(db, current_user.id)
    consumer = get_consumer()
    return TokenStatusResponse(
        connected=token is not None,
        expires_at=token.expires_at if token else None,
        consumer_running=consumer is not None,
    )


@router.post(
    "/kite/instruments/sync",
    response_model=InstrumentSyncResponse,
    dependencies=[Depends(require_admin)],
)
async def kite_instruments_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InstrumentSyncResponse:
    """Download Kite instruments CSV and upsert into kite_instruments. Admin only."""
    token = await get_active_token(db, current_user.id)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Kite token. Please authenticate first via /broker/kite/login.",
        )
    synced = await sync_instruments(db, token.access_token)
    return InstrumentSyncResponse(synced=synced)


@router.post(
    "/kite/consumer/start",
    dependencies=[Depends(require_admin)],
)
async def consumer_start(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Manually start (or restart) the tick consumer. Admin only."""
    started = await start_consumer(current_user.id)
    if not started:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not start consumer — authenticate with Kite first and sync instruments.",
        )
    return {"detail": "Tick consumer started"}


@router.post(
    "/kite/consumer/stop",
    dependencies=[Depends(require_admin)],
)
async def consumer_stop() -> dict[str, str]:
    """Stop the tick consumer. Admin only."""
    await stop_consumer()
    return {"detail": "Tick consumer stopped"}
