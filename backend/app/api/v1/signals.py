"""Signal endpoints — Phase 5/6 (offline signal engine + event guard).

GET  /signals/active          — list active signals, sortable by confidence
GET  /signals/{id}            — full detail including factor breakdown
POST /signals/generate        — (admin) trigger generation for a stock
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user as get_current_active_user
from app.core.deps import get_db, require_admin
from app.models.signal import Signal, SignalOutcome
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import SignalListResponse, SignalOut, SignalOutcomeOut
from app.signals.event_guard import is_signal_suppressed

router = APIRouter(prefix="/signals", tags=["signals"])


class GenerateRequest(BaseModel):
    stock_id: int
    timeframe: str = "1d"
    capital: Decimal = Decimal("500000")
    # risk_pct is a WHOLE percent (2.0 = 2%) — compute_quantity divides by
    # 100 itself. The old 0.02 default undersized every manual signal 100×;
    # the floor rejects fractional-style values loudly instead of sizing
    # them silently wrong.
    risk_pct: Decimal = Field(
        default=Decimal("2.0"), ge=Decimal("0.1"), le=Decimal("10")
    )


async def _enrich(signal: Signal, db: AsyncSession) -> SignalOut:
    """Attach stock symbol to a signal."""
    stock = await db.get(Stock, signal.stock_id)
    out = SignalOut.model_validate(signal)
    out.symbol = stock.symbol if stock else ""
    return out


@router.get("/active", response_model=SignalListResponse)
async def list_active_signals(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
    direction: str | None = Query(default=None, description="BUY | SELL"),
    classification: str | None = Query(default=None),
    min_confidence: int = Query(default=70, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SignalListResponse:
    now = datetime.now(tz=UTC)
    q = (
        select(Signal)
        .where(Signal.status == "active", Signal.validity_until > now)
        .where(Signal.confidence_pct >= min_confidence)
    )
    if direction:
        q = q.where(Signal.direction == direction.upper())
    if classification:
        q = q.where(Signal.classification == classification.lower())

    q = q.order_by(Signal.confidence_pct.desc(), Signal.created_at.desc())

    count_q = q.with_only_columns(Signal.id)
    total_result = await db.execute(count_q)
    total = len(total_result.scalars().all())

    result = await db.execute(q.offset(offset).limit(limit))
    signals = result.scalars().all()
    enriched = [await _enrich(s, db) for s in signals]
    return SignalListResponse(total=total, signals=enriched)


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(
    signal_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> SignalOut:
    signal = await db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    return await _enrich(signal, db)


@router.get("/{signal_id}/outcome", response_model=SignalOutcomeOut)
async def get_signal_outcome(
    signal_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> SignalOutcomeOut:
    """Tick-level outcome record (slice 3.6): first entry/SL/TP touches
    inside validity + the status ladder. 404 while no alert has touched
    the signal AND it hasn't expired (the row is written lazily)."""
    outcome = await db.get(SignalOutcome, signal_id)
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outcome recorded yet for this signal",
        )
    return SignalOutcomeOut.model_validate(outcome)


@router.post("/generate", response_model=SignalOut, status_code=status.HTTP_201_CREATED)
async def generate_signal(
    req: GenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SignalOut:
    """Admin-only: run the signal engine for one stock, respecting the event guard."""
    stock = await db.get(Stock, req.stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    guard = await is_signal_suppressed(db, req.stock_id)
    if guard.suppressed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Signal suppressed by event guard: {guard.reason}",
        )

    from zoneinfo import ZoneInfo

    from app.services.fii_dii_service import (
        get_market_flow_5d,
        get_stock_block_deal_net_cr,
    )
    from app.services.signal_service import generate_signal_for_stock

    as_of = datetime.now(tz=UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
    fii_net_5d, dii_net_5d = await get_market_flow_5d(db, as_of)
    block_net_cr = await get_stock_block_deal_net_cr(db, req.stock_id, as_of)

    signal = await generate_signal_for_stock(
        db=db,
        stock=stock,
        capital=req.capital,
        risk_pct=req.risk_pct,
        timeframe=req.timeframe,
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net_cr,
    )
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confidence below threshold or insufficient data",
        )

    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return await _enrich(signal, db)
