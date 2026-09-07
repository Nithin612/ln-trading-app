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


# Longest run of consecutive missing weekdays still credible as a market closure.
# NSE's longest is a festival abutting a weekend; anything longer is a hole in our data.
_MAX_CLOSURE_RUN = 5


def derive_closures(
    lo: date, hi: date, session_dates: set[date]
) -> tuple[dict[date, str], list[tuple[date, date, int]]]:
    """Split missing weekdays in [lo, hi] into real closures and data gaps.

    Returns `(closures, skipped_gaps)`. A run of missing weekdays counts as a market
    closure only when it is at most `_MAX_CLOSURE_RUN` long; anything longer is a hole in
    OUR data and is reported instead of recorded.

    ⚠ The naive version — mark every missing weekday — corrupted the calendar on
    2026-09-07. After the dev database was restored, `ohlcv_1d` held 2020-03-20→27 (a
    backfill smoke run) plus 2023-07-03→today, with a 3.3-year hole between, and every
    weekday in that hole became a "holiday": **896 of them against a real rate of ~13 a
    year.** 850 rows had to be deleted by hand. Trading-day arithmetic drives signal
    validity windows, so a fabricated holiday is a correctness bug, not a cosmetic one.

    The historical backfill (`scripts/backfill_ohlcv_history.py`) makes partial spans
    normal, so this is now the expected case rather than an oddity.
    """
    closures: dict[date, str] = {}
    skipped: list[tuple[date, date, int]] = []
    d = lo
    while d <= hi:
        if d.weekday() > 4 or d in session_dates:
            d += timedelta(days=1)
            continue

        # Collect the WHOLE consecutive run before judging it — a run is only
        # classifiable once you know how long it is.
        run_start = d
        run: list[date] = []
        while d <= hi and (d.weekday() > 4 or d not in session_dates):
            if d.weekday() <= 4:
                run.append(d)
            d += timedelta(days=1)

        if len(run) <= _MAX_CLOSURE_RUN:
            for h in run:
                closures[h] = "derived from bhavcopy session gap"
        else:
            skipped.append((run_start, run[-1], len(run)))
    return closures, skipped


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

        derived, skipped_gaps = derive_closures(span.lo, span.hi, session_dates)
        for lo, hi, n in skipped_gaps:
            print(
                f"⚠ SKIPPED {lo} → {hi} ({n} weekdays): too long to be a market closure —"
                " this is a gap in ohlcv_1d, not a holiday. Backfill it, then re-run.",
                flush=True,
            )

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
