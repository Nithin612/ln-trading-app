"""Scoped intraday morning-window repair from official Kite candles.

Born from soak #3 (2026-07-14, ledger §Third soak): the worker started
09:26:42 instead of pre-09:15, so the first ~12 minutes of live-minted
candles are missing or wrong (opens from 09:24:44 snapshot ticks, volume
short). This tool replaces exactly that window with official data:

1. Refetch official 5m candles for [09:15, --until-ist) on --day for the
   full active-EQ universe (the live worker's subscription join), one
   throttled request per stock via ThrottledKite (~3 req/s).
   ON CONFLICT DO UPDATE — partial/wrong live rows MUST be replaced, so
   backfill_intraday.py's DO-NOTHING semantics can't be reused here.
2. Recompute the 15m and 1h buckets that contain the window as straight
   5m aggregates (open = first bar's open, close = last bar's close,
   high/low = max/min, volume = sum), also DO UPDATE.

1m is deliberately NOT repaired (07-13 precedent: low-value live-only
table). Idempotent; safe to re-run. Touches nothing outside the window.

Usage:
  uv run python scripts/repair_morning_window.py --day 2026-07-14              # real run
  uv run python scripts/repair_morning_window.py --day 2026-07-14 --dry-run    # 5 stocks, no writes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broker.kite_rest import KiteException, ThrottledKite, TokenException  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.broker import BrokerToken, KiteInstrument  # noqa: E402
from app.models.market_data import Ohlcv5m  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from sqlalchemy import CursorResult, select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
SESSION_OPEN = time(9, 15)
COMMIT_EVERY = 100  # stocks per transaction
ABORT_IF_FIRST_N_ALL_FAIL = 20  # dead-token tripwire; isolated failures are tolerated

# Aggregate a window of 5m bars into one enclosing bucket (15m or 1h).
# Table names are hardcoded literals (not caller input); values are binds.
RECOMPUTE_SQL = """
INSERT INTO {table} (time, stock_id, open, high, low, close, volume, is_complete)
SELECT :t0, stock_id,
       (array_agg(open  ORDER BY time ASC))[1],
       max(high), min(low),
       (array_agg(close ORDER BY time DESC))[1],
       sum(volume), true
