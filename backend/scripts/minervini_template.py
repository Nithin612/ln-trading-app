"""Q3.6 — the Minervini trend template: does it separate our outcomes, or is it dropped?

    uv run python scripts/minervini_template.py

The cycle-2 entry checklist accepts **either** answer — *"reading-derived candidates tested
or explicitly dropped"* — so the goal here is a decision, not a defence.

## Why this is not simply "a ninth gate"

Gating was closed as a programme on 2026-09-04: eight shadow gates, two refuted promotions,
best survivor at t ≈ 0.41. But the template is a different SHAPE from those eight. They
partition signals the engine already produced; the template is a **precondition on the
universe** — it changes which names are eligible to generate a signal at all.

⚠ **That distinction has to be argued, not assumed**, and it does not exempt the template
from the bar. If it partitions our existing trades and shows nothing, the honest reading is
that it fails as a *filter on what we actually traded* — which is the only question this
data can answer.

## The template (Minervini's eight conditions)

    1. close > SMA150 and close > SMA200
    2. SMA150 > SMA200
    3. SMA200 rising over ~1 month
    4. SMA50 > SMA150 and SMA50 > SMA200
    5. close > SMA50
    6. close >= 1.30 x 52-week low
    7. close >= 0.75 x 52-week high   (within 25% of the high)
    8. relative-strength rank >= 70

⚠ **Condition 8 is an APPROXIMATION here** and is labelled as such: Minervini's RS rank is
against the whole market from a specific vendor. We compute the stock's 6-month return
percentile **within the set of names we traded**, which is a much smaller and
self-selected universe. Reported separately so the 1–7 result can be read without it.

⚠ **NO LOOK-AHEAD.** Every condition is computed from bars strictly BEFORE the entry date
(hard constraint #3: compute on candle N, valid from N+1). A template evaluated on the
entry bar itself would be reading the day it is meant to predict.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

_POSITIONS = text(
    """
    SELECT p.id, p.stock_id, s.symbol, p.opened_at::date AS entry_date,
           p.avg_entry_price, p.quantity, p.realized_pnl,
           (p.realized_pnl / NULLIF(p.quantity * p.avg_entry_price, 0)) AS ret
    FROM positions p
    JOIN stocks s ON s.id = p.stock_id
    WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
    ORDER BY p.opened_at
    """
)

#: STRICTLY BEFORE the entry date — `time::date < :entry`. Constraint #3.
_BARS = text(
    """
    SELECT time::date AS d, close
    FROM ohlcv_1d
    WHERE stock_id = :sid AND time::date < :entry
    ORDER BY time DESC
    LIMIT 280
    """
)


@dataclass
class Check:
    symbol: str
    entry_date: date
    ret: float
    pnl: float
    conds: dict[str, bool]
    rs_6m: float | None = None

    @property
    def passes_1_7(self) -> bool:
        return all(self.conds.values())


def _sma(closes: list[float], n: int) -> float | None:
    """`closes` is newest-first."""
    return statistics.fmean(closes[:n]) if len(closes) >= n else None


def _evaluate(closes: list[float]) -> tuple[dict[str, bool], float | None] | None:
    """Conditions 1–7 plus the 6-month return, from newest-first closes before entry."""
    if len(closes) < 260:
        return None
    px = closes[0]  # the last close BEFORE the entry date
    sma50, sma150, sma200 = _sma(closes, 50), _sma(closes, 150), _sma(closes, 200)
    if sma50 is None or sma150 is None or sma200 is None:
        return None
    # SMA200 one month ago: the same 200-window shifted back 21 trading days.
    sma200_prev = statistics.fmean(closes[21:221])
    hi52, lo52 = max(closes[:252]), min(closes[:252])
    r6m = (px / closes[126] - 1.0) if len(closes) > 126 and closes[126] else None

    return (
        {
            "1 close>SMA150,SMA200": px > sma150 and px > sma200,
            "2 SMA150>SMA200": sma150 > sma200,
            "3 SMA200 rising": sma200 > sma200_prev,
            "4 SMA50>SMA150,SMA200": sma50 > sma150 and sma50 > sma200,
            "5 close>SMA50": px > sma50,
            "6 >=30% above 52w low": px >= 1.30 * lo52,
            "7 within 25% of 52w high": px >= 0.75 * hi52,
        },
        r6m,
    )


def _bucket(rows: list[Check]) -> str:
    if not rows:
        return "| 0 | — | — | — |"
    mean_ret = statistics.fmean(r.ret for r in rows) * 100
    wins = sum(1 for r in rows if r.pnl > 0)
    total = sum(r.pnl for r in rows)
    return (
        f"| {len(rows)} | {mean_ret:+.3f}% | {100 * wins / len(rows):.0f}% | ₹{total:,.0f} |"
    )


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        positions = list((await db.execute(_POSITIONS)).all())
        checks: list[Check] = []
        skipped = 0
        for p in positions:
            if p.ret is None:
                skipped += 1
                continue
            bars = list(
                (await db.execute(_BARS, {"sid": p.stock_id, "entry": p.entry_date})).all()
            )
            closes = [float(b.close) for b in bars]
            ev = _evaluate(closes)
            if ev is None:
                skipped += 1
                continue
            conds, r6m = ev
            checks.append(
                Check(
                    symbol=p.symbol, entry_date=p.entry_date, ret=float(p.ret),
                    pnl=float(p.realized_pnl), conds=conds, rs_6m=r6m,
                )
            )

    if not checks:
        print("no evaluable positions — need >=260 daily bars before each entry")
        return 1

    # Condition 8, approximated: 6-month return percentile WITHIN THE TRADED SET.
    ranked = sorted((c for c in checks if c.rs_6m is not None), key=lambda c: c.rs_6m or 0)
    rs_rank: dict[str, float] = {
        f"{c.symbol}|{c.entry_date}": 100.0 * i / max(1, len(ranked) - 1)
        for i, c in enumerate(ranked)
    }

    passed = [c for c in checks if c.passes_1_7]
    failed = [c for c in checks if not c.passes_1_7]
    passed_8 = [
        c for c in passed if rs_rank.get(f"{c.symbol}|{c.entry_date}", 0) >= 70
    ]

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# Q3.6 — the Minervini trend template on our closed book ({now.date().isoformat()})",
        "",
        "The cycle-2 checklist accepts **either** answer — *tested or explicitly dropped* —",
        "so this is written to reach a decision, not to defend the idea.",
        "",
        f"**{len(checks)} closed positions evaluable** ({skipped} skipped for want of 260",
        "daily bars before entry or a defined return).",
        "",
        "⚠ **No look-ahead:** every condition is computed from bars strictly BEFORE the entry",
        "date (constraint #3). A template read on the entry bar would be using the day it is",
        "meant to predict.",
        "",
        "## Conditions 1–7 (the price/moving-average structure)",
        "",
        "| cohort | n | mean return | win | total |",
        "|---|--:|--:|--:|--:|",
        f"| **passes all of 1–7** {_bucket(passed)}",
        f"| **fails at least one** {_bucket(failed)}",
        "",
        "### Which condition bites, one at a time",
        "",
        "| condition | n passing | mean return of passers |",
        "|---|--:|--:|",
    ]
    for cond in checks[0].conds:
        subset = [c for c in checks if c.conds[cond]]
        mr = (
            f"{statistics.fmean(c.ret for c in subset) * 100:+.3f}%" if subset else "—"
        )
        out.append(f"| {cond} | {len(subset)} | {mr} |")

    out += [
        "",
        "## Condition 8 (relative strength) — approximated",
        "",
        "⚠ Minervini ranks against the **whole market** from a specific vendor. This ranks",
        "the 6-month return **within the names we traded** — a smaller, self-selected",
        "universe — so it is a weaker test and is reported separately.",
        "",
        "| cohort | n | mean return | win | total |",
        "|---|--:|--:|--:|--:|",
        f"| **passes 1–7 AND RS≥70** {_bucket(passed_8)}",
        "",
        "## Verdict",
        "",
    ]

    if not passed or not failed:
        # ⚠ An empty cohort is NOT the same as an uninformative split, and the first draft
        # of this script conflated them ("does not partition ⇒ drop"). A 0-of-N result says
        # something much stronger: the template and our engine select DISJOINT sets. That
        # cannot be settled on trades we took — there is no passing cohort to compare —
        # but it is emphatically not "tells us nothing".
        binding = sorted(
            (sum(1 for c in checks if c.conds[k]), k) for k in checks[0].conds
        )[:3]
        out += [
            f"⛔ **NOT ONE of the {len(checks)} evaluable positions passes all seven "
            "conditions.**",
            "",
            "That is not an uninformative split — it is a **disjoint** one. The template and",
            "our engine are selecting from effectively non-overlapping sets, so this book",
            "cannot test it: there is no passing cohort to compare a failing one against.",
            "",
            "**The conditions that bind hardest:**",
            "",
        ]
        for n_pass, cond in binding:
            out.append(f"- `{cond}` — only **{n_pass} of {len(checks)}** entries pass")
        out += [
            "",
            "⭐ **Read that as a finding about OUR engine, not about Minervini.** The binding",
            "conditions are the trend-structure ones, so a large majority of the names we",
            "entered were in a structural DOWNTREND on his definition — trading below or",
            "against their own long moving averages. Our selection is not a weaker version",
            "of this template; it is close to its opposite.",
            "",
            f"On these {len(checks)} positions that book made "
            f"**₹{sum(c.pnl for c in checks):,.0f}**.",
            "",
            "**⇒ NOT a clean drop, and NOT a gate either.** The template makes a claim about",
            "which names should be *eligible*, and the only honest test is a **universe-level",
            "corpus rerun** — does applying it change what the engine generates, and is that",
            "set better? That is a real piece of work, not a shadow gate, and it is the",
            "correct next step if anyone wants to pursue it.",
            "",
            "⚠ **It must NOT be shipped as a ninth selection gate.** On this book it would",
            "block 100% of entries, which is not a filter — it is a different strategy",
            "wearing a filter's clothes.",
        ]
    else:
        diff = (
            statistics.fmean(c.ret for c in passed)
            - statistics.fmean(c.ret for c in failed)
        ) * 100
        n_small = min(len(passed), len(failed))
        out += [
            f"Passers beat failers by **{diff:+.3f} pp** of mean return "
            f"({len(passed)} vs {len(failed)}).",
            "",
            f"⚠ **The smaller cohort is n = {n_small}.** Nothing at this size approaches the",
            "project's t ≈ 3.6 bar, and that bar does not fall with more data. Read the",
            "direction, not the magnitude.",
            "",
        ]
        if diff > 0:
            out += [
                "**⇒ The direction is favourable, so this is NOT a clean drop.** The honest",
                "next step is a *universe-level* test — does the template change which names",
                "generate signals at all — because that is the claim it actually makes, and",
                "partitioning trades we already took cannot test it. That is a corpus rerun,",
                "not a gate.",
                "",
                "⚠ **It must not be shipped as a ninth selection gate on this evidence.**",
                "That is precisely the move that was closed as a programme on 2026-09-04.",
            ]
        else:
            out += [
                "**⇒ DROP.** The template's passers did *worse* than its failers on our book,",
                "which is the opposite of its claim. The checklist accepts an explicit drop,",
                "and this is one.",
            ]

    out += [
        "",
        "## ⚠ What this cannot tell you",
        "",
        "- **These are the names our engine chose**, not a cross-section. The template could",
        "  work as a universe filter and be invisible here, which is exactly why a favourable",
        "  direction argues for a corpus rerun rather than a gate.",
        "- **Condition 8 is approximated** within the traded set (see above).",
        "- **~3 years of daily history**, all of it one broad regime.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"minervini-template-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
