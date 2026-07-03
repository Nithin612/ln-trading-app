"""Paper trading endpoints — Phase 8.

POST /trading/orders               — place a paper order from a signal
GET  /trading/positions            — open positions
POST /trading/positions/{id}/close — manually close a position
POST /trading/positions/{id}/update-sl — update stop loss
GET  /trading/history              — closed positions (trade history)
GET  /trading/daily-pnl            — today's P&L + circuit breaker status
"""

from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.paper_broker import close_position, place_paper_order, update_position_pnl
from app.core.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Order, Position
from app.models.user import User
from app.schemas.trading import (
    ClosePositionRequest,
    DailyPnlOut,
    OrderOut,
    PlaceOrderRequest,
    PositionListResponse,
    PositionOut,
    TradeHistoryResponse,
    UpdateSlRequest,
)
from app.services.journal_service import auto_create_journal_entry
from app.trading.circuit_breaker import (
    check_circuit_breaker,
    get_daily_realized_pnl,
    get_trades_taken_today,
)

router = APIRouter(prefix="/trading", tags=["trading"])

_IST = ZoneInfo("Asia/Kolkata")


def _enrich_order(order: Order, symbol: str) -> OrderOut:
    out = OrderOut.model_validate(order)
    out.symbol = symbol
    return out


def _enrich_position(position: Position, symbol: str) -> PositionOut:
    out = PositionOut.model_validate(position)
    out.symbol = symbol
    return out


async def _get_symbol(db: AsyncSession, stock_id: int) -> str:
    stock = await db.get(Stock, stock_id)
    return stock.symbol if stock else ""


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    req: PlaceOrderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderOut:
    """Place a paper BUY order from a signal.

    Circuit breaker is enforced: returns 409 if daily loss limit or max trades exceeded.
    """
    triggered, reason = await check_circuit_breaker(db, user)
    if triggered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)

    signal = await db.get(Signal, req.signal_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    if signal.status not in ("active",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Signal is {signal.status}, not active",
        )

    order, _pos = await place_paper_order(
        db, user, signal, side=req.side, quantity=req.quantity
    )
    await db.commit()
    await db.refresh(order)

    symbol = await _get_symbol(db, order.stock_id)
    return _enrich_order(order, symbol)


@router.get("/positions", response_model=PositionListResponse)
async def list_open_positions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PositionListResponse:
    """List all open paper positions for the current user."""
    result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_(None),
        ).order_by(Position.opened_at.desc())
    )
    positions = result.scalars().all()

    # Refresh unrealized P&L
    for pos in positions:
        await update_position_pnl(db, pos)
    await db.commit()

    enriched = [_enrich_position(p, await _get_symbol(db, p.stock_id)) for p in positions]
    return PositionListResponse(total=len(enriched), positions=enriched)


@router.post("/positions/{position_id}/close", response_model=PositionOut)
async def manual_close_position(
    position_id: str,
    req: ClosePositionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PositionOut:
    """Manually close an open paper position."""
    pos = await db.get(Position, position_id)
    if not pos or pos.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    if pos.closed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Position already closed"
        )

    _close_order, updated_pos = await close_position(
        db, pos, exit_price=req.exit_price, reason="manual"
    )
    journal_entry = await auto_create_journal_entry(db, updated_pos)
    if journal_entry and _close_order.filled_price:
        journal_entry.exit_price = _close_order.filled_price
    await db.commit()
    await db.refresh(updated_pos)

    symbol = await _get_symbol(db, updated_pos.stock_id)
    return _enrich_position(updated_pos, symbol)


@router.post("/positions/{position_id}/update-sl", response_model=PositionOut)
async def update_stop_loss(
    position_id: str,
    req: UpdateSlRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PositionOut:
    """Manually update the stop-loss on an open position."""
    pos = await db.get(Position, position_id)
    if not pos or pos.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    if pos.closed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Position already closed"
        )

    # Validate: for LONG, new SL must be below entry; for SHORT, above entry
    if pos.side == "LONG" and req.new_sl >= pos.avg_entry_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="For LONG positions, stop-loss must be below entry price",
        )
    if pos.side == "SHORT" and req.new_sl <= pos.avg_entry_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="For SHORT positions, stop-loss must be above entry price",
        )

    pos.current_sl = req.new_sl
    await db.commit()
    await db.refresh(pos)

    symbol = await _get_symbol(db, pos.stock_id)
    return _enrich_position(pos, symbol)


@router.get("/history", response_model=TradeHistoryResponse)
async def trade_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TradeHistoryResponse:
    """Return closed paper positions (trade history) for the current user."""
    count_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_not(None),
        )
    )
    all_closed = count_result.scalars().all()
    total = len(all_closed)

    result = await db.execute(
        select(Position)
        .where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_not(None),
        )
        .order_by(Position.closed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    positions = result.scalars().all()

    enriched = [_enrich_position(p, await _get_symbol(db, p.stock_id)) for p in positions]
    return TradeHistoryResponse(total=total, positions=enriched)


@router.get("/daily-pnl", response_model=DailyPnlOut)
async def daily_pnl(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DailyPnlOut:
    """Today's realized P&L and circuit breaker status (IST calendar day)."""
    from datetime import datetime

    from sqlalchemy import func

    ist_today = datetime.now(tz=_IST).date().isoformat()

    realized = await get_daily_realized_pnl(db, user.id)
    trades_today = await get_trades_taken_today(db, user.id)
    triggered, _reason = await check_circuit_breaker(db, user)

    # Count open positions
    open_result = await db.execute(
        select(func.count(Position.id)).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_(None),
        )
    )
    open_count = int(open_result.scalar() or 0)

    # Count positions closed today
    from app.trading.circuit_breaker import _ist_date_window

    start, end = _ist_date_window()
    closed_result = await db.execute(
        select(func.count(Position.id)).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at >= start,
            Position.closed_at <= end,
            Position.closed_at.is_not(None),
        )
    )
    closed_count = int(closed_result.scalar() or 0)

    limit_inr = user.capital_inr * user.daily_loss_limit_pct / Decimal("100")

    return DailyPnlOut(
        trade_date=ist_today,
        realized_pnl=realized,
        open_count=open_count,
        closed_count=closed_count,
        circuit_breaker_triggered=triggered,
        daily_loss_limit_inr=limit_inr,
        trades_taken_today=trades_today,
        max_trades_per_day=user.max_trades_per_day,
    )
