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
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


def is_market_session(now_utc: datetime) -> bool:
    """True iff ``now_utc`` (tz-aware UTC) falls within the NSE regular
    session (09:15–15:30 IST) on a weekday."""
    now_ist = now_utc.astimezone(_IST)
    if now_ist.weekday() > 4:  # 5 = Sat, 6 = Sun
        return False
    t = now_ist.timetz().replace(tzinfo=None)
    return SESSION_OPEN <= t <= SESSION_CLOSE
