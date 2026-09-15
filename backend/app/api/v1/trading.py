"""Paper trading endpoints — Phase 8.

POST /trading/orders               — place a paper order from a signal
GET  /trading/positions            — open positions
POST /trading/positions/{id}/close — manually close a position
POST /trading/positions/{id}/update-sl — update stop loss
GET  /trading/history              — closed positions (trade history)
GET  /trading/daily-pnl            — today's P&L + circuit breaker status
GET  /trading/shadow-compare       — profit-lock shadow comparator (read-only)
"""

import logging
import uuid as _uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker import adapter, event_store
from app.broker.depth import get_live_depths
from app.broker.paper_broker import (
    PRICE_LIVE,
    PRICE_NONE,
    PaperOrderError,
    close_position,
    get_live_ltps,
    place_paper_order,
    stored_price_with_source,
    update_position_pnl,
)
from app.broker.tick_consumer import held_without_instrument
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Order, Position
from app.models.user import User
from app.schemas.trading import (
    ClosePositionRequest,
    DailyPnlOut,
    HealthReasonOut,
    OrderOut,
    PaperDayRow,
    PaperRecordOut,
    PlaceOrderRequest,
    PositionHealthOut,
    PositionListResponse,
    PositionOut,
    PriceSource,
    ShadowCompareResponse,
    ShadowComparisonOut,
    TradeHistoryResponse,
    UpdateSlRequest,
)
from app.services.journal_service import auto_create_journal_entry
from app.services.liquidity import load_median_traded_values_safe
from app.services.profit_lock_shadow import compare_position
from app.trading import risk_engine
from app.trading.circuit_breaker import (
    check_circuit_breaker,
    get_daily_realized_pnl,
    get_trades_taken_today,
)
from app.trading.position_health import PositionHealth, assess_position_health
from app.trading.regime import er_by_stock

router = APIRouter(prefix="/trading", tags=["trading"])

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")


def _enrich_order(order: Order, symbol: str) -> OrderOut:
    out = OrderOut.model_validate(order)
    out.symbol = symbol
    return out


def _health_out(h: PositionHealth) -> PositionHealthOut:
    return PositionHealthOut(
        verdict=h.verdict.value,
        reasons=[
            HealthReasonOut(code=r.code, severity=r.severity.value, detail=r.detail)
            for r in h.reasons
        ],
        drawdown_r=h.drawdown_r,
        rr_remaining=h.rr_remaining,
        regime_er=h.regime_er,
    )


def _enrich_position(
    position: Position,
    symbol: str,
    current_price: Decimal | None = None,
    health: PositionHealth | None = None,
    price_state: PriceSource = PRICE_NONE,
    stranded: bool = False,
    hold_only: bool = False,
) -> PositionOut:
    out = PositionOut.model_validate(position)
    out.symbol = symbol
    out.current_price = current_price
    # V2 — a mark without its provenance is the defect: `current_price` never goes null
    # while any stored close exists, so a dead feed rendered a day-old number as though
    # it were live. Default `none`, so a caller that forgets to pass it understates
    # freshness rather than overstating it.
    out.price_state = price_state if current_price is not None else PRICE_NONE
    out.stranded = stranded
    out.hold_only = hold_only
    out.health = _health_out(health) if health is not None else None
    return out


async def _get_symbol(db: AsyncSession, stock_id: int) -> str:
    stock = await db.get(Stock, stock_id)
    return stock.symbol if stock else ""


async def _validity_by_signal(
    db: AsyncSession, signal_ids: list[str]
) -> dict[str, datetime]:
    """Validity-until per signal for the given ids (one query). Positions held
    past their signal's validity are flagged stale by the health watcher."""
    ids = [s for s in signal_ids if s]
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(Signal.id, Signal.validity_until).where(Signal.id.in_(ids))
        )
    ).all()
    return {r.id: r.validity_until for r in rows}




