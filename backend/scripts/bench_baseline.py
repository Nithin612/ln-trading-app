"""Pandas-engine baseline benchmarks (Phase 1, pre-Rust).

Produces the "before" column for docs/PERFORMANCE.md:
  1. single-stock confluence eval (300 daily candles), best of 5
  2. full-universe scan (every active stock, latest 300 candles, one eval)
  3. full 2y × Nifty50 backtest (BacktestEngine, defaults)
  4. weight-grid cost: 3 sample combos on 10 stocks → extrapolated to
     200 combos × 50 stocks (extrapolation labelled as such)

Usage: uv run python scripts/backfill_eod.py first (data!), then
       uv run python scripts/bench_baseline.py
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.analysis.confluence import run_all_factors, score_from_factors  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def load_universe(
    nifty50_only: bool, min_rows: int, since: datetime | None = None
) -> dict[str, pd.DataFrame]:
    """{symbol: OHLCV frame} for active stocks with enough history."""
    where_n50 = "AND s.is_nifty50" if nifty50_only else ""
    since_clause = "AND o.time >= :since" if since is not None else ""
    params: dict[str, object] = {"since": since} if since is not None else {}

    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    f"SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume"
                    f" FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id"
                    f" WHERE s.is_active {where_n50} {since_clause}"
                    f" ORDER BY s.symbol, o.time"
                ),
                params,
            )
        ).fetchall()

    frames: dict[str, pd.DataFrame] = {}
    by_symbol: dict[str, list] = {}
    for r in rows:
        by_symbol.setdefault(r.symbol, []).append(r)
    for sym, rs in by_symbol.items():
        if len(rs) < min_rows:
            continue
        df = pd.DataFrame(
            {
                "time": [r.time for r in rs],
                "open": [float(r.open) for r in rs],
                "high": [float(r.high) for r in rs],
                "low": [float(r.low) for r in rs],
                "close": [float(r.close) for r in rs],
                "volume": [int(r.volume) for r in rs],
            }
        ).set_index("time")
        frames[sym] = df
    return frames


def bench_single_eval(df: pd.DataFrame) -> float:
    window = df.iloc[-300:]
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        factors = run_all_factors(window, timeframe="1d")
        score_from_factors(factors, window, 70)
        times.append(time.perf_counter() - t0)
    return min(times)


async def _gather_data() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """One event loop for all DB work — the app engine binds to the first
    loop it sees, so multiple asyncio.run() calls break asyncpg."""
    two_years_ago = datetime.now(UTC) - timedelta(days=365 * 2 + 30)
    n50_2y = await load_universe(True, min_rows=200, since=two_years_ago)
    all_latest = await load_universe(False, min_rows=60)
    return n50_2y, all_latest


def main() -> int:
    print(f"# Baseline bench — {datetime.now(UTC).isoformat(timespec='seconds')}")

    # ── data ──
    n50_2y, all_latest = asyncio.run(_gather_data())
    print(f"corpus: nifty50 2y = {len(n50_2y)} stocks · universe = {len(all_latest)} stocks")
    if not n50_2y:
        print("NO DATA — run scripts/backfill_eod.py first")
        return 2

    # ── 1. single eval ──
    sample = next(iter(sorted(n50_2y)))
    t_single = bench_single_eval(n50_2y[sample])
    print(f"\n1. single confluence eval (300 candles, {sample}): {t_single*1000:.1f} ms")

    # ── 2. universe scan ──
    t0 = time.perf_counter()
    for _sym, df in all_latest.items():
        window = df.iloc[-300:]
        factors = run_all_factors(window, timeframe="1d")
        score_from_factors(factors, window, 70)
    t_scan = time.perf_counter() - t0
    print(f"2. full-universe scan ({len(all_latest)} stocks): {t_scan:.1f} s")

    # ── 3. 2y × Nifty50 backtest ──
    cfg = BacktestConfig(
        timeframe="1d", universe="NIFTY50",
        capital=Decimal("500000"), risk_pct=Decimal("2"), min_confidence=70,
    )
    t0 = time.perf_counter()
    result = BacktestEngine(cfg).run(n50_2y)
    t_bt = time.perf_counter() - t0
    print(
        f"3. 2y × {len(n50_2y)}-stock backtest: {t_bt:.1f} s — "
        f"trades={result.total_trades} win%={result.win_rate_pct:.1f} "
        f"sharpe={result.sharpe:.2f} maxDD={result.max_drawdown_pct:.1f}%"
    )

    # ── 4. grid extrapolation ──
    subset = dict(sorted(n50_2y.items())[:10])
    combo_times = []
    for mult in (0.5, 1.0, 1.5):
        t0 = time.perf_counter()
        BacktestEngine(
            BacktestConfig(
                timeframe="1d", universe="X",
                capital=Decimal("500000"), risk_pct=Decimal("2"),
                min_confidence=70, weight_multipliers={"DOW_TREND": mult},
            )
        ).run(subset)
        combo_times.append(time.perf_counter() - t0)
    per_combo_10 = statistics.mean(combo_times)
    extrap_200_full = per_combo_10 * (len(n50_2y) / len(subset)) * 200
    print(
        f"4. weight-grid: {per_combo_10:.1f} s/combo on 10 stocks → "
        f"EXTRAPOLATED 200 combos × {len(n50_2y)} stocks ≈ "
        f"{extrap_200_full/3600:.1f} h"
    )

    print("\nmarkdown row:")
    print(
        f"| single eval {t_single*1000:.0f} ms | universe scan {t_scan:.0f} s | "
        f"2y×{len(n50_2y)} backtest {t_bt/60:.1f} min | "
        f"200-combo grid ≈{extrap_200_full/3600:.1f} h (extrapolated) |"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
