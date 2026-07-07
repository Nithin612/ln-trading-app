"""Kite 5m/15m historical backfill + session-completeness QA manifest
(Phase 2 track T — prerequisite for slice 8c intraday goldens).

Universe: active, non-CA-quarantined Nifty50 + F&O stocks. Candles flow
through the shared ThrottledKite client (~3 req/s), in ≤60-day chunks,
into ohlcv_5m / ohlcv_15m with `is_complete=true`. Idempotent: composite
PK (time, stock_id) + ON CONFLICT DO NOTHING — history is NEVER replaced
(re-runs only fill holes); reruns resume from each stock's last stored
bar unless --full.

Timezone canon: Kite returns IST-aware datetimes; storage is UTC via
.astimezone(UTC) (never tzinfo replace). Bars outside the 09:15–15:30 IST
session window are dropped (pre-open/AMO artifacts must not mint candles).

QA manifest (tests/goldens/intraday_qa_manifest.json): per (symbol,
timeframe) — actual depth (first/last bar), sessions present vs NSE
calendar expectation over the stock's OWN available depth, partial
sessions, gap ratio, and the 8c admission verdict: gap_ratio > threshold
(default 5%) ⇒ EXCLUDED, never patched. Kite's intraday history depth is
not guaranteed (plan risk #6) — the manifest records what each stock
actually has; 8c pins goldens only on admitted stocks.

Usage:
  uv run python scripts/backfill_intraday.py                     # both tfs, resume
  uv run python scripts/backfill_intraday.py --timeframe 15m
  uv run python scripts/backfill_intraday.py --since 2023-07-03 --full
  uv run python scripts/backfill_intraday.py --manifest-only     # recompute QA only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time as _time
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests.exceptions as _rex  # noqa: E402
from app.broker.kite_client import sync_instruments  # noqa: E402
from app.broker.kite_rest import KiteException, ThrottledKite, TokenException  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.broker import BrokerToken, KiteInstrument  # noqa: E402
from app.models.market_calendar import NseHoliday  # noqa: E402
from app.models.market_data import Ohlcv5m, Ohlcv15m  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "goldens" / "intraday_qa_manifest.json"
)

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)  # bar START times must be < close

TF = {
    "5m": {"model": Ohlcv5m, "interval": "5minute", "bars_per_session": 75},
    "15m": {"model": Ohlcv15m, "interval": "15minute", "bars_per_session": 25},
}
CHUNK_DAYS = 60
INSERT_BATCH = 1000


def chunk_ranges(since: date, until: date, chunk_days: int = CHUNK_DAYS) -> list[tuple[date, date]]:
    """[since, until] as inclusive windows of ≤chunk_days each."""
    if until < since:
        return []
    out: list[tuple[date, date]] = []
    lo = since
    while lo <= until:
        hi = min(lo + timedelta(days=chunk_days - 1), until)
        out.append((lo, hi))
        lo = hi + timedelta(days=1)
    return out


def in_session_window(bar_start_ist: datetime) -> bool:
    """NSE cash session guard: bar start ∈ [09:15, 15:30) IST."""
    t = bar_start_ist.timetz().replace(tzinfo=None)
    return SESSION_OPEN <= t < SESSION_CLOSE


def rows_from_candles(stock_id: int, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kite candle dicts → ohlcv rows (UTC storage, session-filtered)."""
    rows: list[dict[str, Any]] = []
    for c in candles:
        dt: datetime = c["date"]
        if dt.tzinfo is None:  # defensive — kiteconnect returns IST-aware
            dt = dt.replace(tzinfo=IST)
        ist = dt.astimezone(IST)
        if not in_session_window(ist):
            continue
        rows.append(
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
    return rows


def gap_verdict(
    sessions_present: int, sessions_expected: int, threshold: float
) -> tuple[float, bool]:
    """(gap_ratio, admitted). No expected sessions ⇒ fully gapped.

    The verdict compares the ROUNDED ratio so a 95/100 stock sits exactly
    at a 5% threshold (float dust must not flip an admission)."""
    if sessions_expected <= 0:
        return 1.0, False
    ratio = round(1.0 - sessions_present / sessions_expected, 4)
    return ratio, ratio <= threshold


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
        raise SystemExit(
            "No live Kite token. Log in via the app page /broker/kite first "
            "(tokens die ~6:00 AM IST daily)."
        )
    return str(token.access_token)


async def _universe(db: AsyncSession) -> list[tuple[int, str]]:
    rows = (
        await db.execute(
            select(Stock.id, Stock.symbol)
            .where(
                Stock.is_active.is_(True),
                Stock.ca_flagged_at.is_(None),
                (Stock.is_nifty50.is_(True)) | (Stock.is_fno.is_(True)),
            )
            .order_by(Stock.symbol)
        )
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


async def _instrument_tokens(db: AsyncSession, symbols: list[str]) -> dict[str, int]:
    rows = (
        await db.execute(
            select(KiteInstrument.tradingsymbol, KiteInstrument.instrument_token).where(
                KiteInstrument.exchange == "NSE",
                KiteInstrument.instrument_type == "EQ",
                KiteInstrument.tradingsymbol.in_(symbols),
            )
        )
    ).fetchall()
    return {r[0]: r[1] for r in rows}


async def _trading_days(db: AsyncSession, start: date, end: date) -> set[date]:
    """NSE sessions in [start, end]: weekdays minus the holiday table."""
    holidays = {
        r[0]
        for r in (
            await db.execute(
                select(NseHoliday.holiday_date).where(
                    NseHoliday.holiday_date >= start, NseHoliday.holiday_date <= end
                )
            )
        ).fetchall()
    }
    out: set[date] = set()
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            out.add(d)
        d += timedelta(days=1)
    return out


async def _last_stored(db: AsyncSession, model: Any, stock_id: int, until: date) -> date | None:
    """Resume point: last COMPLETED session at or before `until`.

    Bounded and is_complete-filtered on purpose — the live tick consumer
    mints TODAY's (possibly forming) intraday rows; an unbounded max(time)
    would report today, make start > until, and silently skip the whole
    historical fetch (bug-hunter finding, Phase-2 gate)."""
    cutoff = datetime.combine(until + timedelta(days=1), time.min, tzinfo=IST).astimezone(UTC)
    mx = (
        await db.execute(
            select(func.max(model.time)).where(
                model.stock_id == stock_id,
                model.time < cutoff,
                model.is_complete.is_(True),
            )
        )
    ).scalar_one_or_none()
    return mx.astimezone(IST).date() if mx else None


async def backfill_stock_tf(
    db: AsyncSession,
    kite: ThrottledKite,
    stock_id: int,
    instrument_token: int,
    tf: str,
    since: date,
    until: date,
    full: bool,
) -> tuple[int, int]:
    """One (stock, timeframe): fetch chunks → filtered rows → DO NOTHING
    upserts. Returns (bars_inserted_or_skipped, requests_made)."""
    model = TF[tf]["model"]
    start = since
    if not full:
        last = await _last_stored(db, model, stock_id, until)
        if last is not None:
            start = max(since, last)  # refetch the last stored day — cheap hole guard
    inserted = requests = 0
    for lo, hi in chunk_ranges(start, until):
        candles = await kite.historical_data(
            instrument_token,
            datetime.combine(lo, time.min),
            datetime.combine(hi, time(23, 59, 59)),
            str(TF[tf]["interval"]),
        )
        requests += 1
        rows = rows_from_candles(stock_id, candles)
        for i in range(0, len(rows), INSERT_BATCH):
            batch = rows[i : i + INSERT_BATCH]
            stmt = pg_insert(model).values(batch)
            await db.execute(stmt.on_conflict_do_nothing(index_elements=["time", "stock_id"]))
            inserted += len(batch)
        await db.commit()
    return inserted, requests


async def build_manifest(
    db: AsyncSession,
    universe: list[tuple[int, str]],
    timeframes: list[str],
    until: date,
    threshold: float,
) -> dict[str, Any]:
    """Session-completeness QA per (symbol, tf) over each stock's OWN depth."""
    entries: dict[str, Any] = {}
    for tf in timeframes:
        table = TF[tf]["model"].__tablename__  # type: ignore[union-attr]
        per_session = (
            await db.execute(
                text(
                    f"SELECT stock_id, (time AT TIME ZONE 'Asia/Kolkata')::date AS session,"  # noqa: S608
                    f" count(*) AS bars FROM {table} GROUP BY stock_id, session"
                )
            )
        ).fetchall()
        by_stock: dict[int, dict[date, int]] = {}
        for r in per_session:
            by_stock.setdefault(r.stock_id, {})[r.session] = r.bars

        full_bars = int(TF[tf]["bars_per_session"])  # type: ignore[arg-type]
        for stock_id, symbol in universe:
            sessions = by_stock.get(stock_id, {})
            key = f"{symbol}:{tf}"
            if not sessions:
                entries[key] = {
                    "symbol": symbol, "timeframe": tf, "bars": 0, "sessions": 0,
                    "gap_ratio": 1.0, "admitted": False, "reason": "no data",
                }
                continue
            first, last = min(sessions), max(sessions)
            expected = await _trading_days(db, first, min(last, until))
            present = set(sessions) & expected
            gap_ratio, admitted = gap_verdict(len(present), len(expected), threshold)
            partial = sum(1 for s in present if sessions[s] < full_bars)
            entries[key] = {
                "symbol": symbol,
                "timeframe": tf,
                "first_session": first.isoformat(),
                "last_session": last.isoformat(),
                "depth_days": (last - first).days,
                "bars": sum(sessions.values()),
                "sessions": len(present),
                "sessions_expected": len(expected),
                "partial_sessions": partial,
                "gap_ratio": gap_ratio,
                "admitted": admitted,
            }
    admitted = sum(1 for e in entries.values() if e["admitted"])
    return {
        "schema": "intraday-qa-manifest-v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "until": until.isoformat(),
        "gap_threshold": threshold,
        "admitted": admitted,
        "total": len(entries),
        "entries": dict(sorted(entries.items())),
    }


async def _run_backfill(
    db: AsyncSession,
    universe: list[tuple[int, str]],
    timeframes: list[str],
    args: argparse.Namespace,
) -> int:
    """Fetch loop over (stock, timeframe). Returns nonzero to abort the run
    (historical add-on missing is unrecoverable; anything else skips on)."""
    token = await _active_token(db)
    kite = ThrottledKite(token)

    symbols = [s for _, s in universe]
    tokens = await _instrument_tokens(db, symbols)
    if not tokens:
        print("kite_instruments empty — syncing instrument master first…", flush=True)
        await sync_instruments(db, token)
        await db.commit()
        tokens = await _instrument_tokens(db, symbols)

    missing = [s for s in symbols if s not in tokens]
    if missing:
        print(f"no NSE-EQ instrument token for {len(missing)}: "
              f"{missing[:10]}{'…' if len(missing) > 10 else ''}", flush=True)

    t0 = _time.perf_counter()
    total_rows = total_req = done = 0
    for stock_id, symbol in universe:
        if symbol not in tokens:
            continue
        for tf in timeframes:
            try:
                rows, reqs = await backfill_stock_tf(
                    db, kite, stock_id, tokens[symbol], tf,
                    args.since, args.until, args.full,
                )
            except TokenException as exc:
                # Token death (~6:00 AM IST) is a lifecycle event, not an
                # error loop — abort cleanly, don't hammer Kite unspaced.
                print(f"\n✗ Kite token expired/invalid: {exc}", flush=True)
                print("  Log in again (uv run python scripts/kite_login.py) and "
                      "rerun — resume skips everything already stored.", flush=True)
                return 4
            except (KiteException, _rex.RequestException) as exc:
                print(f"  ✗ {symbol}/{tf}: {type(exc).__name__}: {exc}", flush=True)
                if "permission" in str(exc).lower() or "subscribe" in str(exc).lower():
                    print(
                        "HISTORICAL API NOT ENABLED on this Kite app — add the "
                        "historical add-on at developers.kite.trade and rerun.",
                        flush=True,
                    )
                    return 3
                continue
            total_rows += rows
            total_req += reqs
        done += 1
        if done % 10 == 0 or done == len(universe):
            el = _time.perf_counter() - t0
            print(
                f"[{done}/{len(universe)}] rows≈{total_rows} req={total_req} "
                f"{el:.0f}s ({total_req / el if el else 0:.2f} req/s)",
                flush=True,
            )
    return 0


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeframe", choices=[*TF, "both"], default="both")
    ap.add_argument("--since", type=date.fromisoformat, default=date(2023, 7, 3))
    ap.add_argument(
        "--until", type=date.fromisoformat,
        default=datetime.now(IST).date() - timedelta(days=1),
    )
    ap.add_argument("--gap-threshold", type=float, default=0.05)
    ap.add_argument("--full", action="store_true", help="ignore resume points, refetch all")
    ap.add_argument("--manifest-only", action="store_true", help="skip fetching, QA only")
    ap.add_argument("--limit", type=int, default=0, help="first N symbols (smoke runs)")
    args = ap.parse_args()
    timeframes = list(TF) if args.timeframe == "both" else [args.timeframe]
    yesterday = datetime.now(IST).date() - timedelta(days=1)
    if args.until > yesterday:
        # Intra-session Kite bars are FORMING; storing them is_complete
        # would poison the no-look-ahead guarantee downstream.
        print(f"--until clamped to {yesterday} (today's bars may still be forming)")
        args.until = yesterday

    async with AsyncSessionFactory() as db:
        universe = await _universe(db)
        if args.limit:
            universe = universe[: args.limit]
        print(f"universe: {len(universe)} stocks · {timeframes} · "
              f"{args.since} → {args.until}", flush=True)

        if not args.manifest_only:
            rc = await _run_backfill(db, universe, timeframes, args)
            if rc:
                return rc

        manifest = await build_manifest(db, universe, timeframes, args.until, args.gap_threshold)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
        print(
            f"\nQA manifest → {MANIFEST_PATH.name}: {manifest['admitted']}/{manifest['total']} "
            f"(symbol,tf) admitted at gap ≤ {args.gap_threshold:.0%}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
