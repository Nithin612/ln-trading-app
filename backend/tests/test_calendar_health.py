"""A36 — NSE calendar-coverage expiry alarm.

The holiday table has a horizon (its last seeded circular); past it, trading-day arithmetic
silently drops to weekday-only. A36 turns that invisible query-time warning into a proactive
push + a daily-report line. These tests cover the four coverage states (absent / expired /
expiring-soon / healthy), the notification mapping, the report block, and the two
never-raises guarantees (a failing read, and the optional XNSE cross-check being absent).
"""

from datetime import UTC, date, datetime

from app.models.market_calendar import NseHoliday
from app.services import calendar_health as ch
from app.services import market_calendar as mc
from app.services.notifier import Level
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed(db: AsyncSession, *dates: date) -> None:
    for d in dates:
        db.add(NseHoliday(holiday_date=d, name="seed", source="published"))
    await db.commit()


def _at(y: int, m: int, d: int) -> datetime:
    """An IST-ish 'now' — the service converts to the IST date, so noon UTC is unambiguous."""
    return datetime(y, m, d, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# read_calendar_status — the four states                                      #
# --------------------------------------------------------------------------- #
class TestReadStatus:
    async def test_absent_when_nothing_seeded(self, db: AsyncSession) -> None:
        st = await ch.read_calendar_status(db, now=_at(2026, 1, 1))
        assert st.absent and not st.expired and st.trading_days_remaining == 0

    async def test_healthy_when_horizon_is_far_out(self, db: AsyncSession) -> None:
        await _seed(db, date(2026, 12, 25))  # Christmas — many months ahead
        st = await ch.read_calendar_status(db, now=_at(2026, 1, 1))
        assert st.healthy and not st.expiring_soon
        assert st.coverage_end == date(2026, 12, 25)
        assert st.trading_days_remaining > ch.WARN_BELOW_TRADING_DAYS

    async def test_expiring_soon_when_runway_below_threshold(self, db: AsyncSession) -> None:
        # Horizon 2026-01-20; from 2026-01-02..20 there are ~12 trading days (< 20).
        await _seed(db, date(2026, 1, 20))
        st = await ch.read_calendar_status(db, now=_at(2026, 1, 1))
        assert st.expiring_soon and not st.expired
        assert 0 < st.trading_days_remaining < ch.WARN_BELOW_TRADING_DAYS

    async def test_expired_when_horizon_is_in_the_past(self, db: AsyncSession) -> None:
        await _seed(db, date(2026, 1, 20))
        st = await ch.read_calendar_status(db, now=_at(2026, 6, 1))
        assert st.expired and st.trading_days_remaining == 0

    async def test_never_raises_when_the_read_fails(
        self, db: AsyncSession, monkeypatch
    ) -> None:
        async def _boom(*_a, **_k):
            raise RuntimeError("db down")

        monkeypatch.setattr(mc, "coverage_end", _boom)
        st = await ch.read_calendar_status(db, now=_at(2026, 1, 1))
        assert st.absent  # degraded to 'absent', not an exception into the report


# --------------------------------------------------------------------------- #
# to_notification — the proactive push mapping                                 #
# --------------------------------------------------------------------------- #
class TestNotification:
    def test_healthy_says_nothing(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), date(2026, 12, 25), 250)
        assert ch.to_notification(st) is None

    def test_expiring_soon_is_a_warning(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), date(2026, 1, 20), 12)
        n = ch.to_notification(st)
        assert n is not None and n.level is Level.WARNING
        assert n.event == "calendar_coverage"

    def test_expired_is_an_error(self) -> None:
        st = ch.CalendarStatus(date(2026, 6, 1), date(2026, 1, 20), 0)
        n = ch.to_notification(st)
        assert n is not None and n.level is Level.ERROR

    def test_absent_is_an_error(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), None, 0)
        n = ch.to_notification(st)
        assert n is not None and n.level is Level.ERROR

    def test_a_crosscheck_disagreement_pushes_even_when_healthy(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), date(2026, 12, 25), 250, "⚠ XNSE says …")
        n = ch.to_notification(st)
        assert n is not None and "XNSE" in "\n".join(n.lines)


# --------------------------------------------------------------------------- #
# render_lines — the human-read daily-report block                            #
# --------------------------------------------------------------------------- #
class TestRender:
    def test_healthy_is_one_quiet_line_stating_the_horizon(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), date(2026, 12, 25), 250)
        out = "\n".join(ch.render_lines(st))
        assert "✅ covered through 2026-12-25" in out and "250 trading days" in out

    def test_expiring_soon_is_a_warn_line(self) -> None:
        st = ch.CalendarStatus(date(2026, 1, 1), date(2026, 1, 20), 12)
        out = "\n".join(ch.render_lines(st))
        assert "⚠️ only **12 trading days**" in out

    def test_gone_is_a_loud_header(self) -> None:
        st = ch.CalendarStatus(date(2026, 6, 1), date(2026, 1, 20), 0)
        out = "\n".join(ch.render_lines(st))
        assert "COVERAGE GONE" in out and "weekday-only" in out


# --------------------------------------------------------------------------- #
# the optional XNSE cross-check degrades to None when the library is absent    #
# --------------------------------------------------------------------------- #
def test_crosscheck_is_none_without_exchange_calendars() -> None:
    """exchange_calendars is not a dependency; its absence must be silent, not a failure."""
    note = ch._crosscheck(date(2026, 1, 1), date(2026, 2, 1), {date(2026, 1, 5)})
    assert note is None
