"""MCE slice 6 — is a news/sentiment veto buildable from the data we actually hold?

    uv run python scripts/news_veto_feasibility.py

**Run this BEFORE building slice 6, and re-run it when filings history deepens.**

The phase doc specifies slice 6 as: *extend `event_guard` to an earnings-blackout window +
rating-DOWNGRADE veto + severity/decay*. Each of those three clauses assumes a specific
fact about `corporate_filings`. This script checks each assumption against the live table
rather than against the spec, and reports which are true.

That order matters. A veto built on an assumption the data does not support does not fail
loudly — it silently never fires, and then *looks like protection* on every dashboard that
renders it. The existing 60-minute guard is already in that state, and nobody would have
known without counting.

## The three preconditions

1. **Rating direction is recoverable** — a downgrade veto that cannot tell a downgrade from
   an upgrade is not a veto.
2. **Earnings timing is known in advance** — a *blackout* is forward-looking. A cooldown
   after the fact is a different, weaker thing.
3. **Filings and signals actually coincide** — if no signal is ever near a filing, every
   variant of this gate is moot regardless of how well it is built.

⚠ Read-only. Gates nothing, changes nothing.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

_COVERAGE = text(
    """
    SELECT filing_type, COUNT(*) AS n,
           MIN(filing_time)::date AS first_seen,
           MAX(filing_time)::date AS last_seen
    FROM corporate_filings GROUP BY 1 ORDER BY 2 DESC
    """
)

_DIRECTION = text(
    """
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE (headline || ' ' || COALESCE(body,'')) ~* 'upgrad') AS up,
           COUNT(*) FILTER (WHERE (headline || ' ' || COALESCE(body,'')) ~* 'downgrad') AS down,
           COUNT(*) FILTER (WHERE COALESCE(body,'') ~* '^https?://') AS body_is_url
    FROM corporate_filings WHERE filing_type = 'rating_change'
    """
)

_COINCIDENCE = text(
    """
    WITH sig AS (
        SELECT id, stock_id, created_at FROM signals
        WHERE is_shadow IS FALSE AND created_at >= (
            SELECT MIN(filing_time) FROM corporate_filings
        )
    )
    SELECT
      (SELECT COUNT(*) FROM sig) AS signals,
      (SELECT COUNT(*) FROM sig s WHERE EXISTS (
          SELECT 1 FROM corporate_filings f
          WHERE f.stock_id = s.stock_id
            AND f.filing_type IN ('earnings','merger','rating_change')
            AND f.filing_time BETWEEN s.created_at - INTERVAL '1 hour' AND s.created_at
      )) AS hit_1h,
      (SELECT COUNT(*) FROM sig s WHERE EXISTS (
          SELECT 1 FROM corporate_filings f
          WHERE f.stock_id = s.stock_id
            AND f.filing_type IN ('earnings','merger','rating_change')
            AND f.filing_time BETWEEN s.created_at - INTERVAL '3 days' AND s.created_at
      )) AS hit_3d
    """
)

#: Headline shapes that reveal a filing is POST-facto rather than a forward notice. A
#: blackout needs to know an event is coming; "Outcome of ..." tells you it already went.
_POSTFACTO = text(
    """
    SELECT filing_type,
           COUNT(*) AS n,
           COUNT(*) FILTER (WHERE headline ~* '^outcome') AS post_facto,
           COUNT(*) FILTER (WHERE headline ~* '(clarification|delay|non-submission)')
             AS administrative
    FROM corporate_filings
    WHERE filing_type IN ('earnings','board_meeting')
    GROUP BY 1
    """
)


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        coverage = list((await db.execute(_COVERAGE)).all())
        direction = (await db.execute(_DIRECTION)).one()
        coincide = (await db.execute(_COINCIDENCE)).one()
        postfacto = list((await db.execute(_POSTFACTO)).all())

    total_filings = sum(r.n for r in coverage)
    now = datetime.now(UTC).astimezone(_IST)

    p1 = direction.down > 0
    p2 = any(r.n > (r.post_facto + r.administrative) for r in postfacto)
    p3 = coincide.hit_1h > 0

    out: list[str] = [
        f"# MCE slice 6 — news-veto feasibility ({now.date().isoformat()})",
        "",
        "**Checked before building.** The phase doc specifies slice 6 as *earnings-blackout +",
        "rating-DOWNGRADE veto + severity/decay*. Each clause assumes something about",
        "`corporate_filings`; this checks the assumptions against the live table.",
        "",
        "⚠ **Why check first:** a veto built on an assumption the data does not support does",
        "not fail loudly. It silently never fires, and then *looks like protection* wherever",
        "it is rendered.",
        "",
        f"**{total_filings:,} filings** on record.",
        "",
        "| type | rows | first | last |",
        "|---|--:|---|---|",
    ]
    out += [f"| {r.filing_type} | {r.n:,} | {r.first_seen} | {r.last_seen} |" for r in coverage]

    out += [
        "",
        "## Precondition 1 — is rating DIRECTION recoverable?",
        "",
        f"- `rating_change` rows: **{direction.total}**",
        f"- mention *upgrade*: **{direction.up}**",
        f"- mention *downgrade*: **{direction.down}**",
        f"- rows whose `body` is just a **URL**, not text: **{direction.body_is_url}** "
        f"of {direction.total}",
        "",
        f"**{'✅ satisfied' if p1 else '⛔ NOT satisfied'}.** "
        + (
            ""
            if p1
            else "The headline is a bare label (`Credit Rating`) and the body is a link to a "
            "PDF we do not parse, so the direction lives in a document we never read. A "
            "downgrade veto here would match **zero** rows — a gate that cannot fire."
        ),
        "",
        "## Precondition 2 — is earnings timing known IN ADVANCE?",
        "",
        "| type | rows | `Outcome of…` (post-facto) | administrative |",
        "|---|--:|--:|--:|",
    ]
    out += [
        f"| {r.filing_type} | {r.n:,} | {r.post_facto:,} | {r.administrative:,} |"
        for r in postfacto
    ]
    out += [
        "",
        f"**{'✅ satisfied' if p2 else '⛔ NOT satisfied'}.** "
        + (
            ""
            if p2
            else "`board_meeting` rows are *Outcome of Board Meeting* — they report a meeting "
            "that already happened. `earnings` rows are *Clarification / Delayed submission* "
            "— administrative notes ABOUT results, not the results. There is no forward "
            "earnings calendar here, so a **blackout** (which must anticipate) cannot be "
            "built; only a cooldown (which reacts) can."
        ),
        "",
        "## Precondition 3 — do filings and signals ever COINCIDE?",
        "",
        f"- signals minted since filings began: **{coincide.signals:,}**",
        f"- would be suppressed by the existing **1-hour** guard: **{coincide.hit_1h}**",
        f"- would be suppressed by a **3-day** window (72× wider): **{coincide.hit_3d}** "
        f"({100 * coincide.hit_3d / max(1, coincide.signals):.1f}%)",
        "",
        f"**{'✅ satisfied' if p3 else '⛔ NOT satisfied'}.** "
        + (
            ""
            if p3
            else "⭐ **The existing event guard has never fired.** Not once, across every "
            "signal minted since the filings feed started. Widening the window 72× still "
            "reaches under 1% of signals. Whatever is losing money on this book, it is not "
            "signals minted next to a corporate filing."
        ),
        "",
        "## Verdict",
        "",
    ]

    satisfied = sum([p1, p2, p3])
    if satisfied == 0:
        out += [
            "⛔ **NONE of the three preconditions holds. DEFER slice 6.**",
            "",
            "This is not 'the gate would be weak' — it is that two of its three clauses are",
            "**unimplementable** from data we hold, and the third has nothing to act on:",
            "",
            "1. the downgrade veto would match **0** rows;",
            "2. the blackout has no forward earnings dates to blackout *against*;",
            "3. the guard it extends has **never fired**.",
            "",
            "**Building severity/decay on top of a gate that fires zero times is decoration.**",
            "It would add a knob, a shadow sidecar and a line in the daily report, all",
            "reporting on an event that does not occur — and every one of those surfaces",
            "would read as protection.",
            "",
            "### What would change this answer",
            "",
            "- **A forward earnings calendar** (dates announced ahead), which makes a real",
            "  blackout possible. Not in `corporate_filings`; needs a source.",
            "- **Parsed rating documents**, or a feed carrying direction as a field.",
            "- **More history** — this is ~6 weeks. Re-run this script as it deepens; the",
            "  coincidence rate is the number to watch.",
            "",
            "### On the RSS + FinBERT alternative (review item A18)",
            "",
            "The external review proposed Google News RSS + FinBERT instead. That is a",
            "**different and much larger** proposal than the phase doc's slice 6, and it needs",
            "a decision rather than a build:",
            "",
            "- **`transformers` + `torch` is a locked-stack change** (~2 GB, GPU-adjacent). The",
            "  project's standing posture is 'adopt no new deps, stay lean'.",
            "- **It adds a live external dependency** on the signal path — a third-party feed",
            "  that can rate-limit, change shape, or go down.",
            "- ⚠ **Precondition 3 still applies to it.** If corporate filings never coincide",
            "  with our signals, the open question is whether *news* does — and that is",
            "  measurable far more cheaply than by installing a language model.",
            "",
            "**Recommended sequence:** answer the cheap question first (does adverse news",
            "coincide with our entries at all?), and only then decide whether it justifies the",
            "stack change.",
        ]
    else:
        out += [
            f"**{satisfied} of 3 preconditions hold.** Build only the clauses whose",
            "precondition is satisfied, and say in the code why the others are absent.",
        ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"news-veto-feasibility-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
