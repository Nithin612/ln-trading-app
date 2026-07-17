"""Deactivate master stocks that have no live Kite listing.

Born from the 2026-07-17 universe ruling (phase-03 ledger §Decisions,
user: option (a) + (c)): after the kite_instruments stale sweep, active
stocks whose symbol has NO EQ-type listing in the dump are ghosts — the
screener scores them but no data source or broker path exists. Two
reasons, recorded separately so either group can be reversed alone:

  dead_no_listing  no EQ-type kite_instruments row for the symbol on ANY
                   exchange, plain or series-suffixed (delisted or
                   suspended everywhere Kite trades).
  moved_bse_only   master says NSE and NSE has nothing (plain or
                   suffixed), but a plain BSE EQ listing exists. Ruling:
                   deactivate rather than follow to BSE (NSE-first
                   platform; names that LEFT NSE trade thin on BSE).

Trade-to-trade stocks are NOT touched — ruling (a): a series-suffixed
NSE listing (SYMBOL-BE, -BZ, -SM, -ST) means the stock is alive under
surveillance; it stays active in the master (EOD keeps flowing) and is
excluded from LIVE coverage naturally because the worker join matches
plain symbols only. Membership is dynamic: when NSE moves it back to
the EQ series, the daily sync + join re-cover it with zero action.
Index rows riding the dump (segment='INDICES') never count as listings.

Forensic + reversal: deactivated rows are appended to the cumulative
table `forensic_stocks_deactivated` (stock_id, symbol, exchange, reason,
run_at) in the SAME statement snapshot as the update. Reactivate a run
with (run_at is stored UTC — compare in IST, else a 00:00–05:29 IST run
lands on the previous UTC date and the filter silently matches nothing):
  UPDATE stocks s SET is_active = true
  FROM forensic_stocks_deactivated f
  WHERE s.id = f.stock_id
    AND (f.run_at AT TIME ZONE 'Asia/Kolkata')::date = '<IST run date>';

Idempotent (a second run finds nothing active to touch); safe to re-run
after any instrument sync to sweep newly-delisted names.

Usage (APP_DEBUG=false silences the engine's SQL echo):
  APP_DEBUG=false uv run python scripts/deactivate_dead_stocks.py --dry-run
  APP_DEBUG=false uv run python scripts/deactivate_dead_stocks.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

# Active stocks with no plain-or-suffixed EQ listing on their own exchange;
# reason splits on whether a plain BSE listing exists. `segment != 'INDICES'`
# keeps index rows from counting as listings; the suffix LIKE keeps every
# T2T/series variant (SYMBOL-…) counting as alive.
_CLASSIFY_SQL = """
SELECT s.id, s.symbol, s.exchange,
       CASE WHEN EXISTS (
            SELECT 1 FROM kite_instruments b
            WHERE b.exchange = 'BSE' AND b.instrument_type = 'EQ'
              AND b.segment != 'INDICES' AND b.tradingsymbol = s.symbol)
            THEN 'moved_bse_only' ELSE 'dead_no_listing' END AS reason
FROM stocks s
WHERE s.is_active
  AND NOT EXISTS (
      SELECT 1 FROM kite_instruments ki
      WHERE ki.instrument_type = 'EQ' AND ki.segment != 'INDICES'
        AND ki.exchange = s.exchange
        AND (ki.tradingsymbol = s.symbol OR ki.tradingsymbol LIKE s.symbol || '-%'))
ORDER BY reason, s.symbol
"""

_FORENSIC_DDL = """
CREATE TABLE IF NOT EXISTS forensic_stocks_deactivated (
    stock_id BIGINT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    reason TEXT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


# Snapshot + deactivate as ONE statement: classify, forensic INSERT, and
# UPDATE all read the same statement snapshot, so a sync_instruments
# commit racing this run can neither deactivate a just-relisted stock
# nor record a forensic reason that disagrees with the acted-on one
# (bug-hunter MEDIUM, 2026-07-17: the three-statement version re-read
# committed state per statement under READ COMMITTED).
_SWEEP_SQL = f"""
WITH doomed AS ({_CLASSIFY_SQL}),
ins AS (
    INSERT INTO forensic_stocks_deactivated (stock_id, symbol, exchange, reason)
    SELECT id, symbol, exchange, reason FROM doomed
)
UPDATE stocks s SET is_active = false FROM doomed d WHERE s.id = d.id
RETURNING d.id, d.symbol, d.exchange, d.reason
"""


async def deactivate_dead_stocks(db: AsyncSession, dry_run: bool) -> dict[str, int]:
    """Classify, snapshot, deactivate. Returns {reason: count}."""
    mixed_case = (
        await db.execute(
            text("SELECT symbol FROM stocks WHERE is_active AND symbol <> upper(symbol)")
        )
    ).scalars().all()
    if mixed_case:
        # the classify SQL is deliberately case-sensitive (it mirrors the
        # worker join) — a mixed-case master symbol would classify dead
        # even with a live listing; surface instead of sweeping silently
        print(f"  WARNING: {len(mixed_case)} active mixed-case symbol(s): {mixed_case}")

    if dry_run:
        rows = (await db.execute(text(_CLASSIFY_SQL))).all()
    else:
        await db.execute(text(_FORENSIC_DDL))
        rows = sorted((await db.execute(text(_SWEEP_SQL))).all(), key=lambda r: (r[3], r[1]))

    counts: dict[str, int] = {}
    for _id, symbol, exchange, reason in rows:
        counts[reason] = counts.get(reason, 0) + 1
        print(f"  {reason}: {symbol} ({exchange}, id={_id})")
    return counts


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="classify + print, no writes")
    args = ap.parse_args()

    async with AsyncSessionFactory() as db:
        counts = await deactivate_dead_stocks(db, dry_run=args.dry_run)
        if not args.dry_run:
            await db.commit()
    mode = "DRY-RUN, nothing written" if args.dry_run else "deactivated + forensic snapshot"
    print(f"{mode}: {counts or 'nothing matched'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
