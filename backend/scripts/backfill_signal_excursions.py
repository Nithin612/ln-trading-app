#!/usr/bin/env python
"""One-off backfill of signal-level MFE/MAE (Phase 6 slice 6.1).

Drains the terminal-outcome cohort (>= OUTCOME_EPOCH) in batches, then exits.
Idempotent — a re-run only touches rows that still lack an excursion. Rows whose
window ends on the current IST day are deferred (their 1m tape may still be
ingesting); the 5-min expiry beat picks them up once the day has passed.

Usage:  cd backend && uv run python scripts/backfill_signal_excursions.py
"""

from __future__ import annotations

import asyncio
import logging

from app.db.session import AsyncSessionFactory
from app.services.signal_excursions import compute_outcome_excursions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_signal_excursions")


async def _main() -> None:
    total = 0
    async with AsyncSessionFactory() as db:
        while True:
            n = await compute_outcome_excursions(db, limit=500)
            total += n
            log.info("batch computed %d (running total %d)", n, total)
            if n == 0:
                break
    log.info("backfill complete: %d outcomes now carry excursion", total)


if __name__ == "__main__":
    asyncio.run(_main())
