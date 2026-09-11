"""E2 / B6 — does the composite score carry cross-sectional information?

⛔ **PRE-REGISTERED.** Estimands, horizon, thresholds, decision tree and predictions were
fixed in `docs/analysis/E2-PREREGISTRATION-2026-09-12.md` and committed (`fe5d508`) BEFORE
this file existed. Read that first. Nothing here may quietly differ from it; a deviation
is an amendment in that document, timestamped, with the original left standing.

    uv run python scripts/e2_score_ic.py [--stocks 250] [--stride 5] [--dump panel.csv]

## The three estimands (§1 of the pre-registration)

    3a  UNCONDITIONAL IC   Spearman(S, fwd_5d) within each session, across the eligible
                           universe, averaged over sessions.  ⭐ THE DECISION READS THIS.
    3b  MATCHED-TAIL       mean fwd_5d of gate-passers minus date-and-characteristic-
                           matched non-passers (nearest neighbour on log-close and 20d
                           realised vol, same session).
    3c  GATE-CONDITIONAL   Spearman within passers only.
                           ⚠ A COLLIDER — gate passage is a threshold on the same weighted
                           sum S is. Reported, NEVER decided on.

`S` is the **signed** `normalized_score` (amendment 1): a cross-sectional IC asks whether
the score ORDERS forward returns, and `confidence_pct` is a magnitude that treats a strong
SELL and a strong BUY identically. Confidence is reported beside it because it is the key
the deployed UI sorts by, but it does not move the decision.

## Two assumed constants this run must RETIRE (§3)

`sd(IC_t)` is `[ASSUMED] 0.10` and every power figure in two documents is linear in it;
`factor_sweep.py` does not store per-date ICs, so this is the only way to measure it.
`E[z | selected]` is **2.268**, a NORMAL-TAIL approximation applied to a hard gate at 70 on
a bounded score whose passers have mean 77.8 / sd 5.8 — which is not a normal tail.

## Read-only

SELECT-only. The frozen scorer is imported and CALLED (`min_confidence=0` so a score exists
for every name, a supported parameter — not modified). No gate is flipped, no knob moved,
no recorded number touched.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analysis.confluence import run_all_factors, score_from_factors  # noqa: E402
from app.analysis.indicators.adx import adx_is_strong, adx_is_weak  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.market_calendar import (  # noqa: E402
    observed_session_index,
    window_has_holes,
)
from factor_sweep import _spearman  # noqa: E402  (W2: one implementation)
from swing_dependence_probe import load_frames  # noqa: E402

WINDOW = 300
HORIZON = 5            # ⛔ PRE-REGISTERED. 20d is descriptive only — at 20d the test can
SECONDARY = 20         #    only return INCONCLUSIVE (SE(IC) 0.0159 ⇒ t 1.26 at IC 0.02).
GATE = 70
PRICE_FLOOR = 1.0


@dataclass
class Row:
    day: date
    sym: str
    score: float          # signed normalized_score, THE predictor
    conf: int             # |normalized| * 100, the deployed sort key
    passed: bool          # cleared the ADX-adjusted gate
    fwd: float            # h=5d forward return %
    fwd20: float
    logpx: float
    vol20: float


def _fwd(closes: pd.Series, i: int, h: int) -> float:
    """Forward return % from the DECISION bar's close to `h` sessions later.

    ⚠ From the CLOSE, not from an entry price. Round 8's methods trap: measuring from a
    trigger price spans the rest of the entry day and rewards a bar that already ran — it
    manufactured a 1.8pp 'effect' that vanished when measured from the close.
    """
    if i + h >= len(closes):
        return float("nan")
    a, b = float(closes.iloc[i]), float(closes.iloc[i + h])
    return (b / a - 1.0) * 100.0 if a > 0 else float("nan")


def _realised_vol(closes: pd.Series, i: int, n: int = 20) -> float:
    seg = closes.iloc[max(0, i - n) : i + 1].pct_change().dropna()
    return float(seg.std() * 100) if len(seg) > 2 else float("nan")


def _mean_se(v: list[float]) -> tuple[int, float, float]:
    n = len(v)
    if n < 2:
        return n, (v[0] if v else float("nan")), float("nan")
    return n, statistics.mean(v), statistics.stdev(v) / math.sqrt(n)


def _band(mean: float, se: float, breakeven: float) -> str:
    """⛔ The pre-registered decision bands (§4). Not re-derived at read time."""
    if se != se:
        return "INCONCLUSIVE (no SE)"
    lo, hi = mean - 1.645 * se, mean + 1.645 * se
    if lo > breakeven:
        return "POSITIVE"
    if lo < 0 < hi and hi < breakeven:
        return "NULL"
    return "INCONCLUSIVE"


async def main(n_stocks: int, stride: int, dump: str | None) -> None:
    frames = await load_frames(n_stocks)
    async with AsyncSessionFactory() as db:
        sessions = await observed_session_index(db)
    print(f"names {len(frames)}   observed sessions {len(sessions):,}   "
          f"horizon {HORIZON}d (pre-registered)   stride {stride}")

    # ⭐ A CROSS-SECTIONAL IC REQUIRES EVERY NAME SCORED ON THE SAME SESSION.
    # The obvious loop — walk each name from its own bar 300 by `stride` — samples a
    # DIFFERENT set of dates per name, so the "cross-section" on any given date is one or
    # two names and the IC is noise by construction. (Caught by the smoke run, which
    # reported a median cross-section of 1.) So the decision dates come from the market's
    # own calendar, and each name is looked up ON those dates.
    grid = sorted(sessions)[::stride]
    print(f"decision sessions on the global grid: {len(grid):,}")

    rows: list[Row] = []
    skipped_gap = 0
    for sym, df in frames.items():
        closes = df["close"]
        pos = {d.date(): k for k, d in enumerate(df.index)}
        for day in grid:
            i = pos.get(day)
            if i is None or i < WINDOW or i >= len(df) - SECONDARY - 1:
                continue
            if float(closes.iloc[i]) <= PRICE_FLOOR:
                continue
            window = df.iloc[i - WINDOW + 1 : i + 1]
            if window_has_holes(
                sessions, window.index[0].date(), window.index[-1].date(), WINDOW
            ):
                skipped_gap += 1
                continue
            factors = run_all_factors(window)
            # min_confidence=0 so EVERY eligible name gets a score, not only passers.
            res = score_from_factors(factors, window, min_confidence=0)
            if res is None:
                continue
            eff = GATE + 5 if adx_is_weak(window) else (
                max(65, GATE - 5) if adx_is_strong(window) else GATE
            )
            fwd = _fwd(closes, i, HORIZON)
            if fwd != fwd:
                continue
            rows.append(Row(
                day=day, sym=sym,
                score=float(res.normalized_score), conf=int(res.confidence_pct),
                passed=bool(res.confidence_pct >= eff),
                fwd=fwd, fwd20=_fwd(closes, i, SECONDARY),
                logpx=math.log(float(closes.iloc[i])),
                vol20=_realised_vol(closes, i),
            ))

    print(f"panels scored {len(rows):,}   (skipped for window holes: {skipped_gap:,})")
    if len(rows) < 100:
        print("too few panels — aborting")
        return

    by_day: dict[date, list[Row]] = {}
    for r in rows:
        by_day.setdefault(r.day, []).append(r)
    print(f"sessions with panels {len(by_day):,}")

    _report(by_day, rows)
    if dump:
        import csv
        with open(dump, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["day", "sym", "score", "conf", "passed", "fwd", "fwd20",
                        "logpx", "vol20"])
            for r in rows:
                w.writerow([r.day, r.sym, r.score, r.conf, int(r.passed), r.fwd,
                            r.fwd20, r.logpx, r.vol20])
        print(f"\n== dumped {len(rows):,} panel rows -> {dump} ==")


def _report(by_day: dict[date, list[Row]], rows: list[Row]) -> None:
    print("\n" + "=" * 100)
    print("0. COVERAGE — power must be weighted by it (§3)")
    print("=" * 100)
    sizes = sorted(len(v) for v in by_day.values())
    n_med = sizes[len(sizes) // 2]
    print(f"  names per session: min {sizes[0]}  p10 {sizes[len(sizes)//10]}  "
          f"median {n_med}  max {sizes[-1]}")
    print(f"  pure-noise IC floor at the MEDIAN cross-section 1/sqrt({n_med}) = "
          f"{1/math.sqrt(n_med):.4f}")
    print(f"  ...at the SMALLEST 1/sqrt({sizes[0]}) = {1/math.sqrt(sizes[0]):.4f}   "
          f"⚠ compare against the break-even band below")

    # ── σ_cs and E[z|selected]: the two constants this run must RETIRE ────────────
    sig_cs = [statistics.stdev([r.fwd for r in v]) for v in by_day.values() if len(v) > 2]
    # ⭐ On the ABSOLUTE score, because the gate is a MAGNITUDE threshold: it admits
    # |normalized| >= 0.70, so it selects BOTH tails and a strong SELL standardises to a
    # large NEGATIVE z on the signed score. The smoke run returned E[z|sel] = -1.61, which
    # is not a tail-strength statistic at all — it is the short side outvoting the long.
    # D3's transfer E[excess|sel] ~ IC * sigma_cs * E[z|sel] assumes selection on |score|
    # with the sign taken by the direction, so |z| is the quantity it means.
    zsel: list[float] = []
    for v in by_day.values():
        if len(v) < 5:
            continue
        absc = [abs(r.score) for r in v]
        m, sd = statistics.mean(absc), statistics.stdev(absc)
        if sd <= 0:
            continue
        sel = [(abs(r.score) - m) / sd for r in v if r.passed]
        if sel:
            zsel.append(statistics.mean(sel))
    print("\n" + "=" * 100)
    print("1. THE TWO ASSUMED CONSTANTS, MEASURED (§3) — these supersede §16.1")
    print("=" * 100)
    print(f"  sigma_cs (cross-sectional sd of {HORIZON}d forward return): "
          f"median {statistics.median(sig_cs):.3f}%  mean {statistics.mean(sig_cs):.3f}%")
    if zsel:
        nz, mz, sez = _mean_se(zsel)
        print(f"  ⭐ E[z | selected]  MEASURED {mz:+.4f}  SE {sez:.4f}  (n={nz} sessions)"
              f"   vs the ASSUMED 2.268")
    sel_rate = 100 * sum(1 for r in rows if r.passed) / len(rows)
    print(f"  gate pass rate {sel_rate:.2f}%   passers {sum(1 for r in rows if r.passed):,}")

    # break-even IC from D3's transfer, at the MEASURED inputs
    ez = statistics.mean(zsel) if zsel else 2.268
    scs = statistics.median(sig_cs)
    be = 0.255 / (scs * ez) if scs * ez else float("nan")
    print(f"  ⇒ break-even IC = 25.5bps / (sigma_cs {scs:.3f}% x E[z|sel] {ez:.3f}) "
          f"= {be:.4f}")

    # ── 3a ────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("2. ⭐ 3a — UNCONDITIONAL IC. THE DECISION READS THIS.")
    print("=" * 100)
    for key, lab in (("score", "signed normalized_score  <- PRE-REGISTERED"),
                     ("conf", "confidence_pct (the deployed sort key; secondary)")):
        for h, hl in (("fwd", f"{HORIZON}d"), ("fwd20", f"{SECONDARY}d (descriptive only)")):
            ics = []
            for v in by_day.values():
                if len(v) < 5:
                    continue
                xs = [getattr(r, key) for r in v]
                ys = [getattr(r, h) for r in v]
                pair = [(x, y) for x, y in zip(xs, ys, strict=True) if y == y]
                if len(pair) < 5:
                    continue
                ic = _spearman([p[0] for p in pair], [p[1] for p in pair])
                if ic is not None:
                    ics.append(ic)
            if len(ics) < 5:
                continue
            n, m, se = _mean_se(ics)
            sd_ic = statistics.stdev(ics)
            verdict = _band(m, se, be) if key == "score" and h == "fwd" else ""
            print(f"  {lab:<52} {hl:<22} IC {m:+.4f}  sd(IC_t) {sd_ic:.4f}  "
                  f"SE {se:.4f}  t {m/se if se else float('nan'):+6.2f}  "
                  f"90% [{m-1.645*se:+.4f}, {m+1.645*se:+.4f}]  {verdict}")
            if key == "score" and h == "fwd":
                print(f"      ⭐ sd(IC_t) MEASURED {sd_ic:.4f} vs the ASSUMED 0.10 "
                      f"(n={n} sessions)")

    # ── 3b ────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("3. ⭐⭐ 3b — MATCHED-TAIL CONTRAST (the pre-registered estimand)")
    print("=" * 100)
    diffs: list[float] = []
    matched = 0
    for v in by_day.values():
        passers = [r for r in v if r.passed]
        pool = [r for r in v if not r.passed and r.vol20 == r.vol20]
        if not passers or len(pool) < 3:
            continue
        for p in passers:
            if p.vol20 != p.vol20:
                continue
            nn = min(pool, key=lambda q: (q.logpx - p.logpx) ** 2
                     + ((q.vol20 - p.vol20) / max(p.vol20, 1e-6)) ** 2)
            diffs.append(p.fwd - nn.fwd)
            matched += 1
    if len(diffs) > 5:
        n, m, se = _mean_se(diffs)
        lo, hi = m - 1.645 * se, m + 1.645 * se
        print(f"  matched pairs {matched:,}")
        print(f"  ⭐ passer MINUS matched non-passer, {HORIZON}d: {m:+.4f}%  SE {se:.4f}  "
              f"t {m/se if se else float('nan'):+6.2f}  90% [{lo:+.4f}, {hi:+.4f}]")
        print(f"     break-even needs > +0.255% (the explicit round-trip charge stack)")
        print(f"     VERDICT: {'POSITIVE' if lo > 0.255 else ('NULL' if hi < 0.255 and lo < 0 < hi else 'INCONCLUSIVE')}")
    else:
        print("  too few matched pairs")

    # ── 3c ────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("4. 3c — GATE-CONDITIONAL IC. ⚠ A COLLIDER. REPORTED, NEVER DECIDED ON.")
    print("=" * 100)
    ics = []
    for v in by_day.values():
        pv = [r for r in v if r.passed]
        if len(pv) < 5:
            continue
        ic = _spearman([r.score for r in pv], [r.fwd for r in pv])
        if ic is not None:
            ics.append(ic)
    if len(ics) >= 5:
        n, m, se = _mean_se(ics)
        print(f"  within passers: IC {m:+.4f}  SE {se:.4f}  t {m/se if se else 0:+6.2f}  "
              f"(n={n} sessions)")
    print("  ⚠ gate passage is a threshold on the same weighted sum the score IS, so this")
    print("     number is conditioned on the estimator's own output. It cannot license a")
    print("     conclusion in either direction (ChatGPT R4-15, adopted round 4).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=250)
    ap.add_argument("--stride", type=int, default=HORIZON,
                    help="sample every Nth session; default = horizon (non-overlapping)")
    ap.add_argument("--dump", default=None, help="write the panel to this CSV")
    a = ap.parse_args()
    asyncio.run(main(a.stocks, a.stride, a.dump))
