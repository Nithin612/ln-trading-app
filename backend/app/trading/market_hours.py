"""Market-session helper for trading tasks — NSE regular session in IST.

This is the strict regular-session window (09:15–15:30 IST, Mon–Fri) the
position monitor uses to decide whether it may act on prices at all. It is
deliberately separate from the broker's live-worker window (which adds a
drain grace past close): the monitor closes real paper positions, so it must
not act one minute before the open or after the close.

Holidays are NOT encoded here — the monitor also gates on the presence of a
live LTP, which is absent on a holiday (no ticks), so a weekday holiday
naturally results in a no-op.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


def is_market_session(
    now_utc: datetime, hours: tuple[time, time] | None | Literal["weekday"] = "weekday"
) -> bool:
    """True iff ``now_utc`` (tz-aware UTC) falls within the session's IST hours.

    ``hours`` comes from the calendar (`market_calendar.session_hours`): the day's
    (open, close), or None when the day is not a trading day. The default
    ``"weekday"`` is the calendar-free fallback — 09:15–15:30 on Mon–Fri — for the
    few pure contexts with no database; it cannot see a weekend session or a holiday,
    so a task with a DB uses `market_calendar.in_market_session` instead."""
    now_ist = now_utc.astimezone(_IST)
    if hours == "weekday":
        if now_ist.weekday() > 4:  # 5 = Sat, 6 = Sun
            return False
        hours = (SESSION_OPEN, SESSION_CLOSE)
    if hours is None:
        return False
    t = now_ist.timetz().replace(tzinfo=None)
    return hours[0] <= t <= hours[1]
