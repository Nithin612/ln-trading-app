"""Read-only probe: what does the confluence engine actually select, and on what?

Answers three questions the daily reports cannot, because they only see the
signals that were MINTED, never the panels that were scored and discarded:

  1. **Participation** — how often does each of the 14 (+1) factors actually
     score a non-zero value on a real daily window? A factor that abstains
     contributes nothing AND leaves the confidence denominator (SIGNAL_ENGINE.md
     §3 normalizes by the weight of factors that scored), so an abstainer is
     invisible in the output but decisive in the arithmetic.
  2. **Selectivity** — what share of stock-days clears the >=70% gate, and how
     many factors is a passing signal actually resting on?
  3. **Level geometry** — for the signals that pass, what stop width, R:R and
     notional does `compute_levels` + `compute_quantity` produce, and how many
     die at the class SL cap before they are ever seen?

SELECT-only: no writes, no DB mutation, frozen engine neither edited nor
subclassed (it is imported and called exactly as the nightly job calls it).

Run:  cd backend && uv run python scripts/engine_selectivity_probe.py
      [--stocks 250] [--dates 30] [--stride 25]
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import statistics
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

# Runnable from any cwd: put backend/ (the `app` package root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.confluence import run_all_factors, score_from_factors
from app.analysis.indicators.adx import adx_is_strong, adx_is_weak
from app.analysis.risk import compute_quantity, volatility_adjusted_qty
from app.analysis.structure.dow import (
    _find_swing_highs,
    _find_swing_lows,
    dow_trend_factor,
    swing_levels,
)
from app.db.session import AsyncSessionFactory
from app.signals.classifier import classify_signal
from app.signals.risk_guards import safe_levels

WINDOW = 300  # the window canon: last 300 completed candles
CAPITAL = Decimal("100000")  # the LIVE account figure, not the sampling scale
RISK_PCT = Decimal("2.0")


def _pct(values: list[float], q: float) -> float:
    vals = sorted(values)
    return vals[int(q * (len(vals) - 1))] if vals else float("nan")


def dow_trend_reachability() -> None:
    """Can `dow_trend_factor` EVER score on a 1d window?

    The daily call is `dow_trend_factor(candles, lookback=20, swing_n=5)`. Inside a
    20-bar window a pivot can only sit at index 5..14, and any two of those differ by
    at most 9 < 2*5+1 = 11, so their pivot windows overlap and both can be the max
    only on an exact float tie. The function needs TWO swing highs AND TWO swing lows.
    A synthetic staircase uptrend (higher highs and higher lows by construction) is the
    cleanest demonstration.
    """
    n = WINDOW
    close = np.linspace(100, 200, n) + np.sin(np.arange(n) / 3.0) * 3
    df = pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.5,
            "low": close - 1.5,
            "close": close,
            "volume": [100_000] * n,
        }
    )
    win = df.iloc[-20:]
    highs = _find_swing_highs(win["high"].astype(float).reset_index(drop=True), 5)
    lows = _find_swing_lows(win["low"].astype(float).reset_index(drop=True), 5)
    daily = dow_trend_factor(df, lookback=20, swing_n=5)
    intra = dow_trend_factor(df, lookback=20, swing_n=3)
    print("== DOW_TREND reachability (synthetic textbook uptrend) ==")
    print(f"  pivots in the 20-bar window at n=5: highs={highs} lows={lows}")
    print(f"  daily call    (lookback=20, swing_n=5): score {daily.score}  '{daily.explanation}'")
    print(f"  intraday call (lookback=20, swing_n=3): score {intra.score}  '{intra.explanation}'")


async def load_frames(n_stocks: int) -> dict[int, pd.DataFrame]:
    async with AsyncSessionFactory() as db:
        ids = [
            r[0]
            for r in (
                await db.execute(
                    text(
                        """
                        SELECT stock_id FROM ohlcv_1d
                        WHERE time > now() - interval '180 days'
                        GROUP BY stock_id HAVING count(*) > 100
                        ORDER BY percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY close * volume) DESC
                        LIMIT :n
                        """
                    ),
                    {"n": n_stocks},
                )
            ).all()
        ]
        bars = (
            await db.execute(
                text(
                    """
                    SELECT stock_id, time, open, high, low, close, volume FROM ohlcv_1d
                    WHERE stock_id = ANY(:i) AND is_complete
                      AND time > now() - interval '1200 days'
                    ORDER BY stock_id, time
                    """
                ),
                {"i": ids},
            )
        ).all()
    grouped: dict[int, list[Any]] = collections.defaultdict(list)
    for row in bars:
        grouped[row[0]].append(row)
    frames: dict[int, pd.DataFrame] = {}
    for sid, rows in grouped.items():
        if len(rows) < WINDOW + 30:
            continue
        frames[sid] = pd.DataFrame(
            {
                "open": [float(r[2]) for r in rows],
                "high": [float(r[3]) for r in rows],
                "low": [float(r[4]) for r in rows],
                "close": [float(r[5]) for r in rows],
                "volume": [r[6] for r in rows],
            },
            index=[r[1] for r in rows],
        )
    return frames


async def main(n_stocks: int, n_dates: int, stride: int) -> None:  # noqa: C901 — one linear measurement pass; splitting it would hide the sequence
    dow_trend_reachability()
    frames = await load_frames(n_stocks)
    print(f"\nstocks with usable history: {len(frames)}")

    seen = passed = dow_nonzero = 0
    participation: collections.Counter[str] = collections.Counter()
    weights: dict[str, float] = {}
    scoring_count: collections.Counter[int] = collections.Counter()
    denominators: list[float] = []
    confidences: list[float] = []
    pass_factors: collections.Counter[str] = collections.Counter()
    pass_n: list[float] = []
    pass_den: list[float] = []
    sl_pct: list[float] = []
    rr: list[float] = []
    notional: list[float] = []
    level_reject = 0
    dirs: collections.Counter[str] = collections.Counter()
    classes: collections.Counter[str] = collections.Counter()
    pivot_dist: list[float] = []
    adx_adjust: collections.Counter[str] = collections.Counter()

    for frame in frames.values():
        length = len(frame)
        for offset in range(0, n_dates * stride, stride):
            end = length - offset
            if end < WINDOW:
                break
            window = frame.iloc[end - WINDOW : end]
            seen += 1
            try:
                factors = run_all_factors(window, "1d")
            except Exception:  # noqa: BLE001 — a bad window must not stop the probe
                continue
            for f in factors:
                weights[f.name] = f.weight
                if f.score != 0.0:
                    participation[f.name] += 1
                    if f.name == "DOW_TREND":
                        dow_nonzero += 1
            if adx_is_weak(window):
                adx_adjust["weak: threshold 75"] += 1
            elif adx_is_strong(window):
                adx_adjust["strong: threshold 65"] += 1
            else:
                adx_adjust["normal: threshold 70"] += 1
            scored = [f for f in factors if f.score != 0.0]
            scoring_count[len(scored)] += 1
            denominator = sum(f.weight for f in scored)
            denominators.append(denominator)
            if denominator:
                weighted = sum(f.weight * f.score for f in factors)
                confidences.append(int(abs(weighted / denominator) * 100))

            entry = Decimal(str(window["close"].iloc[-1]))
            low, high = swing_levels(window)
            if low is not None:
                pivot_dist.append(float((entry - low) / entry * 100))

            result = score_from_factors(factors, window, 70)
            if result is None:
                continue
            passed += 1
            pass_n.append(len(scored))
            pass_den.append(denominator)
            dirs[result.direction] += 1
            for f in scored:
                pass_factors[f.name] += 1
            classification = classify_signal("1d", result.factors, result.is_multibagger)
            classes[classification] += 1
            levels = safe_levels(result.direction, classification, entry, low, high, None)
            if levels is None:
                level_reject += 1
                continue
            stop, target = levels
            sl_pct.append(float(abs(entry - stop) / entry * 100))
            risk = abs(entry - stop)
            if risk > 0:  # safe_levels already rejects stop == entry
                rr.append(float(abs(target - entry) / risk))
            qty = volatility_adjusted_qty(
                compute_quantity(CAPITAL, RISK_PCT, entry, stop), window
            )
            notional.append(float(entry * qty))

    print(f"\n== panels scored: {seen} ==")
    print(f"DOW_TREND scored non-zero on {dow_nonzero} of {seen} daily windows")
    print("\n== factor participation (share of panels with a non-zero score) ==")
    for name, count in participation.most_common():
        print(f"  {name:20s} w{weights[name]:>3.0f}   {100 * count / seen:5.1f}%")
    print("\n== scoring factors per panel ==")
    for k in sorted(scoring_count):
        print(f"  {k}: {100 * scoring_count[k] / seen:5.1f}%")
    print(
        f"denominator (Σ weight of scoring factors, max 160): "
        f"p50 {_pct(denominators, 0.5):.0f}  p90 {_pct(denominators, 0.9):.0f}  "
        f"mean {statistics.mean(denominators):.1f}"
    )
    print(f"confidence: p50 {_pct(confidences, 0.5):.0f}  p90 {_pct(confidences, 0.9):.0f}")
    print("\n== ADX regime adjustment to the 70% gate ==")
    for label, count in adx_adjust.most_common():
        print(f"  {label:24s} {100 * count / seen:5.1f}%")
    print(
        f"\n== gate: {passed}/{seen} = {100 * passed / seen:.2f}% "
        f"dirs={dict(dirs)} classes={dict(classes)} =="
    )
    if not passed:
        return
    print(
        f"  passing panels: scoring factors p10 {_pct(pass_n, 0.1):.0f} "
        f"p50 {_pct(pass_n, 0.5):.0f} p90 {_pct(pass_n, 0.9):.0f} · "
        f"denominator p50 {_pct(pass_den, 0.5):.0f}"
    )
    for name, count in pass_factors.most_common(12):
        print(f"     {name:20s} present in {100 * count / passed:5.1f}% of passing signals")
    print(
        f"\n== level geometry: {len(sl_pct)} usable, {level_reject} rejected by the "
        f"class SL cap / degenerate pivot =="
    )
    print(
        f"  stop width %: p10 {_pct(sl_pct, 0.1):.2f}  p50 {_pct(sl_pct, 0.5):.2f}  "
        f"p90 {_pct(sl_pct, 0.9):.2f} · under 2%: "
        f"{100 * sum(1 for x in sl_pct if x < 2) / len(sl_pct):.1f}%"
    )
    rrs = rr
    print(
        f"  R:R p10 {_pct(rrs, 0.1):.2f}  p50 {_pct(rrs, 0.5):.2f}  p90 {_pct(rrs, 0.9):.2f} · "
        f"below 1.0: {100 * sum(1 for x in rrs if x < 1) / len(rrs):.1f}%"
    )
    print(
        f"  notional at ₹{CAPITAL:,.0f}/{RISK_PCT}%: p50 ₹{_pct(notional, 0.5):,.0f}  "
        f"p90 ₹{_pct(notional, 0.9):,.0f} · over the 1.0× cap: "
        f"{100 * sum(1 for x in notional if x > float(CAPITAL)) / len(notional):.1f}%"
    )
    print(
        f"\n== pivot geometry (entry → last swing low, % of price) ==\n"
        f"  p10 {_pct(pivot_dist, 0.1):.2f}  p50 {_pct(pivot_dist, 0.5):.2f}  "
        f"p90 {_pct(pivot_dist, 0.9):.2f} · at or above the entry close: "
        f"{100 * sum(1 for x in pivot_dist if x <= 0) / len(pivot_dist):.1f}% · "
        f"beyond the 8% swing cap: "
        f"{100 * sum(1 for x in pivot_dist if x > 8) / len(pivot_dist):.1f}%"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=250)
    ap.add_argument("--dates", type=int, default=30)
    ap.add_argument("--stride", type=int, default=25)
    args = ap.parse_args()
    asyncio.run(main(args.stocks, args.dates, args.stride))
