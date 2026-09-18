"""B7 — the MFE/MAE surface and the hazard curve `P(+1R before −1R | day d)`.

    uv run python scripts/b7_hazard.py <swing_trades.csv> [--stocks 250]

⭐ **Why this is B6's companion and not a separate errand.** E2 alone gives half a verdict.
If the unconditional IC is a null the closure is clean — but if it is POSITIVE, the next
question is whether the barrier geometry gives the information back, and only the
excursion surface can answer that (§12.28's decision tree, branch 4). `MFE ≫ |MAE|` with a
realised R < 0 is a **geometry** repair, not closure.

⭐ **And it retires a PARKED item for free.** §13.11 lists hold-period-as-breadth-lever as
UNCONVERGED: round 8's D2 argued 9 slots × 3-day holds gives 298 effective observations a
year against 109, and both Kimi and ChatGPT pushed back that more observations ≠ more
information because shortening the hold changes μ, turnover cost and the DP drag together.
**The hazard curve decides it** — if the edge is concentrated in the first 2–3 days,
shortening the hold raises μ as well as n.

⚠ **Three things this measures that nothing else has:**
  1. `P(+1R before −1R | day d)` for d = 1..20 — the actual resolution shape.
  2. Time-to-MFE and time-to-MAE by stop-width bucket and by direction.
  3. ⭐ **The `T = 0` cohort, separated out.** §12.31f measured 27 of 185 trades (14.6%)
     exiting on the bar they opened at **mean R −0.7034 and a 14.8% win rate**, against
     −0.0541 and 43.7% for the rest. **One trade in seven dies on its entry bar and that
     has never been isolated anywhere.**

⚠ **Read-only.** Consumes the artifact `swing_dependence_probe.py --dump-trades` writes and
re-walks the daily bars between entry and exit. Touches no engine and no money path.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import math
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from swing_dependence_probe import load_frames  # noqa: E402

MAX_DAY = 20


def _load(path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            d: dict[str, Any] = {}
            for k, v in r.items():
                if k in ("sym", "entry", "exit", "dir"):
                    d[k] = v
                elif k == "straddle":
                    d[k] = v == "True"
                else:
                    try:
                        d[k] = float(v)
                    except (TypeError, ValueError):
                        d[k] = float("nan")
            out.append(d)
    return out


def _mean_se(v: list[float]) -> tuple[int, float, float]:
    n = len(v)
    if n < 2:
        return n, (v[0] if v else float("nan")), float("nan")
    return n, statistics.mean(v), statistics.stdev(v) / math.sqrt(n)


def walk_excursions(
    trades: list[dict[str, Any]], frames: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Each trade's own bars → MFE/MAE in R, and the day each barrier was first touched.

    ⭐ Extracted from `main` for queue item 6, unchanged, so the re-run can walk the SAME
    excursions under the delete treatment instead of reimplementing this (W2). Returns
    `(records, unmatched)`.

    ⚠ `w` is `t["w"]`, which the probe computes from `rec.entry_price` — the FILL. So MFE and
    MAE are FILL-referenced like every other R in this codebase (M64), and a trade whose fill
    already gapped through its stop is normalised by a risk distance that the live engine
    would never have accepted. That is exactly the population item 4's delete treatment
    removes, and why B7 is in item 6's scope at all.
    """
    recs: list[dict[str, Any]] = []
    missing = 0
    for t in trades:
        df = frames.get(t["sym"])
        if df is None:
            missing += 1
            continue
        pos = {d.date(): k for k, d in enumerate(df.index)}
        e = pos.get(date.fromisoformat(t["entry"]))
        x = pos.get(date.fromisoformat(t["exit"]))
        if e is None or x is None or x < e:
            missing += 1
            continue
        px = t["entry_px"]
        w = t["w"] / 100.0 * px            # risk per share, in rupees
        if w <= 0 or px <= 0:
            continue
        sgn = 1.0 if t["dir"] == "BUY" else -1.0
        mfe = mae = 0.0
        day_1r = day_m1r = None
        # day 0 is the entry bar itself — 14.6% of trades never see a day 1.
        for k in range(e, min(x, e + MAX_DAY) + 1):
            hi, lo = float(df["high"].iloc[k]), float(df["low"].iloc[k])
            up = sgn * (hi - px) if sgn > 0 else sgn * (lo - px)
            dn = sgn * (lo - px) if sgn > 0 else sgn * (hi - px)
            mfe = max(mfe, up / w)
            mae = min(mae, dn / w)
            d = k - e
            if day_1r is None and mfe >= 1.0:
                day_1r = d
            if day_m1r is None and mae <= -1.0:
                day_m1r = d
        recs.append({
            **t, "mfe_r": mfe, "mae_r": mae,
            "day_1r": day_1r, "day_m1r": day_m1r,
            "mfe_pct": mfe * t["w"], "mae_pct": mae * t["w"],
            "mfe_atr": (mfe * t["w"] / t["atr_pct"]) if t["atr_pct"] == t["atr_pct"]
            and t["atr_pct"] else float("nan"),
        })
    return recs, missing


async def main(csv_path: str, n_stocks: int) -> None:
    trades = _load(csv_path)
    frames = await load_frames(n_stocks)
    print(f"trades {len(trades)}   frames {len(frames)}")

    recs, missing = walk_excursions(trades, frames)
    print(f"excursion paths walked {len(recs)}   (unmatched: {missing})")
    if len(recs) < 20:
        print("too few — aborting")
        return
    _report(recs)


