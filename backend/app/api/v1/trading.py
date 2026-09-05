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
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.circuit_bands import get_circuit_band
from app.broker.paper_broker import (
    PaperOrderError,
    close_position,
    get_live_ltp,
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
    HealthReasonOut,
    OrderOut,
    PaperDayRow,
    PaperRecordOut,
    PlaceOrderRequest,
    PositionHealthOut,
    PositionListResponse,
    PositionOut,
    ShadowCompareResponse,
    ShadowComparisonOut,
    TradeHistoryResponse,
    UpdateSlRequest,
)
from app.services.benchmark import load_market_regime_context, load_rs_context
from app.services.journal_service import auto_create_journal_entry
from app.services.liquidity import load_traded_values
from app.services.profit_lock_shadow import compare_position
from app.signals import restrictions
from app.trading.atr import atr_timeframe_for, latest_atr
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
) -> PositionOut:
    out = PositionOut.model_validate(position)
    out.symbol = symbol
    out.current_price = current_price
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


async def _load_restriction_context(  # noqa: C901 — a flat sequence of INDEPENDENT
    # optional loads, one per context key, each gated on "is any gate that needs this on".
    # The branching is the point: it is what keeps `off` a true no-op (no query, no stamp).
    # Splitting it into per-key helpers would scatter the savepoint/fail-open discipline
    # that has to be identical across all of them.
    db: AsyncSession,
    signal: Signal,
    side: str,
    cfg: restrictions.RestrictionConfig,
    *,
    allow_offmarket: bool,
) -> restrictions.RestrictionContext:
    """Resolve, point-in-time, exactly the context the non-off restrictions need.

    A38: the RULES live in `app/signals/restrictions.py` and are shared with the display
    path; this function does only the I/O the order path can afford. It used to also
    contain the rules, in a second hand-maintained sequence that had to be kept in step
    with the preview by a contract test and a comment — see that module for why that
    arrangement is the thing being removed.

    Two properties preserved exactly:

    * **`off` is a TRUE no-op.** A key is loaded only when a restriction that needs it is
      not off, so an off gate costs no query and leaves no stamp.
    * **Every load fails open, inside its own SAVEPOINT.** A DB fault must never suppress
      a trade, and a nested block that rolls back leaves the session usable for
      `place_paper_order` below (cf. `get_circuit_band`'s except→None).

    ⚠ **One property deliberately NOT preserved: context is resolved EAGERLY.** The old
    inline chain interleaved load-and-judge and raised on the first block, so gates after
    the blocker did no I/O. Here every non-off gate's context is fetched before any
    judging, so an order rejected by the 3rd gate still pays for the 5th–8th (today, with
    diversity active and the rest shadow: +3 queries and +1 Redis read on a blocked
    click). That is the price of a PURE composer — `check` takes a resolved context so it
    can be shared with the display path and tested without a database — and it is charged
    per Buy click, not per listed row. Said plainly here rather than left as a docstring
    claiming an economy the code no longer has (quant-verifier MEDIUM).

    `as_of` is the signal's `created_at`, so every context is the one knowable AT COMMIT —
    the anchoring that keeps these overlays free of look-ahead.
    """
    as_of = signal.created_at
    available: set[str] = set()
    atr: Decimal | None = None
    band = None
    rs_ctx = None
    mkt_ctx = None
    traded: list[Decimal] | None = None
    ltp: Decimal | None = None

    def on(*gates: str) -> bool:
        return any(cfg.mode(g) != "off" for g in gates)

    if on(restrictions.GATE_DIVERSITY, restrictions.GATE_SL_ATR):
        atr = await latest_atr(
            db,
            signal.stock_id,
            timeframe=atr_timeframe_for(signal.classification),
            before=as_of,
        )
        # Recorded as available only when a real ATR came back: a None ATR leaves the
        # sl_atr half genuinely unjudged, which `unassessed` must surface.
        if atr is not None:
            available.add(restrictions.CTX_ATR)

    if on(restrictions.GATE_CIRCUIT):
        band = await get_circuit_band(signal.stock_id)
        available.add(restrictions.CTX_CIRCUIT_BAND)

    if on(restrictions.GATE_SECTOR_RS):
        try:
            async with db.begin_nested():
                rs_ctx = await load_rs_context(
                    db, signal.stock_id, lookback=cfg.sector_rs_lookback, as_of=as_of
                )
        except SQLAlchemyError:
            log.exception(
                "sector-RS context load failed; failing open for stock_id=%s", signal.stock_id
            )
            rs_ctx = None
        available.add(restrictions.CTX_RS)

    if on(restrictions.GATE_MARKET_REGIME):
        try:
            async with db.begin_nested():
                mkt_ctx = await load_market_regime_context(
                    db,
                    market_symbol=cfg.market_regime_market_symbol,
                    dma_period=cfg.market_regime_dma_period,
                    as_of=as_of,
                )
        except SQLAlchemyError:
            log.exception(
                "market-regime context load failed; failing open for stock_id=%s",
                signal.stock_id,
            )
            mkt_ctx = None
        available.add(restrictions.CTX_MARKET)

    if on(restrictions.GATE_LIQUIDITY):
        try:
            async with db.begin_nested():
                traded = await load_traded_values(
                    db, signal.stock_id, lookback=cfg.liquidity_lookback, as_of=as_of
                )
        except SQLAlchemyError:
            log.exception(
                "liquidity context load failed; failing open for stock_id=%s", signal.stock_id
            )
            traded = []
        available.add(restrictions.CTX_TRADED_VALUES)

    if on(restrictions.GATE_CHASE):
        # get_live_ltp does its own Redis read + fail-to-None, so no savepoint is needed.
        ltp = await get_live_ltp(signal.stock_id)
        if ltp is not None:
            available.add(restrictions.CTX_MARKET_PRICE)

    return restrictions.RestrictionContext(
        signal=signal,
        side=side,
        as_of=as_of,
        allow_offmarket=allow_offmarket,
        available=frozenset(available),
        atr=atr,
        market_price=ltp,
        circuit_band=band,
        rs=rs_ctx,
        market=mkt_ctx,
        traded_values=traded,
    )


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

    # Eligibility restrictions (A38): ONE registry, shared with the display path, walked
    # in one canonical order. `OVERLAY` only — the paper broker enforces its own
    # unconditional pre-fill rejections (off-market, through-stop) downstream, and running
    # them here as well would double-reject. Each gate is a no-op unless its mode is on;
    # judgements come back for stamping on the order.
    cfg = restrictions.config_from_settings()
    ctx = await _load_restriction_context(
        db, signal, req.side, cfg, allow_offmarket=bool(user.allow_offmarket_entry)
    )
    outcome = restrictions.check(ctx, cfg, enforced_by=restrictions.EnforcedBy.OVERLAY)
    if outcome.unassessed:
        # Reachable without any registry change: flip `entry_sl_atr_gate_mode` active and
        # a stock with too little history for an ATR lands here. Otherwise it means a
        # restriction was added without a loader. Either way the behaviour is correct
        # (fail-open, as before) — this is a diagnostic, not a rejection.
        log.warning(
            "order path could not assess ACTIVE gate(s) %s for signal_id=%s "
            "(no ATR history, or a restriction has no context loader)",
            ", ".join(outcome.unassessed), signal.id,
        )
    if outcome.blocked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=outcome.reason)

    try:
        order, _pos = await place_paper_order(
            db, user, signal, side=req.side, quantity=req.quantity
        )
    except (PaperOrderError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    # Stamp the restriction verdicts on the order for the shadow reports (shadow +
    # active only; off leaves no footprint). New dict, not in-place, so SQLAlchemy flags
    # the JSONB column dirty.
    stamps = outcome.stamps()
    if stamps:
        order.broker_payload = {**(order.broker_payload or {}), **stamps}
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
            _enrich_position(p, await _get_symbol(db, p.stock_id), prices.get(p.id), health)
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
    for pos in open_positions:
        await update_position_pnl(db, pos)
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
