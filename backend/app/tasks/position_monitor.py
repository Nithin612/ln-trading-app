"""Position monitor Celery task — Phase 8.

Runs every minute during market hours (9:15–15:30 IST, weekdays).
For each open paper position:
  1. Gets the current price (Redis LTP → daily-close fallback).
  2. Checks if SL or TP has been hit → closes the position automatically.
  3. Advances trail-SL state if applicable.
  4. Refreshes unrealized_pnl on still-open positions.
"""

from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.position_monitor.monitor_positions", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def monitor_positions(self: object) -> dict[str, int]:  # noqa: ARG001
    """Scan all open paper positions and auto-close on SL/TP hit."""
    return asyncio.get_event_loop().run_until_complete(_run_monitor())


async def _run_monitor() -> dict[str, int]:
    from sqlalchemy import select

    from app.broker.paper_broker import close_position, get_current_price, update_position_pnl
    from app.db.session import AsyncSessionFactory
    from app.models.trading import Position
    from app.trading.trail_sl import advance_trail, is_sl_hit, is_tp_hit

    closed = 0
    updated = 0

    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(Position).where(
                Position.mode == "paper",
                Position.closed_at.is_(None),
            )
        )
        positions = result.scalars().all()

        from app.services.journal_service import auto_create_journal_entry

        for pos in positions:
            price = await get_current_price(db, pos.stock_id)
            if price is None:
                continue

            # Check SL/TP hit
            if pos.current_sl is not None and is_sl_hit(
                side=pos.side, current_price=price, current_sl=pos.current_sl
            ):
                close_order, closed_pos = await close_position(
                    db, pos, exit_price=pos.current_sl, reason="sl_hit"
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

            # Advance trail SL if signal had one (original SL known from signal)
            if pos.current_sl is not None and pos.signal_id is not None:
                from app.models.signal import Signal

                sig = await db.get(Signal, pos.signal_id)
                if sig is not None:
                    trail = advance_trail(
                        side=pos.side,
                        entry=pos.avg_entry_price,
                        original_sl=sig.stop_loss,
                        current_sl=pos.current_sl,
                        current_price=price,
                        current_state=pos.trail_state,
                    )
                    if trail.advanced:
                        pos.current_sl = trail.new_sl
                        pos.trail_state = trail.new_state

            await update_position_pnl(db, pos)
            updated += 1

        await db.commit()

    log.info("Position monitor: closed=%d, updated=%d", closed, updated)
    return {"closed": closed, "updated": updated}
