"""Seed the nse_holidays table (Phase 2 slice 1).

Two sources, honestly separated:

1. DERIVED (past, ground truth): any weekday inside the ohlcv_1d data span
   with zero candles across all stocks was a market closure — the bhavcopy
   data itself is the authority for history.
2. PUBLISHED (future): weekday holidays from the NSE circular, maintained
   in the FUTURE_HOLIDAYS dict below. Movable-festival dates for years NSE
   has not yet published (or that need confirmation) are NOT guessed —
   add them via the admin endpoint (POST /api/v1/calendar/holidays) when
   the circular lands. The market-calendar service logs a warning when
   queried beyond seeded coverage.

Idempotent: upserts by date; never deletes admin-entered rows.

Run: uv run python scripts/seed_nse_holidays.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Weekday NSE trading holidays already published for dates the bhavcopy
# span cannot cover. Verify against the NSE circular before extending —
# guessing festival dates is a trading-correctness bug.
FUTURE_HOLIDAYS: dict[date, str] = {
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 12, 25): "Christmas",
}


async def main() -> int:
    async with AsyncSessionFactory() as db:
        span = (
            await db.execute(
                text("SELECT MIN(time)::date AS lo, MAX(time)::date AS hi FROM ohlcv_1d")
            )
        ).one()
        if span.lo is None:
            print("ohlcv_1d is empty — run scripts/backfill_eod.py first")
            return 2

        session_dates = {
            r[0]
            for r in (
                await db.execute(text("SELECT DISTINCT time::date FROM ohlcv_1d"))
            ).all()
        }

        derived: dict[date, str] = {}
        d = span.lo
        while d <= span.hi:
            if d.weekday() <= 4 and d not in session_dates:
                derived[d] = "derived from bhavcopy session gap"
            d += timedelta(days=1)

        rows = [(k, v, "derived") for k, v in sorted(derived.items())] + [
            (k, v, "published") for k, v in sorted(FUTURE_HOLIDAYS.items()) if k > span.hi
        ]

        inserted = 0
        for holiday_date, name, source in rows:
            result = await db.execute(
                text(
                    "INSERT INTO nse_holidays (holiday_date, name, source)"
                    " VALUES (:d, :n, :s) ON CONFLICT (holiday_date) DO NOTHING"
                ),
                {"d": holiday_date, "n": name, "s": source},
            )
            inserted += result.rowcount or 0
        await db.commit()

        print(
            f"bhavcopy span {span.lo} → {span.hi}: {len(derived)} derived weekday"
            f" closures; {len(rows) - len(derived)} published future rows;"
            f" {inserted} inserted (rest already present)"
        )
        print("coverage ends at the last seeded holiday — add new NSE circulars"
              " via POST /api/v1/calendar/holidays")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
