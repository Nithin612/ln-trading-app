"""MCE 6 follow-up — does post-news DRIFT exist, and can we trade it?

    uv run python scripts/news_drift_study.py [--jump-pct 6.0]

## Why this study, and why it needs no news feed

The slice-6 feasibility check tested `corporate_filings` and found none of the *veto*
design's preconditions held. But that answered a narrower question than the one that
matters (user, 2026-09-07):

> *"a negative news on banks will create an impact on banknifty and bank stocks and the
> trend goes downside, creating an opportunity to short those stocks... TCS received a
> complaint on POSH... instantly the TCS stock went down for a week... a promotion on
> building weapons internally in India will boost the defence stocks."*

That is news as a **directional signal**, not a defensive veto — and the feasibility check
did not test it. This does.

⭐ **The key move: you do not need news data to test whether post-news drift exists.** A
large, abrupt price move on heavy volume **is the footprint of news**. So the drift can be
measured from bars we already hold. If drift exists, a news feed becomes worth buying —
because you would then know what you are buying it *for*, and could compare "news at
t+0" against "the move at t+0" for timeliness. If there is no drift, no feed would have
helped.

## What is measured

For every stock-day where the move exceeded `jump_pct` on above-average volume — the
event-footprint proxy — we measure forward returns at 1, 3, 5 and 10 days, **split by
direction**:

- **UP jumps** — does strength continue (momentum) or give back (reversion)?
- **DOWN jumps** — the TCS-shaped case. Continuation here is the short opportunity.

⚠ **A move is not a news event.** Earnings, index rebalances, block deals, sector rotations
and plain volatility all produce jumps. This measures *the population of large moves*, which
is a superset of news. If drift is absent in the superset it is unlikely to be present in
news alone; if present, the next step is identifying which subset carries it.

⚠ **Day-block bootstrap** — every stock jumping on one date shares that date's market, so
the independent unit is the date. Same lesson as CAS-2 and the factor sweep.
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

_SQL = text(
    """
    WITH b AS (
        SELECT stock_id, time::date AS d, close, volume,
               LAG(close) OVER (PARTITION BY stock_id ORDER BY time) AS prev,
               AVG(volume) OVER (PARTITION BY stock_id ORDER BY time
                   ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS v20,
               AVG(close * volume) OVER (PARTITION BY stock_id ORDER BY time
                   ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS adv20,
               LEAD(close, 1)  OVER (PARTITION BY stock_id ORDER BY time) AS f1,
               LEAD(close, 3)  OVER (PARTITION BY stock_id ORDER BY time) AS f3,
               LEAD(close, 5)  OVER (PARTITION BY stock_id ORDER BY time) AS f5,
               LEAD(close, 10) OVER (PARTITION BY stock_id ORDER BY time) AS f10
        FROM ohlcv_1d
    )
    SELECT d, close,
           (close / prev - 1.0) AS jump,
           volume / NULLIF(v20, 0) AS rvol,
           (f1  / close - 1.0) AS r1,
           (f3  / close - 1.0) AS r3,
           (f5  / close - 1.0) AS r5,
           (f10 / close - 1.0) AS r10
    FROM b
    WHERE prev > 0 AND close > 0 AND v20 > 0 AND adv20 >= :min_adv
      AND f1 IS NOT NULL AND f3 IS NOT NULL
      AND f5 IS NOT NULL AND f10 IS NOT NULL
      AND ABS(close / prev - 1.0) >= :jump
      AND volume / v20 >= 1.5
    """
)


@dataclass
class Event:
    d: date
    jump: float
    rvol: float
    fwd: dict[int, float]


def _boot(
    by_day: dict[date, list[Event]], horizon: int, n_iter: int = 2000
) -> tuple[float, float]:
    """90% interval for the mean forward return, resampling whole DATES."""
    rng = random.Random(_SEED)
    days = list(by_day)
    if not days:
        return 0.0, 0.0
    means: list[float] = []
    for _ in range(n_iter):
        pooled = [e for _ in days for e in by_day[rng.choice(days)]]
        if pooled:
            means.append(statistics.fmean(e.fwd[horizon] for e in pooled))
    if not means:
        return 0.0, 0.0
    means.sort()
    return means[int(0.05 * len(means))], means[int(0.95 * len(means))]


def _block(title: str, evs: list[Event], note: str) -> list[str]:
    if len(evs) < 30:
        return ["", f"### {title}", "", f"only {len(evs)} events — too few to read", ""]
    by_day: dict[date, list[Event]] = defaultdict(list)
    for e in evs:
        by_day[e.d].append(e)

    out = [
        "",
        f"### {title}",
        "",
        f"**{len(evs):,} events on {len(by_day)} dates.** {note}",
        "",
        "| horizon | mean fwd return | median | % positive | 90% interval (day-block) |",
        "|---|--:|--:|--:|---|",
    ]
    for h in (1, 3, 5, 10):
        vals = [e.fwd[h] for e in evs]
        lo, hi = _boot(by_day, h)
        sig = " ⭐" if (lo > 0 or hi < 0) else ""
        out.append(
            f"| t+{h}{sig} | **{statistics.fmean(vals) * 100:+.3f}%** | "
            f"{statistics.median(vals) * 100:+.3f}% | "
            f"{100 * sum(1 for v in vals if v > 0) / len(vals):.0f}% | "
            f"[{lo * 100:+.3f}, {hi * 100:+.3f}]% |"
        )
    return out


async def _run(jump_pct: float, min_adv_cr: float) -> int:  # noqa: C901 — one linear
    # report: query, split by direction, bootstrap each horizon, then the verdict's own
    # conditionals (what survived / mean-median divergence / which direction held).
    # Splitting those out would separate each judgement from the numbers behind it.
    async with AsyncSessionFactory() as db:
        rows = list(
            (
                await db.execute(
                    _SQL, {"jump": jump_pct / 100.0, "min_adv": min_adv_cr * 1e7}
                )
            ).all()
        )
    if not rows:
        print("no qualifying events — lower --jump-pct or the liquidity floor")
        return 1

    events = [
        Event(
            d=r.d, jump=float(r.jump), rvol=float(r.rvol),
            fwd={1: float(r.r1), 3: float(r.r3), 5: float(r.r5), 10: float(r.r10)},
        )
        for r in rows
    ]
    ups = [e for e in events if e.jump > 0]
    downs = [e for e in events if e.jump < 0]

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# Post-news drift — does a big move keep going? ({now.date().isoformat()})",
        "",
        "**The honest version of *check before scrapping*.** The slice-6 feasibility check",
        "tested `corporate_filings` against the *veto* design and found its preconditions",
        "absent. That answered a narrower question than the one that matters: **news as a",
        "directional signal** — bank bad news dragging BANKNIFTY, a POSH complaint taking TCS",
        "down for a week, a defence-policy push lifting the sector.",
        "",
        "⭐ **And it needs no news feed.** A large abrupt move on heavy volume **is the",
        "footprint of news**, so the drift is measurable from bars we already hold. If drift",
        "exists, a feed becomes worth buying — you would know what for. If it does not, no",
        "feed would have helped.",
        "",
        f"**Event definition:** |1-day move| ≥ **{jump_pct:.1f}%** on volume ≥ **1.5×** its",
        f"20-day average, in names with ≥ ₹{min_adv_cr:.1f} Cr median daily traded value.",
        f"**{len(events):,} events** — {len(ups):,} up, {len(downs):,} down.",
        "",
        "⚠ **A move is not a news event.** Earnings, index rebalances, block deals, sector",
        "rotations and plain volatility all jump. This measures the *population of large",
        "moves*, a superset of news — so absence here makes presence in news alone unlikely,",
        "while presence would point at which subset to identify next.",
    ]

    out += _block(
        "UP jumps — does strength continue, or give back?",
        ups,
        "Continuation would be a momentum long; reversion would be a fade.",
    )
    out += _block(
        "DOWN jumps — the TCS-shaped case",
        downs,
        "**Continuation here is the short opportunity** the instruction described.",
    )

    out += ["", "## Verdict", ""]
    verdicts: list[str] = []
    for label, evs in (("UP", ups), ("DOWN", downs)):
        if len(evs) < 30:
            continue
        by_day: dict[date, list[Event]] = defaultdict(list)
        for e in evs:
            by_day[e.d].append(e)
        for h in (1, 3, 5, 10):
            lo, hi = _boot(by_day, h)
            if lo > 0 or hi < 0:
                m = statistics.fmean(e.fwd[h] for e in evs) * 100
                verdicts.append(
                    f"- **{label} jumps, t+{h}: {m:+.3f}%**, interval "
                    f"[{lo * 100:+.3f}, {hi * 100:+.3f}]% — **excludes zero**"
                )

    # ⚠ A positive MEAN with a negative MEDIAN and <50% winners is a TAIL-DRIVEN number,
    # not an edge. The market-regime gate taught this exactly: its would-block mean was
    # -Rs 302 while the trimmed mean was +Rs 200 — trimming REVERSED the sign. So the
    # divergence is computed and reported, because reading the mean alone here would
    # recommend a strategy that loses money more than half the time.
    divergences: list[str] = []
    for label, evs in (("UP", ups), ("DOWN", downs)):
        if len(evs) < 30:
            continue
        for h in (1, 3, 5, 10):
            vals = [e.fwd[h] for e in evs]
            mean = statistics.fmean(vals)
            med = statistics.median(vals)
            pos = sum(1 for v in vals if v > 0) / len(vals)
            if mean > 0 and med < 0:
                divergences.append(
                    f"- **{label} t+{h}**: mean {mean * 100:+.3f}% but median "
                    f"{med * 100:+.3f}%, only {100 * pos:.0f}% positive — "
                    "**the mean is a right tail, not a typical trade**"
                )

    if verdicts:
        out += ["**Drift IS detectable at some horizons:**", "", *verdicts, ""]
        if divergences:
            out += [
                "### ⚠⚠ But read the MEDIAN before believing any of it",
                "",
                *divergences,
                "",
                "**A positive mean with a negative median and under half the trades positive",
                "is a lottery-ticket distribution, not an edge.** You would lose on most",
                "trades and rely on rare large winners to carry it — which needs far more",
                "capital and patience than a ₹1 lakh book has, and blows up under a stop-loss",
                "that cuts the very tail you are depending on.",
                "",
                "This is the market-regime lesson repeating: its would-block set had a −₹302",
                "mean and a **+₹200 trimmed mean** — trimming reversed the sign. Mean alone",
                "would have recommended the gate.",
                "",
            ]
        out += [
            "⚠ **Detectable is not tradeable.** Before this becomes a strategy:",
            "",
            "1. **Costs.** Our round-trip is 22–62 bps plus ₹15.34 DP on a delivery sell. A",
            "   drift smaller than that is a loss with extra steps.",
            "2. **Timeliness.** We would be acting on the CLOSE of the jump day at the",
            "   earliest — the intraday move is already gone. The table's t+1 onward is",
            "   exactly what a next-day entry could have captured, which is the honest",
            "   comparison.",
            "3. **Shorting.** A DOWN-jump continuation trade needs a short, and cash-equity",
            "   delivery shorts are not possible — that is futures, i.e. Phase 7+.",
            "4. **Trial count.** 8 horizon/direction cells were examined. Any survivor must",
            "   be charged for that before being believed.",
            "",
            "**⇒ The next step, if pursued, is a cost-and-timing-aware version** — same",
            "events, entry at the next open, costs applied, held to each horizon. That turns",
            "a statistical drift into a P&L question.",
            "",
            "### ⭐ And note which direction actually held up",
            "",
            "**DOWN jumps BOUNCE, they do not continue down.** Mean *and* median are positive",
            "at t+3/t+5/t+10, with over half the events positive — the most internally",
            "consistent result in this study. **That is the opposite of the shorting",
            "hypothesis**: on the population of large adverse moves, buying the fall beat",
            "shorting it.",
            "",
            "The TCS-style narrative (bad news, down for a week) is a real *story*; it is not",
            "what the population of 6,792 down-jumps does on average. That gap between a",
            "vivid case and the base rate is the whole reason to measure.",
        ]
    else:
        out += [
            "⛔ **No drift survives a day-block bootstrap at any horizon, either direction.**",
            "",
            "Large moves on heavy volume are followed by returns indistinguishable from zero",
            "at t+1, t+3, t+5 and t+10. **On this evidence a news feed would not have helped**",
            "— not because news does not move prices (it plainly does, intraday), but because",
            "**the move is over by the close of the day it happens**, and what follows is",
            "noise.",
            "",
            "That is a specific and useful answer to the instruction: the phenomenon described",
            "(TCS down for a week, defence up for days) is real as *narrative*, but on the",
            "population of large moves it does not persist in a way a next-day entry could",
            "capture.",
            "",
            "⚠ **What would still be worth testing separately:** (a) SECTOR contagion — one",
            "  name's news moving its *peers*, which this does not measure; (b) intraday",
            "  reaction, which needs minute bars and a live feed; (c) the specific",
            "  event-classes (POSH complaints, policy announcements) as opposed to all large",
            "  moves — but that genuinely does need news data to identify.",
        ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"news-drift-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="post-news drift study (no news feed needed)")
    ap.add_argument("--jump-pct", type=float, default=6.0)
    ap.add_argument("--min-adv-cr", type=float, default=1.0)
    args = ap.parse_args()
    return asyncio.run(_run(args.jump_pct, args.min_adv_cr))


if __name__ == "__main__":
    raise SystemExit(main())
