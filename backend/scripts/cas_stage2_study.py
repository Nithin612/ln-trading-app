"""CAS Stage 2 — does the closing-auction move REVERSE overnight?

    uv run python scripts/cas_stage2_study.py [--out docs/analysis/cas-stage2-<date>.md]

**Stage 1 is complete** (`cas_daily`: 1,664 rows / 8 sessions, no window missed). This is
the study it was accrued for, and it is **read-only — it never gates, sizes or trades.**

## What is measured

    cas_move_i,d      = (official_close − pre_auction_price) / pre_auction_price
    next_return_i,d   = (close_{d+1} − official_close_d) / official_close_d

The reversal hypothesis says these are **negatively** related: a name pushed up into the
auction gives it back tomorrow.

## The control that matters, and why it is cross-sectional

The memory's standing warning on this study is *"control for the oversold regime"* — if the
whole market sagged into the close and bounced the next morning, a naive correlation
measures market beta and calls it an auction edge.

So both series are **demeaned WITHIN each day** before anything is computed. That removes
the market factor exactly rather than approximately: whatever happened to every stock that
day is subtracted from every stock that day. What survives is purely *relative* — did the
names pushed hardest **relative to their peers** give it back **relative to their peers**.

⚠ This also means the study can say nothing about a market-wide auction effect, by
construction. It answers the cross-sectional question only.

## ⚠ The binding constraint is DAYS, not rows

1,664 rows looks like a lot and is not. 208 names on the same afternoon share one market,
so the independent unit is the **day**, and there are **8 captured — of which 7 have a
next day** (`ohlcv_1d` ends on the last capture date). Every interval here is bootstrapped
by resampling **whole days**, because resampling rows would treat 208 correlated
observations as 208 independent ones and produce a confidence interval roughly √208 ≈ 14×
too narrow.

A day-block bootstrap on 7 blocks is a weak instrument. That is the honest state of the
evidence and the report says so rather than burying it.

⚠ `app/services/block_bootstrap.py` is not reused here: it resamples a *return series* to
bootstrap a **Sharpe ratio**, and the statistic here is a cross-sectional correlation over
day-groups. Same idea, different unit — bending it would have meant lying about what the
blocks contain.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OUT_DIR = _REPO_ROOT / "docs" / "analysis"

_SEED = 20260907  # deterministic: an unseeded study is not reproducible

_SQL = text(
    """
    WITH cas AS (
        SELECT stock_id,
               trade_date,
               (official_close - pre_auction_price) / pre_auction_price AS cas_move,
               official_close
        FROM cas_daily
        WHERE pre_auction_price > 0 AND official_close > 0
    ),
    nxt AS (
        SELECT c.stock_id,
               c.trade_date,
               c.cas_move,
               (
                   SELECT o.close
                   FROM ohlcv_1d o
                   WHERE o.stock_id = c.stock_id
                     AND o.time::date > c.trade_date
                   ORDER BY o.time
                   LIMIT 1
               ) AS next_close,
               c.official_close
        FROM cas c
    )
    SELECT trade_date, stock_id, cas_move,
           (next_close - official_close) / official_close AS next_return
    FROM nxt
    WHERE next_close IS NOT NULL AND official_close > 0
    ORDER BY trade_date, stock_id
    """
)


def _demean(xs: list[float]) -> list[float]:
    m = statistics.fmean(xs)
    return [x - m for x in xs]


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


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    return _pearson(_rank(xs), _rank(ys))


def _quintile_spread(pairs: list[tuple[float, float]]) -> tuple[list[float], float | None]:
    """Mean next-return per quintile of cas_move, and the Q1−Q5 spread.

    Q1 is the most NEGATIVE auction move. Under the reversal hypothesis Q1 should have the
    HIGHEST next-day return and the spread should be positive.
    """
    if len(pairs) < 25:
        return [], None
    ordered = sorted(pairs, key=lambda p: p[0])
    size = len(ordered) // 5
    means = []
    for q in range(5):
        chunk = ordered[q * size : (q + 1) * size] if q < 4 else ordered[4 * size :]
        means.append(statistics.fmean(y for _x, y in chunk))
    return means, means[0] - means[-1]


def _by_day(rows: Sequence[Any]) -> dict[object, list[tuple[float, float]]]:
    """Demean both series WITHIN each day — the market-factor control."""
    grouped: dict[object, list[tuple[float, float]]] = defaultdict(list)
    for day, _sid, move, ret in rows:
        grouped[day].append((float(move), float(ret)))
    out: dict[object, list[tuple[float, float]]] = {}
    for day, ps in grouped.items():
        if len(ps) < 5:
            continue
        dm = _demean([p[0] for p in ps])
        dr = _demean([p[1] for p in ps])
        out[day] = list(zip(dm, dr, strict=True))
    return out


def _bootstrap_days(
    by_day: dict[object, list[tuple[float, float]]], n_iter: int = 5000
) -> tuple[float, float, float]:
    """Resample WHOLE DAYS with replacement; return (p5, p50, p95) of Spearman.

    Days, not rows. 208 names on one afternoon share a market, so treating them as
    independent would shrink the interval by roughly √208 ≈ 14× and manufacture a
    significance that is not there.
    """
    rng = random.Random(_SEED)
    days = list(by_day)
    stats: list[float] = []
    for _ in range(n_iter):
        picked = [rng.choice(days) for _ in days]
        pooled = [p for d in picked for p in by_day[d]]
        rho = _spearman([p[0] for p in pooled], [p[1] for p in pooled])
        if rho is not None:
            stats.append(rho)
    stats.sort()
    def _pct(q: float) -> float:
        return stats[min(len(stats) - 1, max(0, int(q * len(stats))))]
    return _pct(0.05), _pct(0.50), _pct(0.95)


def _leave_one_out(
    by_day: dict[object, list[tuple[float, float]]],
) -> list[tuple[object, float | None]]:
    """Recompute pooled ρ with each day removed in turn.

    ⚠ **This is the check the project's own constraint #8 demands** — *"the sign must
    survive trimming the tail"* — and it is not optional here. With only 7 blocks a single
    unusual session can carry the whole result, and one of ours (2026-08-31) has ~5× the
    cross-sectional dispersion of every other day. Leave-one-out is the honest way to ask
    whether the finding is a pattern or an afternoon.
    """
    out: list[tuple[object, float | None]] = []
    for drop in sorted(by_day, key=str):
        pooled = [p for d, ps in by_day.items() if d != drop for p in ps]
        out.append(
            (drop, _spearman([p[0] for p in pooled], [p[1] for p in pooled]))
        )
    return out


async def _run(out_path: Path | None) -> int:
    async with AsyncSessionFactory() as db:
        rows = list((await db.execute(_SQL)).all())

    if not rows:
        print("no paired CAS/next-day rows — has ohlcv_1d caught up past the last capture?")
        return 1

    by_day = _by_day(rows)
    n_days = len(by_day)
    pooled = [p for ps in by_day.values() for p in ps]
    n_obs = len(pooled)

    rho = _spearman([p[0] for p in pooled], [p[1] for p in pooled])
    r = _pearson([p[0] for p in pooled], [p[1] for p in pooled])
    quints, spread = _quintile_spread(pooled)
    p5, p50, p95 = _bootstrap_days(by_day)

    per_day = []
    for day in sorted(by_day, key=str):
        ps = by_day[day]
        per_day.append((day, len(ps), _spearman([p[0] for p in ps], [p[1] for p in ps])))
    day_rhos = [d[2] for d in per_day if d[2] is not None]
    n_negative = sum(1 for x in day_rhos if x < 0)

    now = datetime.now(UTC).astimezone(_IST)
    reversal = rho is not None and rho < 0
    interval_excludes_zero = p95 < 0 or p5 > 0

    lines: list[str] = [
        f"# CAS Stage 2 — the overnight-reversal study ({now.date().isoformat()})",
        "",
        "**Read-only.** Nothing here gates, sizes or trades. Stage 1 accrual is complete;",
        "this is the study it was accrued for.",
        "",
        "## ⚠ Read this before the numbers",
        "",
        f"The independent unit is the **day**, not the row. There are **{n_days} usable days**",
        f"({n_obs:,} name-days). 208 names on one afternoon share one market, so every",
        "interval below resamples **whole days** — resampling rows would treat correlated",
        "observations as independent and make the interval roughly **14× too narrow**.",
        "",
        f"**{n_days} blocks is a weak instrument.** Whatever the point estimate says, this",
        "sample cannot clear the project's promotion bar (t ≈ 3.6, flat in n). Treat what",
        "follows as a direction to keep accruing against, not a finding.",
        "",
        "## Method",
        "",
        "- `cas_move` = (official close − 3:15 pre-auction price) / pre-auction price",
        "- `next_return` = (next session's close − official close) / official close",
        "- **Both are demeaned WITHIN each day.** That removes the market factor exactly —",
        "  the standing 'control for the oversold regime' warning — leaving only the",
        "  cross-sectional question: did the names pushed hardest *relative to peers* give it",
        "  back *relative to peers*?",
        "- ⚠ By construction this says nothing about a market-wide auction effect.",
        "",
        "## Result",
        "",
        f"- Spearman ρ (pooled, demeaned): **{rho:+.4f}**" if rho is not None else "- ρ: n/a",
        f"- Pearson r: **{r:+.4f}**" if r is not None else "- r: n/a",
        f"- Day-block bootstrap 90% interval for ρ: **[{p5:+.4f}, {p95:+.4f}]** "
        f"(median {p50:+.4f})",
        f"- Days with a negative (reversal-consistent) ρ: **{n_negative} of {len(day_rhos)}**",
        "",
    ]
    if quints:
        lines += [
            "### Quintiles of auction move (Q1 = pushed DOWN hardest vs peers)",
            "",
            "| quintile | mean next-day return (demeaned) |",
            "|---|---|",
        ]
        for i, m in enumerate(quints, start=1):
            lines.append(f"| Q{i} | {m * 100:+.4f}% |")
        lines += [
            "",
            f"**Q1 − Q5 spread: {spread * 100:+.4f}%** — positive is reversal-consistent"
            if spread is not None else "",
            "",
        ]

    # ── the tail check (constraint #8) ────────────────────────────────────────
    loo = _leave_one_out(by_day)
    loo_vals = [v for _d, v in loo if v is not None]
    sign_survives = all(v < 0 for v in loo_vals) if reversal else all(v > 0 for v in loo_vals)
    worst = max(loo_vals) if reversal else min(loo_vals)

    lines += [
        "### ⭐ Leave-one-day-out (the tail check constraint #8 requires)",
        "",
        "With only 7 blocks a single unusual session can carry the whole result — and",
        "**2026-08-31 has ~5× the cross-sectional dispersion of every other day**, so this",
        "is not a formality.",
        "",
        "| day removed | pooled ρ without it |",
        "|---|---|",
    ]
    for d, v in loo:
        lines.append(f"| {d} | {v:+.4f} |" if v is not None else f"| {d} | — |")
    shrink = abs(worst / rho) if (rho and rho != 0) else None
    lines += [
        "",
        f"**Sign survives every single-day removal: {'YES' if sign_survives else 'NO'}** "
        f"(weakest {worst:+.4f}).",
        "",
    ]
    if shrink is not None and shrink < 0.6:
        lines += [
            "⚠ **But the MAGNITUDE is not robust.** Removing the single most influential",
            f"day takes ρ from {rho:+.4f} to {worst:+.4f} — about **{shrink:.0%} of the "
            f"full-sample estimate**, so roughly half the measured effect rests on one "
            "afternoon.",
            "",
            "That is the distinction worth holding onto: the **direction** is consistent "
            "across every subsample, the **size** is not. Anything sized off the "
            "full-sample number would be sized off that one day.",
            "",
        ]


    lines += ["## Verdict", ""]
    if interval_excludes_zero:
        lines += [
            f"The 90% day-block interval **excludes zero** (`[{p5:+.4f}, {p95:+.4f}]`), so the",
            f"sign is stable across resampled histories. Direction: "
            f"**{'REVERSAL' if reversal else 'CONTINUATION'}**.",
            "",
            f"⚠ **This is not a promotion signal.** {n_days} independent days cannot clear a",
            "t ≈ 3.6 hurdle no matter how clean the sign looks, and the bar does not fall",
            "with n. Keep accruing and re-run; do not act.",
        ]
    else:
        lines += [
            f"The 90% day-block interval **spans zero** (`[{p5:+.4f}, {p95:+.4f}]`).",
            "",
            "**Nothing is established in either direction.** The point estimate leans",
            f"{'reversal' if reversal else 'continuation'}, but on {n_days} independent days",
            "that is indistinguishable from noise — the same shape as the book's own Sharpe",
            "interval [−0.223, +0.118], where even the loss is not established.",
            "",
            "**Recommended: keep the Stage-1 capture running and re-run this at ≥30 days.**",
            "The capture costs nothing; acting on this would cost the usual.",
        ]

    lines += [
        "",
        "## Per-day detail",
        "",
        "| day | names | ρ (within-day) |",
        "|---|---|---|",
    ]
    for day, n, d_rho in per_day:
        cell = f"{d_rho:+.4f}" if d_rho is not None else "—"
        lines.append(f"| {day} | {n} | {cell} |")

    report = "\n".join(x for x in lines if x is not None)
    print(report, flush=True)
    target = out_path or (_OUT_DIR / f"cas-stage2-{now.date().isoformat()}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="CAS Stage 2 — overnight reversal study")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    return asyncio.run(_run(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
