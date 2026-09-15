"""V6 / A5 — the built-and-STARVED alarm: a table a consumer depends on, holding nothing.

⭐ **This is one of the project's two recurring defect shapes**, and the reason A5 asks for
it is that we have hit it repeatedly: `kite_instruments` empty before U1 (so the live
worker subscribed to nothing and the universe rule judged against an empty dump),
`categories` empty, `strategy_profiles` empty. Each time the code was correct, wired and
green — it simply had no data to act on, and **nothing anywhere said so.**

⭐⭐ **THE CASE THAT PROVES IT IS LIVE RIGHT NOW.** `strategy_profiles` is seeded by
migration `o1p2q3r4s5t6_phase2_profile_seeds`, and the dev database is at head — yet it
holds **zero rows**. The 2026-09-07 rebuild restored the SCHEMA with alembic already
marked applied, so the data seed never re-ran and cannot: `alembic upgrade` is a no-op on
a revision it thinks is done. Four production call sites read that table
(`profiles/pipeline`, `broker/provisional`, `api/v1/suggestions`, `daily_report`), so the
style engines have been structurally unable to produce anything for eight days, at head,
with a green suite. **A migration that seeds reference data is invisible to every check we
own once it has been marked applied.**

⚠ **The registry is DECLARED, not derived, and that is deliberate.** "Empty" alone means
nothing: 21 of 57 tables are empty in dev today and most are correctly so — nobody has
created a watchlist, written a journal entry or recorded a corporate action. The
distinction between *starved* and *not used yet* is a fact about intent that no query can
recover. Each entry therefore names **what fills it** (so the alarm carries its own remedy)
and **what consumes it** — A5's "what observes this?" column, which it calls the cheapest
version of this whole idea because it would have caught all five instances at planning time.

⛔ **Tables that already have a dedicated alarm are excluded on purpose.** `ohlcv_1d` and
`fo_bhavcopy` belong to `feed_health`, `nse_holidays` to `calendar_health`,
`universe_snapshot` to `universe_health`. Restating their emptiness here would be a second
instrument for the same fact, which is how a reader learns that two alarms mean one problem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from app.services.notifier import Notification

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumedTable:
    """A table whose EMPTINESS is a fault rather than a state."""

    table: str
    #: The remedy, in the imperative. An alarm that says "X is empty" and stops has moved
    #: the investigation, not started it.
    populated_by: str
    #: A5's "what observes this?" — the consumers that silently do nothing when it is
    #: empty. Naming them is what turns a row count into a consequence.
    observed_by: tuple[str, ...]


#: ⚠ Every entry here was verified BOTH ways before it was added: a real consumer that
#: reads the table, and a real thing that fills it. A table with no consumer is not
#: starved, it is unused; a table with no populator is a design gap, not an alarm.
CONSUMED_TABLES: tuple[ConsumedTable, ...] = (
    ConsumedTable(
        table="strategy_profiles",
        populated_by=(
            "seeded by migration o1p2q3r4s5t6_phase2_profile_seeds — re-run its INSERT "
            "directly; `alembic upgrade` will NOT replay a revision already marked applied"
        ),
        observed_by=(
            "profiles/pipeline.py",
            "broker/provisional.py",
            "api/v1/suggestions.py",
            "services/daily_report.py",
        ),
    ),
    ConsumedTable(
        table="kite_instruments",
        populated_by="the sync-kite-instruments beat (02:30 UTC); the dump is public",
        observed_by=(
            "live_worker subscription",
            "universe_rule KITE_TRADABLE term",
        ),
    ),
    ConsumedTable(
        table="stocks",
        populated_by="scripts/seed_stocks.py (public NSE CSVs, no auth)",
        observed_by=("everything — the master every other table joins to",),
    ),
)


@dataclass(frozen=True)
class Starvation:
    entry: ConsumedTable
    rows: int | None  # None = the count could not be taken

    @property
    def is_starved(self) -> bool:
        return self.rows == 0

    @property
    def is_measurable(self) -> bool:
        return self.rows is not None


async def check_starvation(db: AsyncSession) -> list[Starvation]:
    """Row counts for every declared consumed table. Read-only, and NEVER raises — a
    health probe that can take down its own report has inverted its purpose."""
    out: list[Starvation] = []
    for entry in CONSUMED_TABLES:
        try:
            async with db.begin_nested():
                # The table name comes from the module-level registry above, never from a
                # caller, so there is no untrusted identifier to guard.
                rows = (
                    await db.execute(text(f'SELECT count(*) FROM "{entry.table}"'))  # noqa: S608
                ).scalar()
        except Exception:  # noqa: BLE001 — a health probe must not raise into its report
            log.exception("starvation probe failed for %s", entry.table)
            out.append(Starvation(entry, None))
            continue
        s = Starvation(entry, int(rows or 0))
        if s.is_starved:
            log.warning(
                "STARVED TABLE: %s is EMPTY — consumed by %s; %s",
                entry.table, ", ".join(entry.observed_by), entry.populated_by,
            )
        out.append(s)
    return out


def to_notification(rows: list[Starvation]) -> Notification | None:
    from app.services.notifier import Level, Notification

    starved = [r for r in rows if r.is_starved]
    if not starved:
        return None
    lines = []
    for s in starved:
        lines.append(
            f"{s.entry.table} is EMPTY — read by {', '.join(s.entry.observed_by)}"
        )
        lines.append(f"    REMEDY: {s.entry.populated_by}")
    lines.append(
        "these consumers do not fail when the table is empty; they quietly do nothing, "
        "which is why this needs its own alarm"
    )
    return Notification(
        event="starved_table",
        level=Level.ERROR,
        title=f"STARVED TABLE — {starved[0].entry.table} is empty",
        lines=lines,
    )


def render_lines(rows: list[Starvation]) -> list[str]:
    if not rows:
        return []
    starved = [r for r in rows if r.is_starved]
    if not starved:
        measured = [r for r in rows if r.is_measurable]
        summary = " · ".join(f"{r.entry.table} {r.rows:,}" for r in measured)
        return [f"> ✅ **Consumed tables populated**: {summary}.", ""] if measured else []
    out = [
        "> ## ⚠️ STARVED TABLE (live — as of report generation)",
        ">",
        "> A table a consumer depends on is EMPTY. The code is correct and wired; it "
        "simply has nothing to act on, and the consumers below do not fail — **they "
        "quietly do nothing**, which is why this needs an alarm of its own.",
        ">",
    ]
    for s in starved:
        out.append(
            f"> - **`{s.entry.table}`** is empty — read by "
            f"{', '.join(f'`{c}`' for c in s.entry.observed_by)}."
        )
        out.append(f">   REMEDY: {s.entry.populated_by}")
    out.append("")
    return out
