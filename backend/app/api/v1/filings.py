"""Corporate filings endpoints — Phase 6.

GET /filings/recent           — latest N filings across all stocks
GET /filings/by-stock/{id}    — filings for one stock
GET /filings/guard/{id}       — event-guard status for one stock
POST /filings/ingest           — (admin) trigger an immediate ingest
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.filing import CorporateFiling
from app.models.stock import Stock
from app.models.user import User
from app.schemas.filing import EventGuardStatus, FilingListResponse, FilingOut
from app.signals.event_guard import is_signal_suppressed

router = APIRouter(prefix="/filings", tags=["filings"])


async def _enrich(filing: CorporateFiling, db: AsyncSession) -> FilingOut:
    stock = await db.get(Stock, filing.stock_id)
    out = FilingOut.model_validate(filing)
    out.symbol = stock.symbol if stock else ""
    return out


@router.get("/recent", response_model=FilingListResponse)
async def list_recent_filings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    hours: int = Query(default=24, ge=1, le=168, description="Look-back window in hours"),
    filing_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> FilingListResponse:
    cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
    q = select(CorporateFiling).where(CorporateFiling.filing_time >= cutoff)
    if filing_type:
        q = q.where(CorporateFiling.filing_type == filing_type)
    q = q.order_by(CorporateFiling.filing_time.desc())

    total_result = await db.execute(q.with_only_columns(CorporateFiling.id))
    total = len(total_result.scalars().all())

    result = await db.execute(q.offset(offset).limit(limit))
    filings = result.scalars().all()
    enriched = [await _enrich(f, db) for f in filings]
    return FilingListResponse(total=total, filings=enriched)


@router.get("/by-stock/{stock_id}", response_model=FilingListResponse)
async def list_filings_for_stock(
    stock_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> FilingListResponse:
    stock = await db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    q = (
        select(CorporateFiling)
        .where(
            CorporateFiling.stock_id == stock_id,
            CorporateFiling.filing_time >= cutoff,
        )
        .order_by(CorporateFiling.filing_time.desc())
    )

    total_result = await db.execute(q.with_only_columns(CorporateFiling.id))
    total = len(total_result.scalars().all())

    result = await db.execute(q.offset(offset).limit(limit))
    filings = result.scalars().all()
    enriched = [await _enrich(f, db) for f in filings]
    return FilingListResponse(total=total, filings=enriched)


@router.get("/guard/{stock_id}", response_model=EventGuardStatus)
async def event_guard_status(
    stock_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> EventGuardStatus:
    stock = await db.get(Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    guard = await is_signal_suppressed(db, stock_id)
    return EventGuardStatus(
        stock_id=stock_id,
        symbol=stock.symbol,
        suppressed=guard.suppressed,
        reason=guard.reason,
        suppressed_until=guard.suppressed_until,
    )


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> dict[str, int]:
    """Admin-only: immediately poll NSE + BSE for new filings."""
    from app.ingestion.filings_consumer import ingest_filings
    inserted = await ingest_filings(db)
    return {"inserted": inserted}
