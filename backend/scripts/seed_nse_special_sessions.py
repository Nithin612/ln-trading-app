"""Seed `nse_special_sessions` — exchange sessions held on a Saturday or Sunday.

The same honesty split as `seed_nse_holidays.py`:

1. DERIVED (past, ground truth): any Saturday or Sunday with daily bars in `ohlcv_1d` WAS a
   session — the bhavcopy is the authority for history. Measured 2026-10-03: 8 such dates
   (2019-10-27 … 2026-02-01). Their hours are not in the bhavcopy, so `open_ist`/`close_ist`
   stay NULL ("regular or not recorded"); that only matters for an intraday guard, and these
   dates are all in the past.
2. ANNOUNCED (future): sessions NSE publishes by circular (a Budget Saturday, a DR drill, a
   muhurat Sunday) are added through the admin endpoint `POST /api/v1/calendar/special-sessions`
   with their hours — never guessed here.

Idempotent: inserts by date, never overwrites or deletes a row an admin entered.

Run: uv run python scripts/seed_nse_special_sessions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_DERIVE = text("""
    SELECT (time AT TIME ZONE 'Asia/Kolkata')::date AS d, count(*) AS bars
    FROM ohlcv_1d
    GROUP BY 1
    HAVING extract(isodow FROM (time AT TIME ZONE 'Asia/Kolkata')::date) >= 6
    ORDER BY 1
""")

_INSERT = text("""
    INSERT INTO nse_special_sessions (session_date, name, source)
    VALUES (:d, :name, 'derived')
    ON CONFLICT (session_date) DO NOTHING
""")


def session_name(d: date, bars: int) -> str:
    return f"{d.strftime('%A')} session (bhavcopy has {bars:,} bars)"


async def main(dry_run: bool) -> int:
    async with AsyncSessionFactory() as db:
        rows = [(r[0], int(r[1])) for r in (await db.execute(_DERIVE)).all()]
        for d, bars in rows:
            print(f"{d}  {session_name(d, bars)}")
        if dry_run:
            print(f"dry run: {len(rows)} weekend session(s) found, nothing written")
            return 0
        written = 0
        for d, bars in rows:
            res = await db.execute(_INSERT, {"d": d, "name": session_name(d, bars)})
            written += int(getattr(res, "rowcount", 0) or 0)
        await db.commit()
    print(f"{len(rows)} weekend session(s) derived · {written} new row(s) written")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    raise SystemExit(asyncio.run(main(ap.parse_args().dry_run)))
