"""Position monitor Celery task — Phase 8.

Runs every minute during market hours (9:15–15:30 IST, weekdays).
For each open paper position:
  1. Gets the current LIVE tick price (Redis LTP — no stale fallback).
  2. Checks if SL or TP has been hit → closes the position automatically.
  3. Advances trail-SL state if applicable.
  4. Refreshes unrealized_pnl on still-open positions.

Price discipline (fixes the 2026-07-28 pre-open auto-close bug): the monitor
acts ONLY inside the regular session and ONLY on a live LTP. It never falls
back to the previous daily close — pre-open the `ltp:` keys have expired, and
evaluating SL/TP against yesterday's close closed positions on stale prices,
corrupting the paper record that gates live trading.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.position_monitor.monitor_positions", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def monitor_positions(self: object) -> dict[str, int]:  # noqa: ARG001
    """Scan all open paper positions and auto-close on SL/TP hit."""
    return run_db_task(_run_monitor)


async def _run_monitor() -> dict[str, int]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        return await scan_positions(db, now=datetime.now(tz=UTC))


async def scan_positions(  # noqa: C901 — linear SL/TP/trail branches per position
    db: object, *, now: datetime | None = None
) -> dict[str, int]:
    """Evaluate every open paper position against the live price.

    Split out from the task body so it can be driven by the test session and
    an injected clock. Returns counts of closed / updated / skipped positions.
    A position is *skipped* when no live LTP is available — the monitor never
    acts on a stale price.
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.broker.paper_broker import close_position, get_live_ltp, update_position_pnl
    from app.models.trading import Position
    from app.models.user import User
    from app.services.journal_service import auto_create_journal_entry
    from app.trading.atr import atr_timeframe_for, latest_atr
    from app.trading.market_hours import is_market_session
    from app.trading.profit_lock import absolute_ladder_stop, ladder_params_from_settings
    from app.trading.trail_sl import (
        advance_trail,
        compute_pnl,
        is_sl_hit,
        is_tp_hit,
        stop_fill_price,
    )

    assert isinstance(db, AsyncSession)  # narrow the DI'd session type for mypy
    now = now or datetime.now(tz=UTC)

    # Off-market: do nothing. This is the primary guard against the pre-open
    # (08:30 IST) beat auto-closing positions on the previous session's close.
    if not is_market_session(now):
        log.debug("Position monitor: outside market session (%s) — skipping", now.isoformat())
        return {"closed": 0, "updated": 0, "skipped": 0}

    closed = 0
    updated = 0
    skipped = 0

    result = await db.execute(
        select(Position).where(
            Position.mode == "paper",
            Position.closed_at.is_(None),
        )
    )
    positions = result.scalars().all()

    # Which stop governor runs is a per-user setting; resolve it once per user
    # per scan (a handful of users at most).
    profit_lock_by_user: dict[int, bool] = {}

    for pos in positions:
        # Live tick only — never the daily-close fallback. No fresh price
        # (illiquid, between ticks, holiday) → leave the position untouched.
        price = await get_live_ltp(pos.stock_id)
        if price is None:
            skipped += 1
            continue

        # Track max favourable excursion (GROSS peak profit) for leakage
        # analysis and the profit-lock shadow comparator.
        better = (
            pos.peak_price is None
            or (pos.side == "LONG" and price > pos.peak_price)
            or (pos.side == "SHORT" and price < pos.peak_price)
        )
        if better:
            pos.peak_price = price
            pos.peak_pnl = compute_pnl(
                side=pos.side,
                entry=pos.avg_entry_price,
                exit_price=price,
                quantity=pos.quantity,
            )

        # SL/TP hit → auto-close (reason encodes the trigger for Trade History).
        # A stop guarantees an exit, not a price: fill at the WORSE of the stop
        # and the live price, so a gap through the stop is booked at the market
        # it actually gapped to — never flattered back to the stop price. TP
        # keeps filling at the target (a favourable gap filled there is already
        # conservative).
        if pos.current_sl is not None and is_sl_hit(
            side=pos.side, current_price=price, current_sl=pos.current_sl
        ):
            sl_fill = stop_fill_price(
                side=pos.side, stop=pos.current_sl, market_price=price
            )
            close_order, closed_pos = await close_position(
                db, pos, exit_price=sl_fill, reason="sl_hit"
            )
            journal = await auto_create_journal_entry(db, closed_pos)
            if journal and close_order.filled_price:
                journal.exit_price = close_order.filled_price
            closed += 1
            continue

        if pos.current_tp is not None and is_tp_hit(
            side=pos.side, current_price=price, current_tp=pos.current_tp
        ):
            close_order, closed_pos = await close_position(
                db, pos, exit_price=pos.current_tp, reason="tp_hit"
            )
            journal = await auto_create_journal_entry(db, closed_pos)
            if journal and close_order.filled_price:
                journal.exit_price = close_order.filled_price
            closed += 1
            continue

        # Advance the stop for the NEXT beat (the SL/TP hit check above ran
        # against the pre-advance stop — no intra-beat look-ahead). Which
        # governor runs depends on the owning user's setting:
        #   profit_lock_enabled → Layered Ratchet Stop (app/trading/profit_lock)
        #   otherwise            → the fixed trail_sl ladder (unchanged).
        if pos.current_sl is not None and pos.signal_id is not None:
            from app.models.signal import Signal

            sig = await db.get(Signal, pos.signal_id)
            if sig is not None:
                if pos.user_id not in profit_lock_by_user:
                    owner = await db.get(User, pos.user_id)
                    profit_lock_by_user[pos.user_id] = bool(
                        owner is not None and owner.profit_lock_enabled
                    )

                entry = Decimal(str(pos.avg_entry_price))
                original_sl = Decimal(str(sig.stop_loss))
                current_stop = Decimal(str(pos.current_sl))

                if profit_lock_by_user[pos.user_id]:
                    # Rupee profit ladder: breakeven once peak profit ≥ ₹X, then
                    # seal (peak_profit − giveback), with an ATR-room floor so a
                    # volatile trend isn't noise-stopped. peak_price was refreshed
                    # from this beat above; ATR is entry-time volatility (matches
                    # the shadow model). Sized-to-budget entries (paper_broker
                    # size_for_fill) make the ₹ thresholds mean the same R per trade.
                    peak = pos.peak_price if pos.peak_price is not None else price
                    atr = await latest_atr(
                        db,
                        pos.stock_id,
                        timeframe=atr_timeframe_for(sig.classification),
                        before=pos.opened_at,
                    )
                    new_sl = absolute_ladder_stop(
                        side=pos.side,
                        entry=entry,
                        original_sl=original_sl,
                        peak_price=Decimal(str(peak)),
                        quantity=pos.quantity,
                        atr=atr,
                        params=ladder_params_from_settings(),
                        current_stop=current_stop,
                    )
                    # trail_state stays a ladder-only concept; the lock moves
                    # only the stop price (one-way, never against the position).
                    if new_sl != current_stop:
                        pos.current_sl = new_sl
                else:
                    trail = advance_trail(
                        side=pos.side,
                        entry=entry,
                        original_sl=original_sl,
                        current_sl=current_stop,
                        current_price=price,
                        current_state=pos.trail_state,
                    )
                    if trail.advanced:
                        pos.current_sl = trail.new_sl
                        pos.trail_state = trail.new_state

        await update_position_pnl(db, pos, price=price)
        updated += 1

    await db.commit()

    log.info("Position monitor: closed=%d, updated=%d, skipped=%d", closed, updated, skipped)
    return {"closed": closed, "updated": updated, "skipped": skipped}
