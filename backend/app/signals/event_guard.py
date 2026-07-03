"""Event guard — Phase 6.

Suppresses new signals for a stock when a high-impact corporate filing
(earnings, merger, rating change) was ingested within the last 60 minutes.

Technical analysis is invalidated during fundamental news events because
price action becomes driven by the news, not the chart structure.

Usage:
    guarded = await is_signal_suppressed(db, stock_id)
    if guarded.suppressed:
        return None   # skip signal generation
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.filing import HIGH_IMPACT_TYPES, CorporateFiling

_SUPPRESS_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class GuardResult:
    suppressed: bool
    reason: str | None = None
    suppressed_until: datetime | None = None


async def is_signal_suppressed(db: AsyncSession, stock_id: int) -> GuardResult:
    """Return GuardResult for the given stock.

    Checks the last 1 hour for any high-impact filings. If found, returns
    suppressed=True with details of the triggering filing.
    """
    cutoff = datetime.now(tz=UTC) - _SUPPRESS_WINDOW

    result = await db.execute(
        select(CorporateFiling)
        .where(
            CorporateFiling.stock_id == stock_id,
            CorporateFiling.filing_type.in_(list(HIGH_IMPACT_TYPES)),
            CorporateFiling.filing_time >= cutoff,
        )
        .order_by(CorporateFiling.filing_time.desc())
        .limit(1)
    )
    filing = result.scalar_one_or_none()

    if filing is None:
        return GuardResult(suppressed=False)

    age_minutes = int((datetime.now(tz=UTC) - filing.filing_time).total_seconds() / 60)
    suppressed_until = filing.filing_time + _SUPPRESS_WINDOW
    reason = f"{filing.filing_type} filed {age_minutes} minute{'s' if age_minutes != 1 else ''} ago"
    return GuardResult(suppressed=True, reason=reason, suppressed_until=suppressed_until)
