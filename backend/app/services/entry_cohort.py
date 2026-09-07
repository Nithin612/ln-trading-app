"""Entry-cohort (vintage) attribution — was the SELECTION good, not just the exit day?

The daily report has always grouped P&L by **exit** date. That answers "what did today
realise", which is what accounting needs, and it makes one question unanswerable:

    "We picked 5 names on Aug 26. Were those picks any good?"

Under exit-date grouping, Aug 26's five decisions land on five different report days, mixed
in with decisions made on five other days. The signal about *selection quality* is smeared
out until it is invisible.

Grouping by **entry** date instead — the vintage a fund manager would use — makes it
legible immediately. On the live book it separated a run of bad selection days
(2026-08-26 at 25% win, −₹8,835) from good ones (2026-08-28 at 100% of resolved, +₹5,215)
that the exit-date view could not distinguish.

**Given the entry leak is the demonstrated problem, this is the view that matters.**

## The one rule that keeps it honest

⚠ **A cohort is not final until every one of its picks has resolved.** A day whose five
trades are all still open has realised ₹0 — and printing that as "flat" would be a lie
about a cohort sitting at −₹4,593 unrealised. So resolved and open are ALWAYS reported
separately, and a cohort with anything open is marked in-flight. Merging them into one
number is the single way to make this view mislead.

⚠ **No schema change.** `positions.opened_at` already exists; this is a grouping, not new
data. Nothing about how a trade is recorded or priced changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.trading import Position

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

_Q = Decimal("0.01")


@dataclass(frozen=True)
class Cohort:
    """One entry day's picks, and how they have turned out so far."""

    entry_day: date
    picks: int
    resolved: int
    still_open: int
    realized: Decimal
    open_mtm: Decimal
    wins: int

    @property
    def in_flight(self) -> bool:
        """Anything still open means this cohort's verdict is provisional."""
        return self.still_open > 0

    @property
    def win_pct(self) -> float | None:
        """Over RESOLVED picks only. `None` when nothing has resolved yet.

        Deliberately not "0%" — a cohort with nothing closed has no win rate, and printing
        zero would read as "every pick lost". The undefined/measured distinction, same as
        `app/core/ratios.py` draws for degenerate ratios.
        """
        if self.resolved == 0:
            return None
        return 100.0 * self.wins / self.resolved

    @property
    def total_so_far(self) -> Decimal:
        """Realised + open mark. ⚠ A MIXED number: one part banked, one part a mark that
        can still move. Useful as a running total, never as a result."""
        return (self.realized + self.open_mtm).quantize(_Q)


async def load_cohorts(
    db: AsyncSession,
    *,
    since: date,
    user_id: int | None = None,
    mode: str = "paper",
) -> list[Cohort]:
    """One `Cohort` per entry day, oldest first.

    Grouped in Python rather than SQL because the aggregation is small (one row per
    trading day) and doing it here keeps the resolved/open split explicit instead of
    hiding it in `FILTER` clauses that a later reader might collapse.
    """
    stmt = select(Position).where(
        Position.mode == mode,
        Position.opened_at >= since,
    )
    if user_id is not None:
        stmt = stmt.where(Position.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()

    buckets: dict[date, list[Position]] = {}
    for p in rows:
        buckets.setdefault(p.opened_at.date(), []).append(p)

    out: list[Cohort] = []
    for day in sorted(buckets):
        picks = buckets[day]
        closed = [p for p in picks if p.closed_at is not None]
        openp = [p for p in picks if p.closed_at is None]
        out.append(
            Cohort(
                entry_day=day,
                picks=len(picks),
                resolved=len(closed),
                still_open=len(openp),
                realized=sum(
                    (Decimal(str(p.realized_pnl)) for p in closed), Decimal(0)
                ).quantize(_Q),
                open_mtm=sum(
                    (
                        Decimal(str(p.unrealized_pnl))
                        for p in openp
                        if p.unrealized_pnl is not None
                    ),
                    Decimal(0),
                ).quantize(_Q),
                wins=sum(1 for p in closed if Decimal(str(p.realized_pnl)) > 0),
            )
        )
    return out


def render_lines(cohorts: list[Cohort], *, limit: int = 14) -> list[str]:
    """Daily-report block: the most recent `limit` entry days, newest last.

    Resolved and open are separate columns on purpose (see the module docstring). The
    header says so, because a reader who merges them mentally gets a wrong answer and the
    table cannot stop them — only the caption can.
    """
    if not cohorts:
        return []
    recent = cohorts[-limit:]
    out = [
        "",
        "## Selection quality by ENTRY day (vintage attribution)",
        "",
        "Grouped by the day the picks were MADE, not the day they closed — so this answers",
        "*\"were that day's selections any good?\"*, which exit-date grouping cannot.",
        "",
        "⚠ **`realised` and `open` are separate on purpose.** A cohort with picks still open",
        "has a PROVISIONAL verdict; its realised figure is not its result. Rows marked",
        "`⏳` are still in flight.",
        "",
        "| entry day | picks | resolved | open | realised | open mark | win% |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for c in recent:
        flag = " ⏳" if c.in_flight else ""
        win = f"{c.win_pct:.0f}%" if c.win_pct is not None else "—"
        out.append(
            f"| {c.entry_day}{flag} | {c.picks} | {c.resolved} | {c.still_open} | "
            f"₹{c.realized:,.0f} | ₹{c.open_mtm:,.0f} | {win} |"
        )

    settled = [c for c in recent if not c.in_flight]
    if settled:
        best = max(settled, key=lambda c: c.realized)
        worst = min(settled, key=lambda c: c.realized)
        if best.entry_day != worst.entry_day:
            out += [
                "",
                f"- Best fully-resolved cohort: **{best.entry_day}** ₹{best.realized:,.0f}"
                + (f" ({best.win_pct:.0f}% win)" if best.win_pct is not None else ""),
                f"- Worst fully-resolved cohort: **{worst.entry_day}** ₹{worst.realized:,.0f}"
                + (f" ({worst.win_pct:.0f}% win)" if worst.win_pct is not None else ""),
            ]
    else:
        out += [
            "",
            "- ⏳ **No cohort in this window has fully resolved yet** — every row above is",
            "  provisional, and none of them is a result.",
        ]
    return out
