"""A36 — alarm on NSE-calendar coverage expiry, not just a warning at query time.

## The failure this catches

The `nse_holidays` table is seeded from published NSE circulars, so it has a HORIZON: the
last seeded holiday (`market_calendar.coverage_end`). Query past that date and
`market_calendar` falls back to **weekday-only** arithmetic — silently miscounting every
trading-day validity window (`SIGNAL_ENGINE.md` §5) and every calendar-aware task around a
holiday it does not yet know about. That fallback logs a WARNING *inside the query*, seen by
nobody: the same technically-announced / practically-invisible degradation this review keeps
surfacing (the CAS window, the tick-mode fallback, the broker token).

A36 makes it **proactive**, mirroring A40's shape: a daily beat task reads how much
holiday-accurate runway the calendar has left and PUSHES (A11) when it is short or gone, and
the daily report carries the same horizon as a human-read line. Plus a **cheap second
opinion** — cross-check upcoming weekdays against `exchange_calendars`' XNSE when that library
is present. The cross-check is strictly optional: it is never a dependency and never a hard
failure, exactly as the finding frames it ("ours has the best data and the weakest alarm").

Shaped to match `token_health` / `worker_health` (same `read_* → render_lines` contract, same
daily-report block) rather than opening a third health surface — W2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.services import market_calendar as mc

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.notifier import Notification

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

#: Warn when fewer than this many trading days of holiday-accurate coverage remain. Chosen so
#: there is roughly a month of lead time to seed the next NSE circular before the calendar
#: silently drops to weekday-only arithmetic.
WARN_BELOW_TRADING_DAYS = 20


@dataclass(frozen=True)
class CalendarStatus:
    """The standing of the NSE holiday calendar's coverage horizon.

    `absent` (nothing seeded) and `expired` (a horizon that has passed) are kept apart even
    though both mean "weekday fallback is in effect now": the remedy is the same admin
    endpoint but the diagnosis is not, and a report that conflates them teaches people to
    ignore it (the same reasoning as `token_health`'s absent-vs-expired split).
    """

    today: date
    coverage_end: date | None
    trading_days_remaining: int
    #: A disagreement surfaced by the optional XNSE cross-check, else None.
    crosscheck_note: str | None = None

    @property
    def absent(self) -> bool:
        return self.coverage_end is None

    @property
    def expired(self) -> bool:
        return self.coverage_end is not None and self.coverage_end <= self.today

    @property
    def expiring_soon(self) -> bool:
        return (
            not self.absent
            and not self.expired
            and self.trading_days_remaining < WARN_BELOW_TRADING_DAYS
        )

    @property
    def healthy(self) -> bool:
        return not (self.absent or self.expired or self.expiring_soon)


async def read_calendar_status(
    db: AsyncSession, *, now: datetime | None = None
) -> CalendarStatus:
    """The calendar's coverage horizon and remaining runway. NEVER raises — this is read by
    the daily report and a health probe that can take down its own report has inverted its
    purpose (the rule `token_health.read_token_status` and `worker_health.read_statuses`
    follow)."""
    today = (now or datetime.now(tz=UTC)).astimezone(_IST).date()
    try:
        end = await mc.coverage_end(db)
    except Exception:  # noqa: BLE001 — a health probe must not raise into its own report
        log.exception("calendar coverage read failed; reporting as absent")
        return CalendarStatus(today=today, coverage_end=None, trading_days_remaining=0)
    if end is None:
        return CalendarStatus(today=today, coverage_end=None, trading_days_remaining=0)

    try:
        # Trading days strictly after today, through the horizon: the holiday-accurate runway.
        upcoming = await mc.trading_days_between(db, today + timedelta(days=1), end)
        remaining = len(upcoming)
    except Exception:  # noqa: BLE001
        log.exception("calendar remaining-days count failed; reporting 0")
        remaining = 0

    note = _crosscheck(today, end, {d for d in upcoming} if remaining else set())
    return CalendarStatus(
        today=today, coverage_end=end, trading_days_remaining=remaining, crosscheck_note=note
    )


def _crosscheck(start: date, end: date, our_trading_days: set[date]) -> str | None:
    """Cheap second opinion against `exchange_calendars`' XNSE, when it is installed.

    Reports weekdays in `(start, end]` that XNSE considers **non-sessions** (holidays) but
    which our table treats as trading days — the actionable disagreement. Entirely
    best-effort: a missing library or any error yields None (no cross-check, not a failure).
    We are not a dependency of XNSE and must never become one.
    """
    if end <= start or not our_trading_days:
        return None
    try:
        # exchange_calendars is intentionally NOT a dependency (approval-gated); mypy is
        # configured to ignore missing imports, so this resolves to Any here and at runtime
        # the `except` below swallows its absence.
        import exchange_calendars as xc
        import pandas as pd

        xnse = xc.get_calendar("XNSE")
        disagreements: list[date] = []
        cur = start + timedelta(days=1)
        while cur <= end:
            if cur.weekday() <= 4 and cur in our_trading_days:
                if not xnse.is_session(pd.Timestamp(cur)):
                    disagreements.append(cur)
            cur += timedelta(days=1)
        if not disagreements:
            return None
        shown = ", ".join(d.isoformat() for d in disagreements[:5])
        more = f" (+{len(disagreements) - 5} more)" if len(disagreements) > 5 else ""
        return (
            f"⚠ XNSE cross-check: {len(disagreements)} weekday(s) XNSE treats as holidays "
            f"but our table trades: {shown}{more}"
        )
    except Exception:  # noqa: BLE001 — the second opinion never breaks the first
        log.debug("XNSE cross-check unavailable or failed (non-fatal)", exc_info=True)
        return None


def to_notification(status: CalendarStatus) -> Notification | None:
    """The proactive push (A11), or None when there is nothing worth a human's attention.

    Deferred import of the notifier keeps this module free of a dependency it only needs at
    the one call site (the beat task), and keeps `render_lines`/status usable in isolation.
    """
    from app.services.notifier import Level, Notification

    if status.healthy and status.crosscheck_note is None:
        return None

    if status.absent:
        level, title = Level.ERROR, "NSE calendar EMPTY — no holidays seeded"
        lines = [
            "every trading-day calculation is weekday-only, so any window spanning a "
            "holiday is miscounted",
            "REMEDY: seed the NSE holiday circular via the admin endpoint",
        ]
    elif status.expired:
        level, title = Level.ERROR, "NSE calendar coverage EXPIRED"
        lines = [
            f"coverage_end={status.coverage_end} (already in the past)",
            "weekday fallback is in effect NOW — holidays past the horizon are invisible",
            "REMEDY: seed the next NSE holiday circular via the admin endpoint",
        ]
    elif status.expiring_soon:
        level, title = Level.WARNING, "NSE calendar coverage running low"
        lines = [
            f"trading_days_remaining={status.trading_days_remaining}",
            f"covered_through={status.coverage_end}",
            "seed the next NSE holiday circular before the horizon passes",
        ]
    else:  # healthy but the cross-check disagreed
        level, title = Level.WARNING, "NSE calendar cross-check disagreement"
        lines = [f"covered_through={status.coverage_end}"]

    if status.crosscheck_note:
        lines.append(status.crosscheck_note)
    return Notification(event="calendar_coverage", level=level, title=title, lines=lines)


def render_lines(status: CalendarStatus) -> list[str]:
    """Daily-report block, matching `token_health.render_lines`'s contract: loud when
    coverage is gone, a warn line when it is running low, one quiet line when healthy — and
    the quiet line still states the horizon, because "the calendar is fine" is only useful if
    it says how long that remains true."""
    if status.absent or status.expired:
        why = (
            "no NSE holidays are seeded at all"
            if status.absent
            else f"coverage ended {status.coverage_end}, which is in the past"
        )
        out = [
            "> ## ⛔ NSE CALENDAR COVERAGE GONE",
            ">",
            f"> {why} — so trading-day arithmetic has fallen back to **weekday-only**.",
            ">",
            "> Every validity window (SIGNAL_ENGINE.md §5) and calendar-aware task that spans",
            "> a holiday past the horizon is now silently miscounted.",
            ">",
            "> Remedy: seed the NSE holiday circular via the admin endpoint.",
        ]
    elif status.expiring_soon:
        out = [
            f"- **NSE calendar:** ⚠️ only **{status.trading_days_remaining} trading days** of "
            f"holiday-accurate coverage remain (through {status.coverage_end}). Seed the next "
            "NSE circular before the horizon passes, or arithmetic drops to weekday-only.",
        ]
    else:
        out = [
            f"- **NSE calendar:** ✅ covered through {status.coverage_end} "
            f"({status.trading_days_remaining} trading days out).",
        ]
    if status.crosscheck_note:
        out.append(f"- {status.crosscheck_note}")
    out.append("")
    return out
