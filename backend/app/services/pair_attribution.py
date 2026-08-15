"""Pair attribution (Phase 6.5b slice 4) — shadow pair expectancy, the df-vs-adf verdict.

Read-only over resolved `pair_signals` (tp_first / sl_first / expired). Reports expectancy
(mean R, win rate, total R) split by ARM (df vs adf — the A/B this whole slice-set exists to
settle), by sector, and by half-life bucket. R is winsorized ±10 (a tiny-risk pair — entry_z
close to z_stop — can otherwise mint an outsized R; the same guard the single-name attribution
uses). Refuses to *rank* a cell below RANK_FLOOR (the n<20-style honesty precedent, relaxed to
5 because pairs are sparse). Mints nothing; measures.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pair import PairSignal

_R_WINSOR = 10.0
RANK_FLOOR = 5  # sparse pairs — don't RANK a cell below this n (but always report it)


@dataclass(frozen=True)
class PairRow:
    method: str
    sector: str | None
    half_life: float
    status: str  # tp_first | sl_first | expired
    outcome_r: float


@dataclass(frozen=True)
class PairCell:
    key: str
    n: int  # resolved signals in the cell
    decided: int  # tp_first + sl_first (win rate denominator)
    wins: int
    win_rate: float | None
    mean_r: float | None  # winsorized, over all resolved (expired marked-to-z counts)
    total_r: float
    ranked: bool


@dataclass(frozen=True)
class PairTable:
    dimension: str
    cells: list[PairCell]


@dataclass(frozen=True)
class PairAttribution:
    since: datetime | None
    total: int
    tables: list[PairTable]


def _winsor(r: float) -> float:
    return max(-_R_WINSOR, min(_R_WINSOR, r))


def _cell(key: str, rows: list[PairRow]) -> PairCell:
    decided = [r for r in rows if r.status in ("tp_first", "sl_first")]
    wins = sum(1 for r in decided if r.status == "tp_first")
    rs = [_winsor(r.outcome_r) for r in rows]  # every resolved row has an outcome_r
    return PairCell(
        key=key,
        n=len(rows),
        decided=len(decided),
        wins=wins,
        win_rate=(wins / len(decided)) if decided else None,
        mean_r=statistics.fmean(rs) if rs else None,
        total_r=sum(rs),
        ranked=len(rows) >= RANK_FLOOR,
    )


def _half_life_bucket(hl: float) -> str:
    if hl < 10:
        return "fast (<10)"
    if hl < 20:
        return "medium (10–20)"
    return "slow (≥20)"


def attribute_pair_rows(rows: list[PairRow]) -> list[PairTable]:
    def table(dim: str, keyfn: Callable[[PairRow], str]) -> PairTable:
        keys = sorted({keyfn(r) for r in rows})
        return PairTable(
            dimension=dim, cells=[_cell(k, [r for r in rows if keyfn(r) == k]) for k in keys]
        )

    return [
        table("Arm (df vs adf)", lambda r: r.method),
        table("Sector", lambda r: r.sector or "(none)"),
        table("Half-life", lambda r: _half_life_bucket(r.half_life)),
    ]


async def compute_pair_attribution(
    db: AsyncSession, *, since: datetime | None = None
) -> PairAttribution:
    """Resolved shadow pair signals as an expectancy attribution. Read-only."""
    stmt = select(
        PairSignal.method,
        PairSignal.sector,
        PairSignal.half_life,
        PairSignal.status,
        PairSignal.outcome_r,
    ).where(PairSignal.status != "open")
    if since is not None:
        stmt = stmt.where(PairSignal.created_at >= since)
    raw = (await db.execute(stmt)).all()
    rows = [
        PairRow(
            method=m,
            sector=s,
            half_life=float(hl),
            status=st,
            outcome_r=float(r) if r is not None else 0.0,
        )
        for m, s, hl, st, r in raw
    ]
    return PairAttribution(since=since, total=len(rows), tables=attribute_pair_rows(rows))


def render_markdown(attr: PairAttribution, *, day: date) -> str:
    out = [
        f"# Pair-trading attribution (shadow) — {day}",
        "",
        f"_Read-only. Expectancy of the RESOLVED shadow pair signals ({attr.total} resolved). "
        "The **Arm** table is the df-vs-adf A/B verdict. R winsorized ±10; a cell with n < "
        f"{RANK_FLOOR} is shown but not ranked. Mints nothing._",
        "",
    ]
    if attr.total == 0:
        out.append("_No resolved shadow pair signals yet — the arms accrue nightly; check back._")
        out.append("")
        return "\n".join(out) + "\n"
    for t in attr.tables:
        out += [
            f"## {t.dimension}",
            "",
            "| cell | n | decided | win% | mean R | total R | |",
            "|---|--:|--:|--:|--:|--:|---|",
        ]
        for c in t.cells:
            wr = f"{c.win_rate:.0%}" if c.win_rate is not None else "—"
            mr = f"{c.mean_r:+.3f}" if c.mean_r is not None else "—"
            flag = "" if c.ranked else "n<floor"
            out.append(
                f"| {c.key} | {c.n} | {c.decided} | {wr} | {mr} | {c.total_r:+.1f} | {flag} |"
            )
        out.append("")
    return "\n".join(out) + "\n"
