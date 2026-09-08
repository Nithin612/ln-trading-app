"""D1 / R1 counterfactual: does a GRADED RVOL confluence factor add edge? (read-only)

## The question (R1, blocked on D1)

R1 proposes adding VWAP/RVOL as confluence factors — a FROZEN-engine change. Two facts reshape it:

1. **VWAP is not testable** — every intraday OHLCV table is empty and VWAP is intrinsically
   intraday; it is excluded here.
2. **RVOL is already in the engine.** `app/analysis/indicators/volume.py::volume_factor` computes
   `curr_vol / avg_vol(20)` — that IS relative volume — and fires **+0.5 at ≥1.5×**. Worse, the
   scorer HARD-FORCES `name=="VOLUME"` to ±0.5 (confirmation only), so a graded raw score is
   impossible under that name. The existing binary version already attributes ≈ neutral.

⇒ The ONLY genuinely-new thing R1-RVOL can contribute over what ships today is a **graded**
(continuous) confirmation that (a) rewards *stronger* surges more than the binary step and (b) gives
*some* weight in the 1.0–1.5× band the binary ignores. This study tests exactly that increment.

## Method — read-only, no frozen edit

We monkeypatch the one seam `app.backtest.engine.run_all_factors` to append a research factor
`RVOL_STUDY` = rest_sign × m(RVOL), where rest_sign is the direction of the non-volume factors
(mirroring the scorer's `rest`) and m = clip((RVOL−1)/1, 0, 1) — so it CONFIRMS the prevailing
direction (never fires alone, never flips it), like the VOLUME factor's contract but graded.
Everything downstream (the frozen `score_from_factors`, classification, levels, honest-fill sim) is
untouched. ⚠ Adding a factor is NOT purely additive: the scorer normalizes by the weight of SCORING
factors, so a modest-magnitude confirmation DILUTES a strong consensus and can push a good signal
below 70% — the augmented set is NOT a superset of baseline. §2 reports both the added and dropped
sets. The DESIGN-AGNOSTIC verdict is §1: among signals we already mint, does RVOL-at-entry predict
outcome at all? If not, no factor design can extract edge from it.

Measured in R (pnl% / risk%). No recorded number is touched.

    uv run python scripts/rvol_factor_study.py --universe liquid --max-stocks 150
    uv run python scripts/rvol_factor_study.py --universe nifty50   # quick harness check
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.backtest.engine as engine_mod  # noqa: E402
import pandas as pd  # noqa: E402
from app.analysis.confluence import run_all_factors as _orig_run_all_factors  # noqa: E402
from app.analysis.types import FactorResult  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine, TradeRecord  # noqa: E402
from tp_geometry_study import _load_frames  # noqa: E402  (reuse the D5 loader — W2)

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_RVOL_WEIGHT = 10.0  # same weight class as the existing VOLUME factor
_AVG_PERIOD = 20     # mirrors volume_factor's lookback window
_TARGET_CLASSES = ("swing", "positional")


def _rvol(candles: pd.DataFrame) -> float:
    if len(candles) < _AVG_PERIOD + 1:
        return 0.0
    avg = float(candles["volume"].iloc[-_AVG_PERIOD - 1 : -1].mean())
    if avg <= 0:
        return 0.0
    return float(candles["volume"].iloc[-1]) / avg


def _augmented_run_all_factors(candles: pd.DataFrame, **kw: object) -> list[FactorResult]:
    """Frozen factors + a graded RVOL confirmation factor (research injection)."""
    factors = _orig_run_all_factors(candles, **kw)  # type: ignore[arg-type]
    rest = sum(f.weight * f.score for f in factors if f.name != "VOLUME")
    rest_sign = 1.0 if rest > 0 else (-1.0 if rest < 0 else 0.0)
    ratio = _rvol(candles)
    m = max(0.0, min(1.0, ratio - 1.0))  # 1.0×→0, 1.5×→0.5 (== binary), 2.0×→1.0 (graded beyond)
    score = rest_sign * m
    if score != 0.0:
        factors = [
            *factors,
            FactorResult("RVOL_STUDY", _RVOL_WEIGHT, score,
                         f"graded RVOL {ratio:.2f}× → {score:+.2f}", ["indicator", "volume"]),
        ]
    return factors


@dataclass
class Row:
    classification: str
    entry: float
    stop: float
    pnl_pct: float
    hit_target: bool
    hit_sl: bool
    rvol: float  # relative volume AT the decision bar (design-agnostic bucketing)


def _risk_pct(entry: float, stop: float) -> float:
    return abs(entry - stop) / entry * 100.0


def _row(t: TradeRecord, rvol: float) -> Row | None:
    if t.pnl_pct is None:
        return None
    if _risk_pct(t.entry_price, t.stop_loss) <= 0:
        return None
    return Row(t.classification, t.entry_price, t.stop_loss, float(t.pnl_pct),
               bool(t.hit_target), bool(t.hit_sl), rvol)


def _r(row: Row) -> float:
    return row.pnl_pct / _risk_pct(row.entry, row.stop)


def _run(frames: dict[str, pd.DataFrame]) -> dict[tuple[str, pd.Timestamp], Row]:
    engine = BacktestEngine(BacktestConfig())
    out: dict[tuple[str, pd.Timestamp], Row] = {}
    for stock, candles in frames.items():
        pos = {ts: i for i, ts in enumerate(candles.index)}
        for t in engine.run_single_stock(stock, candles):
            fill_idx = pos[t.entry_date]  # entry is candle N+1; decision bar is N = fill_idx-1
            rvol = _rvol(candles.iloc[:fill_idx])  # RVOL as-of the decision bar
            row = _row(t, rvol)
            if row is not None:
                out[(stock, t.entry_date)] = row
    return out


def _stats(rows: list[Row]) -> tuple[int, float, float, float, float]:
    """n, mean R, t-stat, win%, tp_hit%."""
    n = len(rows)
    if n == 0:
        return 0, 0.0, 0.0, 0.0, 0.0
    rs = [_r(r) for r in rows]
    mean = statistics.mean(rs)
    t = 0.0
    if n >= 2:
        sd = statistics.stdev(rs)
        t = mean / (sd / n**0.5) if sd > 0 else 0.0
    win = 100.0 * sum(1 for x in rs if x > 0) / n
    tp = 100.0 * sum(1 for r in rows if r.hit_target) / n
    return n, mean, t, win, tp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", choices=["nifty50", "liquid", "all"], default="liquid")
    ap.add_argument("--max-stocks", type=int, default=150)
    ap.add_argument("--min-rows", type=int, default=200)
    args = ap.parse_args()

    frames = asyncio.run(_load_frames(args.universe, args.min_rows, args.max_stocks))
    print(f"loaded {len(frames)} stocks ({args.universe}); baseline pass...", flush=True)
    baseline = _run(frames)

    print("augmented (RVOL) pass...", flush=True)
    engine_mod.__dict__["run_all_factors"] = _augmented_run_all_factors
    try:
        augmented = _run(frames)
    finally:
        engine_mod.__dict__["run_all_factors"] = _orig_run_all_factors

    # Partition. NOTE: adding a factor is NOT purely additive — the scorer normalizes by the weight
    # of SCORING factors, so a modest-magnitude confirmation dilutes a strong consensus and can push
    # a good signal BELOW 70%. So A is not a superset of B; report both the added and dropped sets.
    b_keys, a_keys = set(baseline), set(augmented)
    added = a_keys - b_keys           # RVOL newly admitted (dilution lifted a weak signal over 70)
    dropped = b_keys - a_keys         # RVOL diluted a baseline signal below 70
    shared = b_keys & a_keys
    moved = [k for k in shared
             if (baseline[k].entry, baseline[k].stop) != (augmented[k].entry, augmented[k].stop)]

    def sub(
        rows: dict[tuple[str, pd.Timestamp], Row], keys: set[tuple[str, pd.Timestamp]]
    ) -> list[Row]:
        return [rows[k] for k in keys if rows[k].classification in _TARGET_CLASSES]

    lines: list[str] = []
    emit = lines.append
    today = datetime.now(UTC).date().isoformat()
    emit(f"# RVOL-factor counterfactual (D1 / R1) — {today}")
    emit("")
    emit(f"Universe **{args.universe}** ({len(frames)} stocks) · window 2023-07-03 → today "
         f"(CA-clean) · min_confidence 70. **No frozen edit / no recorded number.**")
    emit("")
    emit("**VWAP is excluded — not backtestable (no intraday data).** The existing binary VOLUME "
         "factor already encodes RVOL at 1.5×; only the GRADED increment over it is in question.")
    emit("")

    # §1 — design-agnostic: does RVOL-at-entry predict outcome among signals we ALREADY mint?
    emit("## 1. Does RVOL-at-entry predict outcome? (baseline signals, design-agnostic)")
    emit("")
    emit("If RVOL carries no outcome information here, NO factor design can extract edge from it. "
         "Buckets by relative volume at the decision bar.")
    emit("")
    emit("| RVOL bucket | n | mean R | t | win% |")
    emit("|---|--:|--:|--:|--:|")
    buckets = [("<1.0×", 0.0, 1.0), ("1.0–1.5×", 1.0, 1.5),
               ("1.5–2.0×", 1.5, 2.0), ("≥2.0×", 2.0, 1e9)]
    base_rows = sub(baseline, b_keys)
    for label, lo, hi in buckets:
        n, mean, t, win, _tp = _stats([r for r in base_rows if lo <= r.rvol < hi])
        emit(f"| {label} | {n} | {mean:+.3f} | {t:+.2f} | {win:.0f} |")
    emit("")

    # ── 2. The injected-factor effect (dilution included) ──
    emit("## 2. Effect of injecting a graded RVOL factor (weight 10)")
    emit("")
    emit(f"Adding the factor is NOT additive: baseline minted **{len(baseline)}**, augmented "
         f"**{len(augmented)}** — RVOL **added {len(added)}** (lifted a weak signal over 70) and "
         f"**dropped {len(dropped)}** (diluted a strong one under 70); shared **{len(shared)}** "
         f"(entry/stop moved: {len(moved)}).")
    emit("")
    emit("| set | n | mean R | t | win% | tp_hit% |")
    emit("|---|--:|--:|--:|--:|--:|")
    for label, src, keys in [
        ("baseline book B", baseline, b_keys),
        ("augmented book A", augmented, a_keys),
        ("RVOL added (A∖B)", augmented, added),
        ("RVOL dropped (B∖A)", baseline, dropped),
    ]:
        n, mean, t, win, tp = _stats(sub(src, keys))
        emit(f"| {label} | {n} | {mean:+.3f} | {t:+.2f} | {win:.0f} | {tp:.0f} |")
    emit("")

    emit("---")
    emit("")
    emit("**Reading it.** §1 is decisive and design-free: if RVOL buckets show no monotonic, "
         "significant (t≈3.6) improvement in mean R, RVOL carries no outcome signal and no factor "
         "design will help — the existing binary VOLUME factor already captures what little it is "
         "worth. §2 shows the real mechanics of adding it to THIS scorer: normalization means a "
         "graded confirmation dilutes strong signals and re-shuffles the minted set, so 'add a "
         "factor' is not free. A frozen spec change (D1 sign-off) is earned only if §1 shows a "
         "real, bar-clearing RVOL edge AND §2's augmented book beats baseline. VWAP stays separate "
         "(forward-only).")

    out = _OUT_DIR / f"rvol-factor-study-{today}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n→ wrote {out}")


if __name__ == "__main__":
    main()
