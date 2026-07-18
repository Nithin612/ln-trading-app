"""Heal all EOD tables up to today — equities (+CA sweep), F&O, VIX, FII/DII.

Usage:
    uv run python scripts/catchup_eod.py [--lookback 21]

Runs the SAME self-healing functions the Celery beat tasks use
(services/eod_catchup.py), so a manual run after any quiet spell is
byte-for-byte the recovery the next beat evening would perform.
Idempotent — every underlying upsert is ON CONFLICT DO NOTHING.
Holes older than the lookback window need scripts/backfill_eod.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Runnable from any cwd: backend/ (the `app` package root) onto sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.eod_catchup import (  # noqa: E402
    LOOKBACK_DAYS,
    catchup_equities_eod,
    catchup_fii_dii,
    catchup_fo_eod,
)


async def run(lookback_days: int) -> int:
    today_ist = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
    print(f"EOD catch-up to {today_ist} (lookback {lookback_days}d)", flush=True)

    async with AsyncSessionFactory() as db:
        equities = await catchup_equities_eod(db, today_ist, lookback_days)
        print(f"equities : {json.dumps(equities)}", flush=True)
        fo = await catchup_fo_eod(db, today_ist, lookback_days)
        print(f"f&o      : {json.dumps(fo)}", flush=True)
        fii_dii = await catchup_fii_dii(db, today_ist, lookback_days)
        print(f"fii/dii  : {json.dumps(fii_dii)}", flush=True)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookback",
        type=int,
        default=LOOKBACK_DAYS,
        help=f"calendar days to heal (default {LOOKBACK_DAYS})",
    )
    args = parser.parse_args()
    if args.lookback < 1:
        print("--lookback must be >= 1", file=sys.stderr)
        return 2
    return asyncio.run(run(args.lookback))


if __name__ == "__main__":
    raise SystemExit(main())
