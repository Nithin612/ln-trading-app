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
    """Mint shadow pair signals for the day. Skips market holidays. Shadow-only."""
    return run_db_task(_run_mint)


async def _run_mint() -> dict[str, int]:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from app.db.session import AsyncSessionFactory
    from app.services.market_calendar import is_trading_day
    from app.services.pair_minter import mint_pair_signals as _mint

    async with AsyncSessionFactory() as db:
        today_ist = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
        if not await is_trading_day(db, today_ist):
            log.info("Pair minting skipped: %s is a market holiday", today_ist)
            return {"pairs_minted": 0}
        minted = await _mint(db)
        log.info("Pair minting: %d shadow pair signals", len(minted))
        return {"pairs_minted": len(minted)}
