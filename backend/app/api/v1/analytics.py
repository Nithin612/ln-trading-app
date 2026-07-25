"""Outcome analytics API (Phase 6 — per-style hit-rate / expectancy).

GET /analytics/outcomes — aggregates the tick-level signal_outcomes (slice 3.6)
by trading style. Read-only and cohorted at OUTCOME_EPOCH; empty until live
outcomes accrue, then feeds the Phase-6 outcome dashboards. Pure observability —
never touches scoring, sizing, gating, or backtests.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile import PROFILE_STYLES
from app.services.signal_outcomes import OUTCOME_EPOCH

router = APIRouter(prefix="/analytics", tags=["analytics"])


class OutcomeStyleStats(BaseModel):
    style: str
    total: int          # cohorted outcomes for this style
    entered: int        # entry zone was touched
    wins: int           # tp_first
    losses: int         # sl_first
    no_entry: int       # expired_untouched
    timed_out: int      # expired_open (entered, neither SL nor TP)
    pending: int        # open + entry_touched (not yet resolved)
    sample: int         # resolved = wins + losses + no_entry + timed_out
    hit_rate: float | None        # wins / (wins + losses)
    entry_rate: float | None      # entered / total
    avg_return_pct: float | None  # mean signals.outcome_pnl_pct (expectancy per signal)


class OutcomeAnalyticsResponse(BaseModel):
    epoch: datetime
    total_outcomes: int
    styles: list[OutcomeStyleStats]


# Fixed tables, bind-parameterized value — no dynamic identifiers.
_AGG_SQL = text("""
    SELECT p.style AS style,
           count(*) AS total,
           count(*) FILTER (WHERE o.entry_touched_at IS NOT NULL) AS entered,
           count(*) FILTER (WHERE o.status = 'tp_first') AS wins,
           count(*) FILTER (WHERE o.status = 'sl_first') AS losses,
           count(*) FILTER (WHERE o.status = 'expired_untouched') AS no_entry,
           count(*) FILTER (WHERE o.status = 'expired_open') AS timed_out,
           count(*) FILTER (WHERE o.status IN ('open', 'entry_touched')) AS pending,
           avg(s.outcome_pnl_pct) FILTER (WHERE s.outcome_pnl_pct IS NOT NULL) AS avg_return
    FROM signal_outcomes o
    JOIN signals s ON s.id = o.signal_id
    JOIN strategy_profiles p ON p.id = s.profile_id
    WHERE s.created_at >= :epoch
    GROUP BY p.style
""")


@router.get("/outcomes", response_model=OutcomeAnalyticsResponse)
async def outcome_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> OutcomeAnalyticsResponse:
    """Per-style outcome summary. Every style is returned (zeros when it has no
    cohorted outcomes yet) so the dashboard renders a stable grid."""
    rows = (await db.execute(_AGG_SQL, {"epoch": OUTCOME_EPOCH})).mappings().all()
    by_style = {r["style"]: r for r in rows}

    styles: list[OutcomeStyleStats] = []
    total_outcomes = 0
    for style in PROFILE_STYLES:
        r = by_style.get(style)
        if r is None:
            styles.append(
                OutcomeStyleStats(
                    style=style, total=0, entered=0, wins=0, losses=0, no_entry=0,
                    timed_out=0, pending=0, sample=0, hit_rate=None, entry_rate=None,
                    avg_return_pct=None,
                )
            )
            continue
        total = int(r["total"])
        entered = int(r["entered"])
        wins = int(r["wins"])
        losses = int(r["losses"])
        no_entry = int(r["no_entry"])
        timed_out = int(r["timed_out"])
        decided = wins + losses
        sample = decided + no_entry + timed_out
        total_outcomes += total
        styles.append(
            OutcomeStyleStats(
                style=style,
                total=total,
                entered=entered,
                wins=wins,
                losses=losses,
                no_entry=no_entry,
                timed_out=timed_out,
                pending=int(r["pending"]),
                sample=sample,
                hit_rate=(wins / decided) if decided else None,
                entry_rate=(entered / total) if total else None,
                avg_return_pct=(float(r["avg_return"]) if r["avg_return"] is not None else None),
            )
        )
    return OutcomeAnalyticsResponse(
        epoch=OUTCOME_EPOCH, total_outcomes=total_outcomes, styles=styles
    )
