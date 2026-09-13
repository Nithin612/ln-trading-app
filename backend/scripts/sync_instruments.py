"""Refresh `kite_instruments` from Kite's PUBLIC instruments dump.

    uv run python scripts/sync_instruments.py

⭐ No Kite token is required. The dump at `api.kite.trade/instruments` is served
without an `Authorization` header, which is the whole reason this table can have
a scheduled owner (`app.tasks.market_data_tasks.sync_kite_instruments`, 08:00 IST
weekdays) — an access token dies ~06:00 IST daily and is renewable only through
an interactive OAuth login, so a job that needed one would go dark on exactly the
mornings nobody logged in.

This script is the manual remedy `make live-worker` prints when it refuses to
start with EXIT_NO_UNIVERSE (5). It is idempotent: upsert plus the two-tier stale
sweep, and it commits itself.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.broker.kite_client import sync_instruments  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        return await sync_instruments(db)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        n = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — the operator needs the reason, not a traceback
        print(f"instrument sync FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"kite_instruments: {n} rows synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
