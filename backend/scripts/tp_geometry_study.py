"""D5 counterfactual: does a different TAKE-PROFIT geometry beat the frozen one?

## The question (D5, `compute_levels`)

For **swing** and **positional** signals the frozen engine pairs a STRUCTURAL stop
(swing low / EMA20) with an ABSOLUTE-% target (swing +6%, positional +15%). R:R is
therefore an accident of how far the structural stop happens to sit — "94 of 295 swing
signals have R:R < 1 by construction". Scalp/intraday are geometry-invariant (their target
is already derived from the stop), so they are reported but not the subject.

## Why this is safe to run against the frozen engine

`BacktestConfig.tp_rule` is a **sanctioned Phase-2 freeze-extension**: `tp_rule=None` is
byte-identical to the frozen engine (proven by the unchanged oracle fixtures), and a non-None
rule overrides ONLY the take-profit via `app.backtest.tp_rules.tp_from_template`. SL, entries,
minting and the honest-fill exit walk are untouched. So this study changes **no recorded
number** and needs no engine edit — it measures a counterfactual.

## Design — a PAIRED test, factors computed ONCE

The minted trade SET is identical across geometries (a target never changes whether a signal
is minted, its stop, or its size). So we run the frozen `run_single_stock` ONCE per stock
(baseline), recover each signal's decision index, then re-run only the honest-fill exit walk
(`_simulate_trade`) for each candidate target — the expensive factor computation happens once.
Every variant therefore shares the same (stock, entry_date) signals; we pair on that key and
compute per-signal ΔR = candidate_R − baseline_R. Paired ⇒ entry quality is controlled for.

## The trap this is built to catch

The obvious "raise R:R" fix is the exact mechanism the R:R≥1 gate was REVERTED for (2026-09-03):
R:R<1 is a proxy for a WIDE stop, wide stops were the profitable cohort, and a nearer target is
mechanically easier to hit. So we segment ΔR by **stop-width cohort** — a candidate that only
wins by shifting the cohort mix, or that loses inside the wide-stop cohort, is the trap, not a fix.

## Measured in R

R = pnl_pct / risk_pct, risk_pct = |entry − SL| / entry × 100. NOTE: a flat round-trip cost
CANCELS in the paired ΔR because a candidate and its baseline share the identical stop (identical
risk%), so cost cannot change the geometry ranking — reported once to make that explicit, not
swept per level. Absolute expectancy stays a GROSS upper bound (the backtest models no costs).

    uv run python scripts/tp_geometry_study.py --universe liquid --max-stocks 250
    uv run python scripts/tp_geometry_study.py --universe all
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from app.backtest.engine import BacktestConfig, BacktestEngine, TradeRecord  # noqa: E402
from app.backtest.tp_rules import tp_from_template  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

# CA-clean window: the pre-COVID backfill is CA-UNADJUSTED and would manufacture fake target
# hits on split/bonus gaps, so this study stays inside the corpus the current stats rest on.
_CLEAN_SINCE = datetime(2023, 7, 3, tzinfo=UTC)

# Candidate geometries. None = frozen canon. rr = target at entry ± ratio × risk (constant R:R).
_RR_RATIOS = [1.0, 1.5, 2.0, 2.5, 3.0]
_ALL_NAMES = ["baseline_frozen"] + [f"rr_{r:.1f}" for r in _RR_RATIOS]

# Stop-width cohorts by risk_pct = |entry − SL| / entry × 100.
_COHORTS: list[tuple[str, float, float]] = [
    ("tight <2%", 0.0, 2.0),
    ("mid 2-5%", 2.0, 5.0),
    ("wide >5%", 5.0, 1e9),
]
_TARGET_CLASSES = ("swing", "positional")  # geometry-relevant; scalp/intraday are invariant


@dataclass
class Row:
    classification: str
    direction: str
    risk_pct: float
    pnl_pct: float
    hit_target: bool
    hit_sl: bool


async def _load_frames(
    universe: str, min_rows: int, max_stocks: int | None
) -> dict[str, pd.DataFrame]:
    """{symbol: OHLCV frame} for the chosen universe, since the CA-clean cutoff."""
    if universe == "nifty50":
        where = "AND s.is_nifty50"
    else:
        where = ""
    async with AsyncSessionFactory() as db:
        # Pick the symbol set first (so 'liquid' / max_stocks rank by median daily traded value).
        pick = await db.execute(
            text(
                f"SELECT s.symbol, COUNT(*) n, "
                f"       percentile_cont(0.5) WITHIN GROUP (ORDER BY o.close*o.volume) mdv "
                f"FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                f"WHERE s.is_active {where} AND o.time >= :since "
                f"GROUP BY s.symbol HAVING COUNT(*) >= :min_rows "
                f"ORDER BY mdv DESC"
            ),
            {"since": _CLEAN_SINCE, "min_rows": min_rows},
        )
        picked = pick.fetchall()
        if universe == "liquid":
            picked = [p for p in picked if p.mdv is not None and float(p.mdv) >= 5e7]  # ≥ ₹5cr/day
        if max_stocks is not None:
            picked = picked[:max_stocks]
        symbols = [p.symbol for p in picked]
        if not symbols:
            return {}
        rows = (
            await db.execute(
                text(
                    "SELECT s.symbol, o.time, o.open, o.high, o.low, o.close, o.volume "
                    "FROM ohlcv_1d o JOIN stocks s ON s.id=o.stock_id "
                    "WHERE s.symbol = ANY(:syms) AND o.time >= :since "
                    "ORDER BY s.symbol, o.time"
                ),
                {"syms": symbols, "since": _CLEAN_SINCE},
            )
        ).fetchall()

    by_symbol: dict[str, list[Any]] = defaultdict(list)
    for r in rows:
        by_symbol[r.symbol].append(r)
    frames: dict[str, pd.DataFrame] = {}
    for sym, rs in by_symbol.items():
        frames[sym] = pd.DataFrame(
            {
                "time": [r.time for r in rs],
                "open": [float(r.open) for r in rs],
                "high": [float(r.high) for r in rs],
                "low": [float(r.low) for r in rs],
                "close": [float(r.close) for r in rs],
                "volume": [int(r.volume) for r in rs],
            }
        ).set_index("time")
    return frames


def _risk_pct(entry: float, stop: float) -> float:
    return abs(entry - stop) / entry * 100.0


def _row(t: TradeRecord) -> Row | None:
    if t.pnl_pct is None:
        return None
    rp = _risk_pct(t.entry_price, t.stop_loss)
    if rp <= 0:
        return None
    return Row(
        t.classification, t.direction, rp, float(t.pnl_pct), bool(t.hit_target), bool(t.hit_sl)
    )


def _r_of(r: Row) -> float:
    return r.pnl_pct / r.risk_pct


def _cohort(risk_pct: float) -> str:
    for name, lo, hi in _COHORTS:
        if lo <= risk_pct < hi:
            return name
    return "?"


def _mean_t(xs: list[float]) -> tuple[float, float, float, int]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0, 0
    mean, med = statistics.mean(xs), statistics.median(xs)
    if n < 2:
        return mean, med, 0.0, n
    sd = statistics.stdev(xs)
    return mean, med, (mean / (sd / n**0.5) if sd > 0 else 0.0), n


def _f(x: float, p: int = 3) -> str:
    return f"{x:+.{p}f}"


def _collect(
    frames: dict[str, pd.DataFrame],
    *,
    keep: Callable[[TradeRecord], bool] | None = None,
    records: dict[tuple[str, pd.Timestamp], TradeRecord] | None = None,
) -> dict[str, dict[tuple[str, pd.Timestamp], Row]]:
    """Factors ONCE per stock (baseline run), then cheap exit-only re-sim per candidate.

    ⭐ `keep` (queue item 6) filters at the TradeRecord, which is where item 4's delete
    treatment lives. Default `None` = the original behaviour exactly, so the published D5 run
    still reproduces. ⭐⭐ **Filtering on the BASELINE record is sufficient for every variant**:
    `is_unfillable` reads only `entry_price` and `stop_loss`, and each variant is an exit-only
    re-sim off the same fill candle and the same stop — only the target moves. So a key is
    unfillable for all variants or for none, and filtering once cannot desynchronise the pairing.

    `records` is an optional sink for the baseline TradeRecords, so a caller can compute the
    delete treatment itself rather than this function imposing a definition of R (M60: three
    are live).
    """
    engine = BacktestEngine(BacktestConfig())  # tp_rule=None → frozen canon
    variants: dict[str, dict[tuple[str, pd.Timestamp], Row]] = {n: {} for n in _ALL_NAMES}
    for stock, candles in frames.items():
        pos = {ts: i for i, ts in enumerate(candles.index)}  # O(1) fill-index recovery
        for t in engine.run_single_stock(stock, candles):
            key = (stock, t.entry_date)
            if keep is not None and not keep(t):
                continue
            if records is not None:
                records[key] = t
            base_row = _row(t)
            if base_row is None:
                continue
            variants["baseline_frozen"][key] = base_row
            sidx = pos[t.entry_date] - 1  # entry_date is candle N+1; decision was N
            entry_d, stop_d = Decimal(str(t.entry_price)), Decimal(str(t.stop_loss))
            for ratio, name in zip(_RR_RATIOS, _ALL_NAMES[1:], strict=True):
                new_tp = tp_from_template(
                    {"kind": "rr", "ratio": ratio}, t.direction, entry_d, stop_d
                )
                rec = engine._simulate_trade(
                    stock=stock, signal_candle_idx=sidx, direction=t.direction,
                    classification=t.classification, confidence_pct=t.confidence_pct,
                    stop_loss=t.stop_loss, take_profit=float(new_tp), qty=t.qty, candles=candles,
                )
                r = _row(rec) if rec is not None else None
                if r is not None:
                    variants[name][key] = r
    return variants


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", choices=["nifty50", "liquid", "all"], default="liquid")
    ap.add_argument("--max-stocks", type=int, default=250)
    ap.add_argument("--min-rows", type=int, default=200)
    args = ap.parse_args()

    frames = asyncio.run(_load_frames(args.universe, args.min_rows, args.max_stocks))
    print(f"loaded {len(frames)} stocks ({args.universe}); running backtests...", flush=True)
    variants = _collect(frames)

    baseline = variants["baseline_frozen"]
    base_keys = {k for k, r in baseline.items() if r.classification in _TARGET_CLASSES}

    lines: list[str] = []
    emit = lines.append
    today = datetime.now(UTC).date().isoformat()
    emit(f"# TP-geometry counterfactual (D5) — {today}")
    emit("")
    emit(f"Universe **{args.universe}** ({len(frames)} stocks, ≤{args.max_stocks}) · window "
      f"**{_CLEAN_SINCE.date()} → today** (CA-clean) · min_confidence 70 · frozen entries+stops, "
      f"target varied via the sanctioned `tp_rule` freeze-extension (baseline `None` = frozen).")
    emit("")
    emit(f"**{len(base_keys)} swing+positional signals** (scalp/intraday geometry-invariant, "
      f"excluded from the verdict). Paired on `(stock, entry_date)` — identical entry set, "
      f"only the exit differs. **R** = pnl% / risk%; a flat cost cancels in the paired ΔR.")
    emit("")

    emit("## 1. Expectancy per geometry (swing+positional, GROSS)")
    emit("")
    emit("| geometry | n | mean R | median R | t | win% | tp_hit% | sl_hit% | sumR |")
    emit("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for name in _ALL_NAMES:
        v = variants[name]
        rs = [v[k] for k in base_keys if k in v]
        rvals = [_r_of(r) for r in rs]
        mean, med, t, n = _mean_t(rvals)
        win = 100.0 * sum(1 for x in rvals if x > 0) / n if n else 0.0
        tp = 100.0 * sum(1 for r in rs if r.hit_target) / n if n else 0.0
        sl = 100.0 * sum(1 for r in rs if r.hit_sl) / n if n else 0.0
        emit(f"| {name} | {n} | {_f(mean)} | {_f(med)} | {t:+.2f} | {win:.0f} | {tp:.0f} | "
          f"{sl:.0f} | {_f(sum(rvals), 1)} |")
    emit("")

    emit("## 2. Paired ΔR vs frozen baseline — overall and by stop-width cohort")
    emit("")
    emit("ΔR = candidate_R − baseline_R on the SAME signal. A candidate is a real fix only if ΔR>0 "
      "**and** it does not come apart inside the wide-stop cohort (the R:R-reversal trap).")
    emit("")
    cnames = [c[0] for c in _COHORTS]
    emit("| geometry | overall ΔR (t, n) | " + " | ".join(f"{c} (n)" for c in cnames) + " |")
    emit("|---" * (2 + len(cnames)) + "|")
    for name in _ALL_NAMES[1:]:
        v = variants[name]
        overall: list[float] = []
        byc: dict[str, list[float]] = defaultdict(list)
        for k in base_keys:
            if k not in v:
                continue
            d = _r_of(v[k]) - _r_of(baseline[k])
            overall.append(d)
            byc[_cohort(baseline[k].risk_pct)].append(d)
        mean, _m, t, n = _mean_t(overall)
        cells = []
        for c in cnames:
            cm, _, _, cn = _mean_t(byc[c])
            cells.append(f"{_f(cm)} ({cn})")
        emit(f"| {name} | {_f(mean)} (t={t:+.2f}, n={n}) | " + " | ".join(cells) + " |")
    emit("")

    emit("## 3. Paired ΔR by class (GROSS)")
    emit("")
    emit("| geometry | swing ΔR (t, n) | positional ΔR (t, n) |")
    emit("|---|--:|--:|")
    for name in _ALL_NAMES[1:]:
        v = variants[name]
        bycls: dict[str, list[float]] = defaultdict(list)
        for k in base_keys:
            if k in v:
                bycls[baseline[k].classification].append(_r_of(v[k]) - _r_of(baseline[k]))
        sm, _, st, sn = _mean_t(bycls["swing"])
        pm, _, pt, pn = _mean_t(bycls["positional"])
        emit(f"| {name} | {_f(sm)} (t={st:+.2f}, {sn}) | {_f(pm)} (t={pt:+.2f}, {pn}) |")
    emit("")

    emit("---")
    emit("")
    emit("**Reading it.** Promotion bar for a real edge is t ≈ 3.6 (deflated-Sharpe, flat in n); "
      "this answers the narrower question of whether geometry moves expectancy at all, and where. "
      "A ~zero or negative overall ΔR, or a positive that inverts in the wide-stop cohort, says "
      "the frozen geometry is not the lever (tourniquet stays). A robust positive ΔR across "
      "cohorts is the case to take to a §8 spec change.")

    out = _OUT_DIR / f"tp-geometry-study-{today}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n→ wrote {out}")


if __name__ == "__main__":
    main()
