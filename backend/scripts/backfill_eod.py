"""Backfill daily OHLCV from NSE bhavcopy archives.

Usage:
    uv run python scripts/backfill_eod.py 2023-07-01 2026-07-02 [--delay 0.7]

Idempotent (ON CONFLICT DO NOTHING per row) — safe to re-run or resume.
Polite to NSE archives: one download per session with a delay; holidays and
weekends come back as 'skipped' and cost one HEAD-ish request.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Runnable from any cwd: backend/ (the `app` package root) onto sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.bhavcopy_service import ingest_bhavcopy_date  # noqa: E402


async def backfill(from_date: date, to_date: date, delay: float) -> int:
    ok = skipped = rows = 0
    sessions = [
        from_date + timedelta(days=i)
        for i in range((to_date - from_date).days + 1)
        if (from_date + timedelta(days=i)).weekday() < 5
    ]
    total = len(sessions)
    print(f"Backfilling {total} weekday sessions {from_date} → {to_date}", flush=True)

    async with AsyncSessionFactory() as db:
        for i, d in enumerate(sessions, 1):
            result = await ingest_bhavcopy_date(db, d)
            if result.status == "ok":
                ok += 1
                rows += result.rows_inserted
            else:
                skipped += 1
            if i % 20 == 0 or i == total:
                print(
                    f"[{i}/{total}] {d} — ok={ok} skipped={skipped} rows={rows}",
                    flush=True,
                )
            await asyncio.sleep(delay)

    print(f"DONE ok={ok} skipped={skipped} rows_inserted={rows}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("from_date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("to_date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("--delay", type=float, default=0.7, help="seconds between downloads")
    args = parser.parse_args()
    if args.from_date > args.to_date:
        print("from_date must be <= to_date", file=sys.stderr)
        return 2
    return asyncio.run(backfill(args.from_date, args.to_date, args.delay))


if __name__ == "__main__":
    raise SystemExit(main())
