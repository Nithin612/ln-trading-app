"""Celery task for pair-signal shadow minting (Phase 6.5b).

Nightly, after EOD bar ingestion + single-name signal generation, screen the universe
(df + adf arms) and mint SHADOW pair signals for currently-extreme candidates. Writes
only to `pair_signals` (is_shadow=True) — never a real order, never the single-name path.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.pair_tasks.mint_pair_signals", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def mint_pair_signals(self: object) -> dict[str, int]:  # noqa: ARG001
    """Nightly pair task: resolve open shadow pair signals from the fresh tape, then mint
    new ones for the day. Skips market holidays. Shadow-only (writes only pair_signals)."""
    return run_db_task(_run_mint)


async def _run_mint() -> dict[str, int]:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from app.db.session import AsyncSessionFactory
    from app.services.market_calendar import is_trading_day
    from app.services.pair_minter import mint_pair_signals as _mint
    from app.services.pair_outcome import track_pair_outcomes

    async with AsyncSessionFactory() as db:
        today_ist = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
        if not await is_trading_day(db, today_ist):
            log.info("Pair task skipped: %s is a market holiday", today_ist)
            return {"pairs_minted": 0, "pairs_resolved": 0}
        resolved = await track_pair_outcomes(db)  # resolve open signals from the fresh tape
        minted = await _mint(db)  # then mint today's new extremes
        log.info("Pair task: resolved %d, minted %d shadow pair signals", resolved, len(minted))
        return {"pairs_minted": len(minted), "pairs_resolved": resolved}
