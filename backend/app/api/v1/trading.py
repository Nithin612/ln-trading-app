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

from app.broker.paper_broker import (
    PaperOrderError,
    close_position,
    place_paper_order,
    update_position_pnl,
)
from app.core.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Order, Position
from app.models.user import User
from app.schemas.trading import (
    ClosePositionRequest,
    DailyPnlOut,
    OrderOut,
    PaperDayRow,
    PaperRecordOut,
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


def _enrich_position(
    position: Position, symbol: str, current_price: Decimal | None = None
) -> PositionOut:
    out = PositionOut.model_validate(position)
    out.symbol = symbol
    out.current_price = current_price
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

    try:
        order, _pos = await place_paper_order(
            db, user, signal, side=req.side, quantity=req.quantity
        )
    except (PaperOrderError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
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

    # Refresh unrealized P&L; keep the price each refresh used so the UI can
    # show the current market price alongside entry.
    prices: dict[str, Decimal | None] = {}
    for pos in positions:
        prices[pos.id] = await update_position_pnl(db, pos)
    await db.commit()

    enriched = [
        _enrich_position(p, await _get_symbol(db, p.stock_id), prices.get(p.id))
        for p in positions
    ]
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


@router.get("/paper-record", response_model=PaperRecordOut)
async def paper_record(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    target_days: int = Query(default=30, ge=1, le=365),
) -> PaperRecordOut:
    """Per-IST-day realized-P&L history for the paper account.

    Groups every closed paper position by its IST close date and reports the
    profitable-day count and current streak — the visible surface of the
    30-day profitable-paper gate. P&L is net of trading costs; a *profitable
    day* is a day with ≥1 closed trade and net realized P&L > 0. The
    authoritative promotion gate remains Phase 7.
    """
    result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_not(None),
        )
    )
    closed = result.scalars().all()

    # Aggregate by IST calendar date (small volumes → Python grouping is fine).
    per_day: dict[str, dict[str, Decimal | int]] = {}
    for pos in closed:
        assert pos.closed_at is not None  # WHERE guarantees it
        day = pos.closed_at.astimezone(_IST).date().isoformat()
        agg = per_day.setdefault(day, {"pnl": Decimal("0"), "charges": Decimal("0"), "trades": 0})
        agg["pnl"] = agg["pnl"] + pos.realized_pnl
        agg["charges"] = agg["charges"] + (pos.charges or Decimal("0"))
        agg["trades"] = int(agg["trades"]) + 1

    days: list[PaperDayRow] = []
    cumulative = Decimal("0")
    profitable_days = losing_days = total_trades = 0
    total_charges = Decimal("0")
    best_streak = run = 0
    for day in sorted(per_day):
        agg = per_day[day]
        pnl = Decimal(str(agg["pnl"]))
        charges = Decimal(str(agg["charges"]))
        trades = int(agg["trades"])
        cumulative += pnl
        total_charges += charges
        total_trades += trades
        is_profit = pnl > 0
        if is_profit:
            profitable_days += 1
            run += 1
            best_streak = max(best_streak, run)
        else:
            if pnl < 0:
                losing_days += 1
            run = 0
        days.append(
            PaperDayRow(
                date=day,
                realized_pnl=pnl,
                charges=charges,
                trades=trades,
                profitable=is_profit,
                cumulative_pnl=cumulative,
            )
        )

    # Current streak = trailing run of profitable days (from the newest day).
    current_streak = 0
    for row in reversed(days):
        if row.profitable:
            current_streak += 1
        else:
            break

    total_traded = len(days)
    win_rate = (
        (Decimal(profitable_days) / Decimal(total_traded) * Decimal("100")).quantize(Decimal("0.1"))
        if total_traded
        else Decimal("0.0")
    )
    return PaperRecordOut(
        days=days,
        total_days_traded=total_traded,
        profitable_days=profitable_days,
        losing_days=losing_days,
        current_streak=current_streak,
        best_streak=best_streak,
        total_realized_pnl=cumulative,
        total_charges=total_charges,
        total_trades=total_trades,
        win_rate_pct=win_rate,
        target_days=target_days,
        start_date=days[0].date if days else None,
        last_date=days[-1].date if days else None,
    )
