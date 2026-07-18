"""NSE market-calendar service (Phase 2 slice 1).

All trading-day arithmetic goes through here — calendar-day approximations
are a bug (.claude/rules/trading-domain.md). A trading day is a weekday
that is not an `nse_holidays` row.

Coverage honesty: the table is seeded from bhavcopy session gaps (past,
ground truth) plus published NSE circulars (future). Queries beyond the
last seeded holiday log a WARNING and fall back to weekday arithmetic —
add the new year's circular via the admin endpoint when NSE publishes it.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_calendar import NseHoliday

log = logging.getLogger(__name__)

# NSE cash-market session (IST wall clock)
SESSION_OPEN_IST = time(9, 15)
SESSION_CLOSE_IST = time(15, 30)
INTRADAY_CUTOFF_IST = time(15, 15)

# SIGNAL_ENGINE.md §5 — validity in TRADING days per classification.
VALIDITY_TRADING_DAYS = {"swing": 5, "positional": 30}


async def _holidays_between(db: AsyncSession, start: date, end: date) -> set[date]:
    result = await db.execute(
        select(NseHoliday.holiday_date).where(
            NseHoliday.holiday_date >= start, NseHoliday.holiday_date <= end
        )
    )
    return set(result.scalars().all())


async def coverage_end(db: AsyncSession) -> date | None:
    """Last seeded holiday — the honesty horizon of the calendar."""
    result = await db.execute(
        select(NseHoliday.holiday_date).order_by(NseHoliday.holiday_date.desc()).limit(1)
    )
    return result.scalar_one_or_none()


def _warn_if_uncovered(last_seeded: date | None, queried_up_to: date) -> None:
    if last_seeded is None or queried_up_to > last_seeded:
        log.warning(
            "market calendar queried up to %s but holiday coverage ends %s — "
            "weekday fallback in effect; seed the new NSE circular",
            queried_up_to,
            last_seeded,
        )


async def is_trading_day(db: AsyncSession, d: date) -> bool:
    """Weekday and not an NSE holiday."""
    if d.weekday() > 4:
        return False
    holidays = await _holidays_between(db, d, d)
    return d not in holidays


async def add_trading_days(db: AsyncSession, start: datetime, n: int) -> datetime:
    """The datetime `n` trading days after `start` (same time of day).

    n must be >= 1; the count starts from the next candidate day, so a
    signal created ANY time on day D with n=5 expires at the same wall
    time five trading sessions later — weekends/holidays never count.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    # window: n trading days can span at most ~2.5x calendar days + slack
    span = timedelta(days=n * 3 + 10)
    holidays = await _holidays_between(db, start.date(), (start + span).date())
    _warn_if_uncovered(await coverage_end(db), (start + span).date())

    d = start.date()
    remaining = n
    while remaining > 0:
        d = d + timedelta(days=1)
        if d.weekday() <= 4 and d not in holidays:
            remaining -= 1
    return datetime.combine(d, start.timetz())


async def next_trading_day(db: AsyncSession, d: date) -> date:
    dt = datetime.combine(d, time(0, 0), tzinfo=UTC)
    return (await add_trading_days(db, dt, 1)).date()


async def prev_trading_day(db: AsyncSession, d: date) -> date:
    holidays = await _holidays_between(db, d - timedelta(days=30), d)
    cur = d - timedelta(days=1)
    while cur.weekday() > 4 or cur in holidays:
        cur = cur - timedelta(days=1)
    return cur


async def last_n_trading_days(db: AsyncSession, end: date, n: int) -> list[date]:
    """The n most recent trading days ending AT `end` (inclusive if it
    trades). Used by the FII/DII 5-trading-day rollup."""
    holidays = await _holidays_between(db, end - timedelta(days=n * 3 + 10), end)
    days: list[date] = []
    cur = end
    while len(days) < n:
        if cur.weekday() <= 4 and cur not in holidays:
            days.append(cur)
        cur = cur - timedelta(days=1)
    days.reverse()
    return days


async def trading_days_between(db: AsyncSession, start: date, end: date) -> list[date]:
    """All trading days in [start, end], ascending ([] when start > end).

    Backbone of the EOD catch-up healer (services/eod_catchup.py)."""
    if start > end:
        return []
    holidays = await _holidays_between(db, start, end)
    _warn_if_uncovered(await coverage_end(db), end)
    days: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() <= 4 and cur not in holidays:
            days.append(cur)
        cur = cur + timedelta(days=1)
    return days


async def validity_offset_days(
    db: AsyncSession, classification: str, created_at: datetime
) -> int:
    """Calendar-day span covering the classification's TRADING-day validity
    (SIGNAL_ENGINE.md §5) — feeds compute_validity_until's
    trading_days_offset hook. 0 for classifications that don't use it."""
    n = VALIDITY_TRADING_DAYS.get(classification)
    if n is None:
        return 0
    target = await add_trading_days(db, created_at, n)
    return (target.date() - created_at.date()).days