@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    req: PlaceOrderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrderOut:
    """Place a paper BUY order from a signal.

    Every pre-trade rule now runs in ONE place — `app/trading/risk_engine.py` (Phase
    7.1). This endpoint's job is transport: load the signal, ask the engine, translate
    its verdict into a status code. It no longer knows the rules or their order, which
    is what stops the next caller from re-deriving a slightly different sequence.

    ⭐ **The intent is recorded BEFORE the gates run** (Phase 7.3). Until this, a refused
    order was not a row at all — it raised, and `orders` therefore recorded only
    successes, so *"what did the risk layer refuse last Tuesday, and under which
    thresholds?"* could not be answered from data. Writing `submitted` first makes that
    structural rather than diligent: a decision cannot fail to be recorded, because the
    row exists before the decision is made.
    """
    signal = await db.get(Signal, req.signal_id)
    client_order_id = adapter.namespaced_id(adapter.GATEWAY_PAPER, str(_uuid.uuid4()))
    await event_store.append(
        db,
        client_order_id=client_order_id,
        kind=adapter.EventKind.SUBMITTED,
        user_id=user.id,
        stock_id=signal.stock_id if signal is not None else None,
        signal_id=req.signal_id,
        payload={"side": req.side, "quantity": req.quantity},
    )

    verdict = await risk_engine.check_pre_trade(
        db, user, signal,
        side=req.side,
        allow_offmarket=bool(user.allow_offmarket_entry),
    )
    if verdict.unassessed:
        # Reachable without any registry change: flip `entry_sl_atr_gate_mode` active and
        # a stock with too little history for an ATR lands here. Otherwise it means a
        # restriction was added without a loader. Either way the behaviour is correct
        # (fail-open, as before) — this is a diagnostic, not a rejection.
        log.warning(
            "order path could not assess ACTIVE gate(s) %s for signal_id=%s "
            "(no ATR history, or a restriction has no context loader)",
            ", ".join(verdict.unassessed), req.signal_id,
        )
    if verdict.denied:
        await event_store.append(
            db,
            client_order_id=client_order_id,
            kind=adapter.EventKind.DENIED,
            user_id=user.id,
            stock_id=signal.stock_id if signal is not None else None,
            signal_id=req.signal_id,
            payload={
                "rule": verdict.rule,
                "reason": verdict.reason,
                # The thresholds in force AT THE TIME. Without these the record answers
                # "what was refused" but not "under what settings", and the second half
                # is what makes an old refusal re-interpretable — the same gap that makes
                # the sl_atr shadow evidence non-point-in-time today.
                **({"stamps": verdict.stamps} if verdict.stamps else {}),
            },
        )
        # ⚠ COMMIT BEFORE RAISING. `get_db` rolls the session back when the handler
        # raises, so without this the denial row is written, discarded, and the entire
        # point of recording refusals is lost — silently, and only in the failure case
        # nobody tests. Pinned by `test_denial_survives_the_exception`.
        await db.commit()
        # Only "the signal does not exist" is a 404; every other refusal is a conflict
        # with the account's current state. This mapping reproduces the pre-7.1 codes
        # exactly, including the ordering quirk that a tripped breaker answers 409 even
        # when the signal id is unknown.
        code = (
            status.HTTP_404_NOT_FOUND
            if verdict.rule == risk_engine.RULE_SIGNAL_MISSING
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=verdict.reason)
    assert signal is not None  # noqa: S101 — narrowed by RULE_SIGNAL_MISSING above

    try:
        order, _pos = await place_paper_order(
            db, user, signal, side=req.side, quantity=req.quantity
        )
    except (PaperOrderError, ValueError) as exc:
        # REJECTED, not DENIED — the broker's own unconditional pre-fill refusals
        # (through-stop, off-market, zero size, notional cap) are the paper analogue of
        # an exchange saying no. Keeping the two kinds apart is what lets a rising rate
        # be attributed to our thresholds or to the market, rather than to "failures".
        await event_store.append(
            db,
            client_order_id=client_order_id,
            kind=adapter.EventKind.REJECTED,
            user_id=user.id,
            stock_id=signal.stock_id,
            signal_id=req.signal_id,
            payload={"reason": str(exc), "error_class": adapter.ErrorClass.TERMINAL.value},
        )
        await db.commit()  # same reason as the denial branch — the raise would roll back
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    # Stamp the restriction verdicts on the order for the shadow reports (shadow +
    # active only; off leaves no footprint). New dict, not in-place, so SQLAlchemy flags
    # the JSONB column dirty.
    if verdict.stamps:
        order.broker_payload = {**(order.broker_payload or {}), **verdict.stamps}

    # Paper fills synchronously, but the stream still records both states a real broker
    # would produce — so a projection built from these events has the same shape whatever
    # gateway produced them, which is what makes 7.4's restart recovery gateway-agnostic.
    broker_order_id = adapter.namespaced_id(adapter.GATEWAY_PAPER, str(order.id))
    await event_store.append(
        db, client_order_id=client_order_id, kind=adapter.EventKind.ACCEPTED,
        user_id=user.id, stock_id=order.stock_id, signal_id=req.signal_id,
        payload={"broker_order_id": broker_order_id},
    )
    await event_store.append(
        db, client_order_id=client_order_id, kind=adapter.EventKind.FILLED,
        user_id=user.id, stock_id=order.stock_id, signal_id=req.signal_id,
        payload={
            "broker_order_id": broker_order_id,
            # CUMULATIVE, never a delta — idempotent under the replay 7.4 rebuilds from.
            "filled_qty": order.filled_qty,
            "filled_price": (
                str(order.filled_price) if order.filled_price is not None else None
            ),
        },
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

    # Refresh unrealized P&L; keep the price each refresh used so the UI can
    # show the current market price alongside entry. Depth is fetched ONCE for the whole
    # book (A21 marks to bid/ask): `get_live_depth` opens its own connection per call, so
    # a per-position read would open ~29 of them per request.
    books = await get_live_depths([p.stock_id for p in positions])
    advs = await load_median_traded_values_safe(
        db, [p.stock_id for p in positions], lookback=settings.paper_participation_lookback
    )
    # V2 — LTPs batched in ONE MGET. The depth read above was batched for exactly this
    # reason and the LTP was missed: `update_position_pnl` falls through to
    # `get_live_ltp`, which opens its own connection PER CALL (its own docstring says
    # so), so this loop was one Redis connection per position.
    ltps = await get_live_ltps([p.stock_id for p in positions])
    stranded_ids = {sid for sid, _sym in await held_without_instrument(db)}
    # V3 — one query for the page: which held names has the universe rule stopped
    # admitting? A held name can leave overnight (D2′b), and the position page is where
    # the user finds out. `False` for a stock row that has vanished entirely — that is
    # `stranded`'s job to report, and claiming hold-only as well would double-badge it.
    hold_only_ids = {
        int(r.id)
        for r in (
            await db.execute(
                select(Stock.id).where(
                    Stock.id.in_({p.stock_id for p in positions}),
                    Stock.is_active.is_(False),
                )
            )
        ).all()
    }

    prices: dict[str, Decimal | None] = {}
    price_states: dict[str, PriceSource] = {}
    for pos in positions:
        # Resolve the mark AND its provenance. Passing the price in keeps
        # `update_position_pnl` from re-deriving it (and re-opening a connection).
        live = ltps.get(pos.stock_id)
        price: Decimal | None
        if live is not None:
            price, state = live, PRICE_LIVE
        else:
            price, state = await stored_price_with_source(db, pos.stock_id)
        price_states[pos.id] = state
        prices[pos.id] = await update_position_pnl(
            db,
            pos,
            price=price,
            depth=books.get(pos.stock_id),
            adv_value=advs.get(pos.stock_id),
        )
    await db.commit()

    # Emergency-exit watcher: regime ER (one batch) + signal validity feed the
    # advisory health assessment per open position.
    now = datetime.now(UTC)
    er_map = await er_by_stock(db, list({p.stock_id for p in positions}), now)
    validity = await _validity_by_signal(db, [p.signal_id for p in positions if p.signal_id])

    enriched = []
    for p in positions:
        health = assess_position_health(
            side=p.side,
            entry=p.avg_entry_price,
            current_price=prices.get(p.id),
            stop_loss=p.current_sl,
            take_profit=p.current_tp,
            regime_er=er_map.get(p.stock_id),
            validity_until=validity.get(p.signal_id) if p.signal_id else None,
            now=now,
        )
        enriched.append(
            _enrich_position(
                p,
                await _get_symbol(db, p.stock_id),
                prices.get(p.id),
                health,
                price_state=price_states.get(p.id, PRICE_NONE),
                stranded=p.stock_id in stranded_ids,
                hold_only=p.stock_id in hold_only_ids,
            )
        )
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


@router.get("/shadow-compare", response_model=ShadowCompareResponse)
async def shadow_compare(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=100),
) -> ShadowCompareResponse:
    """Replay candidate exit policies (current ladder vs Layered Ratchet Stop)
    over recent closed positions' 1m tapes. Read-only evidence — controls no
    real orders. See app/services/profit_lock_shadow.py."""
    result = await db.execute(
        select(Position)
        .where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_not(None),
        )
        .order_by(Position.closed_at.desc())
        .limit(limit)
    )
    positions = result.scalars().all()

    now = datetime.now(tz=UTC)
    comparisons = [
        ShadowComparisonOut.model_validate(await compare_position(db, pos, now=now))
        for pos in positions
    ]
    return ShadowCompareResponse(total=len(comparisons), comparisons=comparisons)


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

    # Open positions — refresh each P&L (same as the positions list) and sum,
    # so the card's total unrealised matches the table exactly.
    open_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.mode == "paper",
            Position.closed_at.is_(None),
        )
    )
    open_positions = open_result.scalars().all()
    open_count = len(open_positions)
    total_unrealized = Decimal("0")
    books = await get_live_depths([p.stock_id for p in open_positions])
    advs = await load_median_traded_values_safe(
        db, [p.stock_id for p in open_positions],
        lookback=settings.paper_participation_lookback,
    )
    for pos in open_positions:
        await update_position_pnl(
            db, pos, depth=books.get(pos.stock_id), adv_value=advs.get(pos.stock_id)
        )
        if pos.unrealized_pnl is not None:
            total_unrealized += pos.unrealized_pnl

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
        total_unrealized_pnl=total_unrealized,
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
    conditions = [
        Position.user_id == user.id,
        Position.mode == "paper",
        Position.closed_at.is_not(None),
    ]
    # Clock reset: once the honest-fill clock is (re)started, count only trades
    # closed on/after that instant — the days before were a different fill model.
    if user.paper_clock_started_at is not None:
        conditions.append(Position.closed_at >= user.paper_clock_started_at)
    result = await db.execute(select(Position).where(*conditions))
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
        clock_started_at=user.paper_clock_started_at,
    )


@router.post("/paper-clock/reset", response_model=PaperRecordOut)
async def reset_paper_clock(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PaperRecordOut:
    """Restart the 30-day profitable-paper clock from now.

    Sets the user's paper-clock start to the current instant, so the record
    (and the eventual Phase-7 go-live gate) counts only closed paper trades
    from here — used after a material fill-model change so the whole 30-day
    record is measured under one honest fill model. Past trades stay in the DB
    for history; they simply no longer count toward the clock.
    """
    user.paper_clock_started_at = datetime.now(tz=UTC)
    await db.commit()
    return await paper_record(db, user, target_days=30)
