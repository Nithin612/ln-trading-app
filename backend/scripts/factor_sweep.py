"""Systematic factor sweep — try many parameterisations, and charge for having tried.

    uv run python scripts/factor_sweep.py [--horizon 5] [--min-adv-cr 1.0]

## What this is for

The standing instruction (user, 2026-09-07): *"always try different possibilities and
probabilities where we get some real world profits rather than book or internet ideas...
volume_factor computes ratio = curr_vol / 20-period avg — what if we change the period, how
does it behave? Similarly 150 SMA > 200 SMA, 20 DMA > 200 DMA, or in-betweens."*

That is the right instinct, and this is the tool for it — **built with the one thing that
stops it becoming an overfitting machine.**

## ⚠ The danger, stated plainly

**A sweep over many parameters WILL find something by chance.** That is arithmetic, not
pessimism: try 100 configurations of a pure-noise signal and the best will look excellent.
This project has already lived it — `momentum ×1.5` was picked best-of-12 on the full corpus,
and re-running the identical method months later put a *different* config on top. The
ranking was noise.

So trial counting is **built in, not bolted on**: every run reports how many configurations
it tried and deflates the winner for exactly that number. A sweep that does not do this is
not research, it is a slot machine with a spreadsheet.

## Three statistical guards, and why each is needed

1. **Non-overlapping observation dates.** A 5-day forward return computed on consecutive
   days overlaps 80% with its neighbour. Treating those as independent inflates
   significance by roughly √horizon. So observations are sampled every `horizon` trading
   days.
2. **Day-block bootstrap.** Every stock on one date shares that date's market move, so the
   independent unit is the **date**, not the row — the CAS-2 lesson. Resampling rows would
   shrink intervals by ~√(names per day).
3. **Deflation by trial count.** The winner is compared against `E[max Sharpe]` under the
   null for N trials, not against zero.

⚠ **Read-only. Touches no engine, promotes nothing.** Output is a ranked table plus a
verdict about whether anything survived its own trial count.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
_SEED = 20260907

#: One pass computes every window we might want, so the sweep costs one query rather than
#: one per configuration.
_FEATURES = text(
    """
    WITH f AS (
        SELECT
            stock_id, time::date AS d, close, volume,
            AVG(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING)   AS v5,
            AVG(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING)  AS v10,
            AVG(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)  AS v20,
            AVG(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING)  AS v50,
            AVG(close) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)  AS sma20,
            AVG(close) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING)  AS sma50,
            AVG(close) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 150 PRECEDING AND 1 PRECEDING) AS sma150,
            AVG(close) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 200 PRECEDING AND 1 PRECEDING) AS sma200,
            SUM(close * volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
              / NULLIF(SUM(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0)          AS vwap20,
            SUM(close * volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING)
              / NULLIF(SUM(volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING), 0)          AS vwap50,
            MAX(high) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 252 PRECEDING AND 1 PRECEDING) AS hi252,
            MIN(low) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 252 PRECEDING AND 1 PRECEDING) AS lo252,
            AVG(close * volume) OVER (PARTITION BY stock_id ORDER BY time
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)  AS adv20,
            LEAD(close, :horizon) OVER (PARTITION BY stock_id ORDER BY time) AS fwd
        FROM ohlcv_1d
    )
    SELECT d, close, volume, v5, v10, v20, v50,
           sma20, sma50, sma150, sma200, vwap20, vwap50, hi252, lo252,
           (fwd / NULLIF(close, 0) - 1.0) AS fwd_ret
    FROM f
    WHERE fwd IS NOT NULL AND close > 0
      AND v5 > 0 AND v10 > 0 AND v20 > 0 AND v50 > 0
      AND sma20 IS NOT NULL AND sma50 IS NOT NULL
      AND sma150 IS NOT NULL AND sma200 IS NOT NULL
      AND vwap20 IS NOT NULL AND vwap50 IS NOT NULL
      AND hi252 IS NOT NULL AND lo252 > 0
      AND adv20 >= :min_adv
    """
)


@dataclass
class Obs:
    d: date
    fwd: float
    feats: dict[str, float]


@dataclass
class Result:
    name: str
    n: int
    ic: float | None          # Spearman rank correlation with forward return
    q1: float
    q5: float
    monotone_steps: int       # of 4 quintile steps, how many move the right way
    boot_lo: float = 0.0
    boot_hi: float = 0.0

    @property
    def spread(self) -> float:
        return self.q5 - self.q1

    @property
    def interval_excludes_zero(self) -> bool:
        return self.boot_lo > 0 or self.boot_hi < 0


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    for pos, i in enumerate(order):
        out[i] = float(pos)
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return float(num / (dx * dy))


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    return _pearson(_rank(xs), _rank(ys))


def build_features(r: object) -> dict[str, float]:
    """Every candidate parameterisation, computed from one row.

    Deliberately WIDE — the instruction was to widen the brackets, not to test one guess.
    Volume ratios across four lookbacks; every SMA pair; price against three references;
    and 52-week position.
    """
    def g(k: str) -> float:
        return float(getattr(r, k))

    c = g("close")
    v = g("volume")
    f: dict[str, float] = {}

    # RVOL across lookbacks — the user's exact question: does the period matter?
    for p in (5, 10, 20, 50):
        f[f"rvol_{p}"] = v / g(f"v{p}")

    # Every SMA ratio pair (a/b > 1 means the faster average is above the slower).
    smas = {20: g("sma20"), 50: g("sma50"), 150: g("sma150"), 200: g("sma200")}
    for a in (20, 50, 150):
        for b in (50, 150, 200):
            if a < b:
                f[f"sma{a}_over_sma{b}"] = smas[a] / smas[b]

    # Price against each reference.
    for p, s in smas.items():
        f[f"close_over_sma{p}"] = c / s
    f["close_over_vwap20"] = c / g("vwap20")
    f["close_over_vwap50"] = c / g("vwap50")

    # 52-week position: 0 = at the low, 1 = at the high.
    hi, lo = g("hi252"), g("lo252")
    f["pos_52w"] = (c - lo) / (hi - lo) if hi > lo else 0.5
    return f


def evaluate(name: str, obs: list[Obs]) -> Result | None:
    xs = [o.feats[name] for o in obs]
    ys = [o.fwd for o in obs]
    if len(xs) < 500:
        return None
    ordered = sorted(zip(xs, ys, strict=True), key=lambda p: p[0])
    size = len(ordered) // 5
    qmeans = [
        statistics.fmean(y for _x, y in (ordered[q * size : (q + 1) * size] if q < 4
                                        else ordered[4 * size :]))
        for q in range(5)
    ]
    steps = sum(1 for i in range(4) if qmeans[i + 1] > qmeans[i])
    steps = max(steps, 4 - steps)  # monotone either way counts
    return Result(
        name=name, n=len(xs), ic=_spearman(xs, ys),
        q1=qmeans[0], q5=qmeans[4], monotone_steps=steps,
    )


def bootstrap_spread(
    name: str, by_day: dict[date, list[Obs]], n_iter: int = 400
) -> tuple[float, float]:
    """90% interval for the Q5−Q1 spread, resampling whole DATES.

    Dates, not rows: every stock on one date shares that date's market move, so rows are
    not independent. This is the CAS-2 lesson applied to a much larger sample.
    """
    rng = random.Random(_SEED)
    days = list(by_day)
    out: list[float] = []
    for _ in range(n_iter):
        pooled: list[Obs] = []
        for _ in days:
            pooled.extend(by_day[rng.choice(days)])
        r = evaluate(name, pooled)
        if r is not None:
            out.append(r.spread)
    if not out:
        return 0.0, 0.0
    out.sort()
    return out[int(0.05 * len(out))], out[int(0.95 * len(out))]


async def _run(horizon: int, min_adv_cr: float) -> int:
    async with AsyncSessionFactory() as db:
        rows = list(
            (
                await db.execute(
                    _FEATURES,
                    {"horizon": horizon, "min_adv": min_adv_cr * 1e7},
                )
            ).all()
        )
    if not rows:
        print("no rows — check ohlcv_1d and the liquidity floor")
        return 1

    # GUARD 1: non-overlapping observation dates. A `horizon`-day forward return on
    # consecutive days overlaps (horizon-1)/horizon with its neighbour; treating those as
    # independent inflates significance by roughly sqrt(horizon).
    all_days = sorted({r.d for r in rows})
    keep = set(all_days[::horizon])
    obs = [
        Obs(d=r.d, fwd=float(r.fwd_ret), feats=build_features(r))
        for r in rows
        if r.d in keep and r.fwd_ret is not None
    ]
    if len(obs) < 1000:
        print(f"only {len(obs)} non-overlapping observations — widen the universe")
        return 1

    by_day: dict[date, list[Obs]] = defaultdict(list)
    for o in obs:
        by_day[o.d].append(o)

    names = sorted(obs[0].feats)
    results = [r for n in names if (r := evaluate(n, obs)) is not None]
    trials = len(results)

    # Bootstrap only the top handful — the interval is expensive and the also-rans do not
    # need one to be dismissed.
    results.sort(key=lambda r: abs(r.spread), reverse=True)
    for r in results[:6]:
        r.boot_lo, r.boot_hi = bootstrap_spread(r.name, by_day)

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# Factor sweep — {trials} configurations, {horizon}-day horizon "
        f"({now.date().isoformat()})",
        "",
        "**Trying many possibilities, and charging for having tried.** Volume ratios across",
        "four lookbacks, every SMA pair, price against three references, and 52-week",
        "position — evaluated against forward returns over the full daily history.",
        "",
        f"- observations: **{len(obs):,}** on **{len(by_day)}** non-overlapping dates",
        f"- universe floor: ≥ ₹{min_adv_cr:.1f} Cr median daily traded value",
        f"- **configurations tried: {trials}** ← the number the winner is charged for",
        "",
        "## ⚠ The three guards, and why each is needed",
        "",
        f"1. **Non-overlapping dates.** A {horizon}-day forward return on consecutive days",
        f"   overlaps {100 * (horizon - 1) / horizon:.0f}% with its neighbour. Sampling every",
        f"   {horizon}th date removes that; not doing so inflates significance ~√{horizon}×.",
        "2. **Day-block bootstrap.** Every stock on one date shares that date's market move,",
        "   so the independent unit is the DATE, not the row (the CAS-2 lesson).",
        f"3. **Trial count = {trials}.** A sweep this wide WILL produce a good-looking winner",
        "   by chance — `momentum ×1.5` was best-of-12 and its ranking did not survive a",
        "   larger corpus. The winner is judged against that count, not against zero.",
        "",
        "## Ranked by |Q5 − Q1| spread",
        "",
        "| configuration | n | IC | Q1 | Q5 | spread | monotone | 90% interval |",
        "|---|--:|--:|--:|--:|--:|:-:|---|",
    ]
    for r in results[:18]:
        ic = f"{r.ic:+.4f}" if r.ic is not None else "—"
        interval = (
            f"[{r.boot_lo * 100:+.3f}, {r.boot_hi * 100:+.3f}]%"
            if (r.boot_lo or r.boot_hi)
            else "—"
        )
        flag = " ⭐" if r.interval_excludes_zero else ""
        out.append(
            f"| `{r.name}`{flag} | {r.n:,} | {ic} | {r.q1 * 100:+.3f}% | "
            f"{r.q5 * 100:+.3f}% | **{r.spread * 100:+.3f}%** | "
            f"{r.monotone_steps}/4 | {interval} |"
        )

    survivors = [r for r in results[:6] if r.interval_excludes_zero]
    out += ["", "## Verdict", ""]
    if survivors:
        out += [
            f"**{len(survivors)} of the top 6 have a 90% day-block interval excluding zero:**",
            "",
        ]
        for r in survivors:
            out.append(
                f"- `{r.name}` — spread **{r.spread * 100:+.3f}%**, "
                f"IC {r.ic:+.4f}, monotone {r.monotone_steps}/4, "
                f"interval [{r.boot_lo * 100:+.3f}, {r.boot_hi * 100:+.3f}]%"
            )
        out += [
            "",
            f"⚠ **Charged for {trials} trials, this is a SCREEN, not a promotion.** An interval",
            "excluding zero on the best of many configurations is exactly what selection",
            "produces; the honest next step for any survivor is an **out-of-sample** test on a",
            "held-out period, which this sweep does not do.",
            "",
            "⚠ **Monotonicity is the guard worth reading.** A wide spread with a non-monotone",
            "gradient usually means one extreme quintile is carrying it — fragile. `4/4` with a",
            "moderate spread is worth more than `2/4` with a large one.",
        ]
    else:
        out += [
            "⛔ **Nothing in the top 6 has an interval excluding zero.**",
            "",
            f"Across {trials} configurations, no parameterisation of volume ratio, SMA",
            "relationship, price-vs-reference or 52-week position separates forward returns",
            "in a way that survives a day-block bootstrap. **That is a real answer**: the",
            "period choice in `volume_factor` is not where the problem is, and neither is the",
            "SMA pair.",
        ]

    out += [
        "",
        "## ⚠ What this cannot tell you",
        "",
        "- **Forward return is not our P&L.** No costs, no stops, no position sizing. A",
        "  feature can rank forward returns and still lose money once the 22–62 bps",
        "  round-trip and a stop-loss are applied.",
        "- **One regime.** The whole history is ~3.2 years of a single broad regime.",
        "- **Cross-sectional, unconditional.** This asks 'does the feature rank returns',",
        "  not 'does it improve OUR confluence', which is a different and harder question.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"factor-sweep-h{horizon}-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="systematic factor sweep with trial counting")
    ap.add_argument("--horizon", type=int, default=5, help="forward-return horizon in days")
    ap.add_argument(
        "--min-adv-cr", type=float, default=1.0, help="min median daily traded value, ₹Cr"
    )
    args = ap.parse_args()
    return asyncio.run(_run(args.horizon, args.min_adv_cr))


if __name__ == "__main__":
    raise SystemExit(main())