FROM ohlcv_5m
WHERE time >= :t0 AND time < :t1 AND is_complete
GROUP BY stock_id
ON CONFLICT (time, stock_id) DO UPDATE
SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, volume = EXCLUDED.volume, is_complete = true
"""


async def _active_token(db: AsyncSession) -> str:
    now = datetime.now(UTC)
    token = (
        await db.execute(
            select(BrokerToken)
            .where(BrokerToken.is_active.is_(True), BrokerToken.expires_at > now)
            .order_by(BrokerToken.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if token is None:
        raise SystemExit("No live Kite token (they die ~6:00 AM IST — run kite_login.py).")
    return str(token.access_token)


async def _universe(db: AsyncSession) -> list[tuple[int, int, str]]:
    """(stock_id, instrument_token, symbol) — the live worker's subscription join."""
    rows = (
        await db.execute(
            select(Stock.id, KiteInstrument.instrument_token, Stock.symbol)
            .join(
                KiteInstrument,
                (KiteInstrument.tradingsymbol == Stock.symbol)
                & (KiteInstrument.exchange == Stock.exchange),
            )
            .where(Stock.is_active.is_(True), KiteInstrument.instrument_type == "EQ")
            .order_by(Stock.symbol)
        )
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def _rows(
    stock_id: int, candles: list[dict[str, Any]], lo: datetime, hi: datetime
) -> list[dict[str, Any]]:
    """Official candles → upsert rows, bar START inside [lo, hi) IST only."""
    out: list[dict[str, Any]] = []
    for c in candles:
        dt = c["date"]
        if dt.tzinfo is None:  # defensive — kiteconnect returns IST-aware
            dt = dt.replace(tzinfo=IST)
        ist = dt.astimezone(IST)
        if not (lo <= ist < hi):
            continue
        out.append(
            {
                "time": ist.astimezone(UTC),
                "stock_id": stock_id,
                "open": str(c["open"]),
                "high": str(c["high"]),
                "low": str(c["low"]),
                "close": str(c["close"]),
                "volume": int(c["volume"]),
                "is_complete": True,
            }
        )
    return out


async def _refetch_5m(
    db: AsyncSession,
    kite: ThrottledKite,
    universe: list[tuple[int, int, str]],
    lo: datetime,
    hi: datetime,
    dry_run: bool,
) -> tuple[int, int] | None:
    """Fetch+upsert the 5m window per stock. (upserted, failed), None = dead token."""
    upserted = failed = consecutive_head_failures = 0
    for i, (stock_id, instrument_token, symbol) in enumerate(universe, 1):
        try:
            candles = await kite.historical_data(
                instrument_token,
                lo.replace(tzinfo=None),  # kiteconnect treats naive as IST
                hi.replace(tzinfo=None),
                "5minute",
            )
        except (KiteException, TokenException) as exc:
            failed += 1
            if i <= ABORT_IF_FIRST_N_ALL_FAIL:
                consecutive_head_failures += 1
                if consecutive_head_failures == ABORT_IF_FIRST_N_ALL_FAIL:
                    print(f"first {i} calls ALL failed — token dead? aborting", flush=True)
                    return None
            print(f"  FAIL {symbol}: {exc}", flush=True)
            continue
        consecutive_head_failures = 0
        rows = _rows(stock_id, candles, lo, hi)
        if dry_run:
            print(f"  {symbol}: {rows}", flush=True)
            continue
        if rows:
            stmt = pg_insert(Ohlcv5m).values(rows)
            await db.execute(
                stmt.on_conflict_do_update(
                    index_elements=["time", "stock_id"],
                    set_={
                        k: getattr(stmt.excluded, k)
                        for k in ("open", "high", "low", "close", "volume", "is_complete")
                    },
                )
            )
            upserted += len(rows)
        if i % COMMIT_EVERY == 0:
            await db.commit()
            print(f"  {i}/{len(universe)} · {upserted} bars · {failed} failed", flush=True)
    if not dry_run:
        await db.commit()
    return upserted, failed


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", type=date.fromisoformat, required=True)
    ap.add_argument("--until-ist", default="09:30", help="window end, bar starts < this (HH:MM)")
    ap.add_argument("--dry-run", action="store_true", help="first 5 stocks, print, no writes")
    args = ap.parse_args()

    h, m = (int(x) for x in args.until_ist.split(":"))
    lo = datetime.combine(args.day, SESSION_OPEN, tzinfo=IST)
    hi = datetime.combine(args.day, time(h, m), tzinfo=IST)
    if hi <= lo:
        raise SystemExit("--until-ist must be after 09:15")

    async with AsyncSessionFactory() as db:
        token = await _active_token(db)
        universe = await _universe(db)
        kite = ThrottledKite(token)
        if args.dry_run:
            universe = universe[:5]
        print(f"repair {args.day} [{lo:%H:%M}–{hi:%H:%M} IST) · {len(universe)} stocks", flush=True)

        result = await _refetch_5m(db, kite, universe, lo, hi, args.dry_run)
        if result is None:
            return 2
        upserted, failed = result
        print(
            f"5m done: {upserted} bars upserted · {failed}/{len(universe)} stocks failed",
            flush=True,
        )
        if args.dry_run:
            return 0

        # Recompute the enclosing 15m and 1h buckets from 5m aggregates.
        t0 = lo.astimezone(UTC)
        for table, minutes in (("ohlcv_15m", 15), ("ohlcv_1h", 60)):
            res = cast(
                CursorResult[Any],
                await db.execute(
                    text(RECOMPUTE_SQL.format(table=table)),
                    {"t0": t0, "t1": t0 + timedelta(minutes=minutes)},
                ),
            )
            await db.commit()
            print(f"{table} 09:15 bucket recomputed: {res.rowcount} rows", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
