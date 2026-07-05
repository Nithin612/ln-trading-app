"""Adjudication evidence pack #2 — drifts F/G/H (Phase-1 exit-gate review).

Three places where BOTH engines drift from SIGNAL_ENGINE.md, found by the
quant-verifier at the Phase-1 gate (phase-01 report §Exit gate). Like the
A–E round, this script measures backtest impact WITHOUT touching frozen
code — variants are runtime monkeypatches and die after the user's ruling.

  F  ATR>3% sizing      spec §4: volatile regime → reduce position size 25%
                        (unimplemented in both engines; atr_pct_of_price is
                        dead code). Decisions unchanged — impact is RUPEE
                        P&L, so it is post-processed from the BASELINE
                        trade list, not re-run.
  G  star gap           spec §2.2: Morning/Evening Star require the star to
                        GAP beyond the first candle's body; both engines
                        omit the gap. Variant = real-body gap required.
  H  weight semantics   spec §3 table sums group weights to 105; code gives
                        every sub-factor its full group weight (max fired
                        weight 150+10). H1 = pairs share the group weight
                        (EMA 7.5+7.5, RSI 5+5, MACD 5+5). H2 = H1 + BBANDS
                        excluded (it has NO row in §3's table).

Corpus is pinned to the bench-day anchor (2024-06-04T12:00Z) so BASELINE
must reproduce the 807-trade parity oracle exactly — a cross-check that the
harness runs the same engine the fixtures pin.

Run (one variant per process; they parallelise cleanly):
  uv run python scripts/adjudication_experiments_fgh.py BASELINE <outdir>
  uv run python scripts/adjudication_experiments_fgh.py G        <outdir>
  uv run python scripts/adjudication_experiments_fgh.py H1       <outdir>
  uv run python scripts/adjudication_experiments_fgh.py H2       <outdir>
  uv run python scripts/adjudication_experiments_fgh.py GH1      <outdir>
  uv run python scripts/adjudication_experiments_fgh.py F        <outdir>  # after BASELINE
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import time
import unittest.mock as um
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.analysis.indicators.bbands import atr_pct_of_price  # noqa: E402
from app.analysis.types import FactorResult  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult  # noqa: E402
from bench_baseline import load_universe  # noqa: E402  (same scripts dir)

# Bench-day anchor — the corpus definition under which the parity oracle
# recorded 807 trades (docs/PERFORMANCE.md 2026-07-05 note).
ANCHOR = datetime(2024, 6, 4, 12, 0, tzinfo=UTC)

CFG = BacktestConfig(
    timeframe="1d", universe="NIFTY50",
    capital=Decimal("500000"), risk_pct=Decimal("2"), min_confidence=70,
)

VOLATILE_ATR_PCT = 3.0   # spec §4 threshold
SIZE_REDUCTION = 0.75    # spec §4: "reduce position size 25%"


# ── G: require the real-body gap on Morning/Evening Star ────────────────────

STAR_COUNTS = {"detected": 0, "gap_rejected": 0}


def make_gapped_star_detector():  # noqa: ANN201
    import app.analysis.patterns.multi as multi_mod

    original = multi_mod.detect_morning_evening_star

    def gapped(candles):  # noqa: ANN001, ANN202
        r = original(candles)
        if not r.detected:
            return r
        STAR_COUNTS["detected"] += 1
        first, star = candles.iloc[-3], candles.iloc[-2]
        star_top = max(float(star["open"]), float(star["close"]))
        star_bot = min(float(star["open"]), float(star["close"]))
        first_top = max(float(first["open"]), float(first["close"]))
        first_bot = min(float(first["open"]), float(first["close"]))
        # Real-body gap (classic definition): the star's body sits entirely
        # beyond the first candle's body — below it for Morning (score>0),
        # above it for Evening (score<0).
        gap_ok = star_top < first_bot if r.score > 0 else star_bot > first_top
        if gap_ok:
            return r
        STAR_COUNTS["gap_rejected"] += 1
        return type(r)(False, 0.0, "star without body gap [G variant]", "STAR")

    return gapped


def make_counting_star_detector():  # noqa: ANN201
    """BASELINE instrumentation only — counts fires, changes nothing."""
    import app.analysis.patterns.multi as multi_mod

    original = multi_mod.detect_morning_evening_star

    def counting(candles):  # noqa: ANN001, ANN202
        r = original(candles)
        if r.detected:
            STAR_COUNTS["detected"] += 1
        return r

    return counting


# ── H: sub-factors share the §3 group weight ────────────────────────────────

H1_WEIGHTS = {
    "EMA_CROSS": 7.5, "PRICE_VS_EMA": 7.5,     # §3 "EMA structure" = 15
    "RSI_LEVEL": 5.0, "RSI_DIVERGENCE": 5.0,   # §3 "RSI (level + divergence)" = 10
    "MACD_CROSS": 5.0, "MACD_HISTOGRAM": 5.0,  # §3 "MACD (cross + histogram)" = 10
}


def make_reweighting_scorer(weights: dict[str, float]):  # noqa: ANN201
    from app.analysis.confluence import score_from_factors as real_scorer

    def scorer(factors, candles, min_confidence=70):  # noqa: ANN001, ANN202
        reweighted = [
            FactorResult(f.name, weights[f.name], f.score, f.explanation, f.tags)
            if f.name in weights
            else f
            for f in factors
        ]
        return real_scorer(reweighted, candles, min_confidence)

    return scorer


# ── F: rupee-P&L post-processing of the BASELINE trade list ─────────────────

def run_f_postprocess(outdir: Path, frames: dict[str, pd.DataFrame]) -> int:
    baseline_path = outdir / "trades_BASELINE.json"
    if not baseline_path.exists():
        print("F needs trades_BASELINE.json — run the BASELINE variant first")
        return 2
    trades = json.loads(baseline_path.read_text())

    volatile = dropped = located = 0
    rupee_base = rupee_f = 0.0
    risk_cut_total = 0.0
    atr_fail = 0
    for t in trades:
        frame = frames.get(t["stock"])
        if frame is None:
            atr_fail += 1
            continue
        try:
            fill_idx = frame.index.get_loc(pd.Timestamp(t["entry_date"]))
        except KeyError:
            atr_fail += 1
            continue
        located += 1
        # Decision window exactly as the engine saw it: last ≤300 completed
        # candles ENDING at the decision candle (fill_idx - 1).
        window = frame.iloc[max(0, fill_idx - 300) : fill_idx]
        atr_pct = atr_pct_of_price(window)
        qty = t["qty"]
        rupee = t["pnl_pct"] / 100.0 * t["entry_price"] * qty
        rupee_base += rupee
        if atr_pct > VOLATILE_ATR_PCT:
            volatile += 1
            qty_f = math.floor(qty * SIZE_REDUCTION)
            risk_cut_total += (qty - qty_f) * abs(t["entry_price"] - t["stop_loss"])
            if qty_f == 0:
                dropped += 1
            rupee_f += t["pnl_pct"] / 100.0 * t["entry_price"] * qty_f
        else:
            rupee_f += rupee

    print(f"F — §4 ATR>{VOLATILE_ATR_PCT:.0f}% → qty×{SIZE_REDUCTION} "
          "(baseline trade list, decisions unchanged)")
    print(f"  trades located: {located}/{len(trades)}  (index misses: {atr_fail})")
    print(f"  volatile-regime trades: {volatile} ({100.0*volatile/max(located,1):.1f}%)")
    print(f"  trades dropped by reduction (qty→0): {dropped}")
    print(f"  rupee P&L  baseline: ₹{rupee_base:,.0f}   with-F: ₹{rupee_f:,.0f}   "
          f"Δ: ₹{rupee_f-rupee_base:,.0f}")
    print(f"  total risk removed from volatile trades: ₹{risk_cut_total:,.0f}")
    print("  NOTE: win%/sharpe/maxDD are pnl_pct-based and unaffected by qty — "
          "F is purely a capital-at-risk decision.")
    return 0


# ── harness ──────────────────────────────────────────────────────────────────

def fmt_row(name: str, r: BacktestResult, seconds: float) -> str:
    return (
        f"| {name:<18} | {r.total_trades:>6} | {r.win_rate_pct:>5.1f} | "
        f"{r.avg_pnl_pct:>7.2f} | {r.total_pnl_pct:>8.1f} | {r.sharpe:>6.2f} | "
        f"{r.max_drawdown_pct:>6.1f} | {seconds/60:>5.1f}m |"
    )


def dump_trades(outdir: Path, name: str, r: BacktestResult) -> None:
    rows = [
        {
            "stock": t.stock, "direction": t.direction,
            "classification": t.classification, "confidence_pct": t.confidence_pct,
            "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
            "stop_loss": t.stop_loss, "take_profit": t.take_profit, "qty": t.qty,
            "exit_price": t.exit_price, "pnl_pct": t.pnl_pct,
            "hit_sl": t.hit_sl, "hit_target": t.hit_target,
        }
        for t in r.trades
    ]
    (outdir / f"trades_{name}.json").write_text(json.dumps(rows))


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"BASELINE", "G", "H1", "H2", "GH1", "F"}:
        print(__doc__)
        return 2
    variant, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)

    frames = asyncio.run(load_universe(True, min_rows=200, since=ANCHOR))
    if not frames:
        print("NO DATA — run scripts/backfill_eod.py first")
        return 2
    print(f"[{variant}] corpus: {len(frames)} Nifty50 stocks, "
          f"{sum(len(f) for f in frames.values())} rows (anchor {ANCHOR.date()})", flush=True)

    if variant == "F":
        return run_f_postprocess(outdir, frames)

    patches: list = []
    import app.analysis.confluence as conf_mod
    import app.backtest.engine as engine_mod

    if variant == "BASELINE":
        patches.append(um.patch.object(
            conf_mod, "detect_morning_evening_star", make_counting_star_detector()))
    if variant in {"G", "GH1"}:
        patches.append(um.patch.object(
            conf_mod, "detect_morning_evening_star", make_gapped_star_detector()))
    if variant in {"H1", "GH1"}:
        patches.append(um.patch.object(
            engine_mod, "score_from_factors", make_reweighting_scorer(H1_WEIGHTS)))
    if variant == "H2":
        h2 = dict(H1_WEIGHTS)
        h2["BBANDS"] = 0.0  # weight 0 ⇒ excluded from numerator AND denominator
        patches.append(um.patch.object(
            engine_mod, "score_from_factors", make_reweighting_scorer(h2)))

    t0 = time.perf_counter()
    import contextlib

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = BacktestEngine(CFG).run(frames)
    elapsed = time.perf_counter() - t0

    print("| variant            | trades | win%  | avgPnL% | totPnL%  | sharpe | maxDD% | time  |")
    print(fmt_row(variant, result, elapsed), flush=True)
    if STAR_COUNTS["detected"] or STAR_COUNTS["gap_rejected"]:
        print(f"[{variant}] star windows detected={STAR_COUNTS['detected']} "
              f"gap_rejected={STAR_COUNTS['gap_rejected']}")
    dump_trades(outdir, variant, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
