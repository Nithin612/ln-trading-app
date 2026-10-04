"""The provisional layer's run window comes from the CALENDAR (2026-10-04).

The canary: `_in_session` was a weekday wall-clock rule (Mon–Fri 09:15–15:35), so the live
leaderboard stayed DARK through NSE weekend sessions (2026-02-01 was a Sunday session) and RAN
on weekday holidays. Now the window is `market_calendar.session_hours` for the run's day plus a
5-minute drain grace — read through the real calendar tables here, not mocked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.broker.provisional import (
    _fallback_window,
    _in_session,
    _todays_window,
    run_window,
)
from app.models.market_calendar import NseHoliday, NseSpecialSession
from sqlalchemy.ext.asyncio import AsyncSession

_IST = ZoneInfo("Asia/Kolkata")
WED, SAT, SUN = date(2027, 3, 3), date(2027, 3, 6), date(2027, 3, 7)


def _at(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=_IST).astimezone(UTC)


class TestThroughTheRealCalendar:
    async def test_a_regular_weekday_runs_09_15_to_15_35(self, db: AsyncSession) -> None:
        from tests.conftest import _engine

        assert await _todays_window(_engine, WED) == (time(9, 15), time(15, 35))

    async def test_a_weekend_special_session_runs(self, db: AsyncSession) -> None:
        """test_provisional_dark_on_weekend_session — the bug."""
        from tests.conftest import _engine

        db.add(NseSpecialSession(session_date=SUN, name="budget", source="published"))
        await db.commit()
        window = await _todays_window(_engine, SUN)
        assert window == (time(9, 15), time(15, 35))
        assert _in_session(_at(SUN, 11, 0), SUN, window)

    async def test_a_muhurat_window_is_its_own_evening_hours(self, db: AsyncSession) -> None:
        """The WINDOW only. ⚠ In production the host `live_worker` still runs the regular
        09:15–15:30 shape, so an evening muhurat stays dark end to end (recorded limit)."""
        from tests.conftest import _engine

        db.add(NseSpecialSession(session_date=SAT, name="muhurat", source="published",
                                 open_ist=time(18, 0), close_ist=time(19, 0)))
        await db.commit()
        window = await _todays_window(_engine, SAT)
        assert window == (time(18, 0), time(19, 5))
        assert not _in_session(_at(SAT, 11, 0), SAT, window)  # NOT the day shape
        assert _in_session(_at(SAT, 18, 30), SAT, window)

    async def test_a_weekday_holiday_stays_dark(self, db: AsyncSession) -> None:
        """The old rule's other half: it RAN on a weekday holiday."""
        from tests.conftest import _engine

        db.add(NseHoliday(holiday_date=WED, name="test holiday", source="published"))
        await db.commit()
        assert await _todays_window(_engine, WED) is None
        assert not _in_session(_at(WED, 11, 0), WED, None)

    async def test_an_ordinary_weekend_stays_dark(self, db: AsyncSession) -> None:
        from tests.conftest import _engine

        assert await _todays_window(_engine, SAT) is None


class TestWindowArithmetic:
    def test_boundaries_are_inclusive_and_the_drain_grace_applies(self) -> None:
        w = run_window((time(9, 15), time(15, 30)))
        assert w == (time(9, 15), time(15, 35))
        assert not _in_session(_at(WED, 9, 14), WED, w)
        assert _in_session(_at(WED, 9, 15), WED, w)
        assert _in_session(_at(WED, 15, 35), WED, w)
        assert not _in_session(_at(WED, 15, 36), WED, w)

    def test_a_different_ist_day_is_outside_the_resolved_window(self) -> None:
        w = run_window((time(9, 15), time(15, 30)))
        assert not _in_session(_at(date(2027, 3, 4), 11, 0), WED, w)

    def test_a_late_close_clamps_at_midnight_instead_of_wrapping(self) -> None:
        w = run_window((time(23, 0), time(23, 57)))
        assert w == (time(23, 0), time.max)
        assert _in_session(_at(WED, 23, 30), WED, w)

    def test_half_recorded_hours_warn_and_use_the_regular_window(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """An open-only special session resolves to 18:00→15:30 — inverted, silently dark."""
        assert run_window((time(18, 0), time(15, 30))) == (time(9, 15), time(15, 35))
        assert "inverted session hours" in caplog.text

    def test_the_unreadable_calendar_fallback_is_the_old_weekday_rule(self) -> None:
        assert _fallback_window(WED) == (time(9, 15), time(15, 35))
        assert _fallback_window(SAT) is None and _fallback_window(SUN) is None