def _hazard(rows: list[dict[str, Any]], label: str) -> None:
    """⭐ P(+1R before −1R | resolved by day d), cumulative, plus what is still open."""
    n = len(rows)
    print(f"\n  ── {label} (n={n}) ──")
    print(f"  {'day':>4} {'+1R first':>10} {'-1R first':>10} {'unresolved':>11} "
          f"{'P(+1R first | resolved)':>25}")
    for d in range(0, MAX_DAY + 1):
        up = sum(1 for r in rows if r["day_1r"] is not None and r["day_1r"] <= d
                 and (r["day_m1r"] is None or r["day_1r"] <= r["day_m1r"]))
        dn = sum(1 for r in rows if r["day_m1r"] is not None and r["day_m1r"] <= d
                 and (r["day_1r"] is None or r["day_m1r"] < r["day_1r"]))
        res = up + dn
        p = up / res if res else float("nan")
        if d <= 5 or d % 5 == 0:
            print(f"  {d:>4} {up:>10} {dn:>10} {n-res:>11} {p:>24.3f}")


def _report(recs: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 100)
    print("1. ⭐ THE T=0 COHORT — one trade in seven dies on the bar it opened")
    print("=" * 100)
    z = [r for r in recs if r["T"] == 0]
    nz = [r for r in recs if r["T"] > 0]
    for lab, g in (("T = 0 (same-session exit)", z), ("T >= 1", nz)):
        if len(g) < 2:
            continue
        n, m, se = _mean_se([r["Rw"] for r in g])
        win = 100 * sum(1 for r in g if r["Rw"] > 0) / n
        _, mf, _ = _mean_se([r["mfe_r"] for r in g])
        _, ma, _ = _mean_se([r["mae_r"] for r in g])
        print(f"  {lab:<28} n={n:>4} ({100*n/len(recs):4.1f}%)  mean R {m:+.4f}  "
              f"SE {se:.4f}  win {win:5.1f}%   MFE {mf:+.3f}R  MAE {ma:+.3f}R")
    if len(z) > 2 and len(nz) > 2:
        _, m1, s1 = _mean_se([r["Rw"] for r in z])
        _, m2, s2 = _mean_se([r["Rw"] for r in nz])
        d, se = m1 - m2, math.hypot(s1, s2)
        print(f"  ⇒ CONTRAST {d:+.4f}  SE {se:.4f}  t {d/se if se else float('nan'):+.2f}")

    print("\n" + "=" * 100)
    print("2. ⭐⭐ THE EXCURSION SURFACE — is there information the geometry gives back?")
    print("=" * 100)
    print("  ⭐ MFE >> |MAE| with realised R < 0 would mean the entry HAS information and")
    print("     the barrier placement hands it back: a GEOMETRY repair, not closure.")
    for lab, g in (("ALL", recs),
                   ("clean", [r for r in recs if not r["straddle"]]),
                   ("clean x BUY", [r for r in recs if not r["straddle"]
                                    and r["dir"] == "BUY"])):
        if len(g) < 5:
            continue
        _, mf, sf = _mean_se([r["mfe_r"] for r in g])
        _, ma, sa = _mean_se([r["mae_r"] for r in g])
        _, mr, sr = _mean_se([r["Rw"] for r in g])
        ratio = mf / abs(ma) if ma else float("nan")
        print(f"  {lab:<14} n={len(g):>4}  MFE {mf:+.3f}R (SE {sf:.3f})  "
              f"MAE {ma:+.3f}R (SE {sa:.3f})  MFE/|MAE| {ratio:5.2f}  "
              f"realised R {mr:+.4f} (SE {sr:.3f})")

    print("\n" + "=" * 100)
    print("3. ⭐⭐ THE HAZARD CURVE — and it decides the PARKED hold-period question")
    print("=" * 100)
    print("  §13.11 lists hold-period-as-breadth-lever as UNCONVERGED: D2 argued 9 slots x")
    print("  3-day holds gives 298 effective obs/yr vs 109, and two reviewers pushed back")
    print("  that more observations != more information. If the edge is concentrated in the")
    print("  first 2-3 days, shortening the hold raises mu as well as n.")
    _hazard(recs, "ALL")
    _hazard([r for r in recs if not r["straddle"] and r["dir"] == "BUY"], "clean x BUY")

    print("\n" + "=" * 100)
    print("4. TIME-TO-EXCURSION by stop-width bucket and direction")
    print("=" * 100)
    print(f"  {'cohort':<22} {'n':>4} {'meanT':>6} {'t->MFE':>8} {'t->MAE':>8} "
          f"{'MFE':>8} {'MAE':>8}")
    buckets: list[tuple[str, list[dict[str, Any]]]] = [
        (f"w {lo}-{hi if hi < 1e8 else 999}%",
         [r for r in recs if lo <= r["w"] < hi])
        for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 10), (10, 1e9))
    ]
    buckets += [("dir BUY", [r for r in recs if r["dir"] == "BUY"]),
                ("dir SELL", [r for r in recs if r["dir"] == "SELL"])]
    for lab, g in buckets:
        if len(g) < 3:
            continue
        t1 = [float(r["day_1r"]) for r in g if r["day_1r"] is not None]
        t2 = [float(r["day_m1r"]) for r in g if r["day_m1r"] is not None]
        print(f"  {lab:<22} {len(g):>4} {statistics.mean([r['T'] for r in g]):>6.2f} "
              f"{statistics.mean(t1) if t1 else float('nan'):>8.2f} "
              f"{statistics.mean(t2) if t2 else float('nan'):>8.2f} "
              f"{statistics.mean([r['mfe_r'] for r in g]):>+8.3f} "
              f"{statistics.mean([r['mae_r'] for r in g]):>+8.3f}")
    _ = collections


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--stocks", type=int, default=250)
    a = ap.parse_args()
    asyncio.run(main(a.csv, a.stocks))
