"""B4 — the gap guard tests the SPAN, not two hardcoded endpoints.

The old guard asked whether a window's two ENDPOINTS straddled ONE named date range
(`GAP_LO, GAP_HI = 2020-12-23, 2023-07-03`). That is a constant describing a single
incident — the shape W5 forbids — and it said nothing about holes INSIDE a window:
measured, it missed 204 of 16,428 panels (1.2%), worst case 516 sessions inside a 300-row
window.
"""

from datetime import date, timedelta

from app.models.market_data import OhlcvDaily
from app.services.market_calendar import (
    observed_session_index,
    session_span,
    window_has_holes,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _index(days: list[date]) -> dict[date, int]:
    return {d: i for i, d in enumerate(days)}


def _weekdays(start: date, n: int) -> list[date]:
    """`n` weekday sessions from `start`. A session calendar is NOT consecutive days."""
    out: list[date] = []
    cur = start
    while len(out) < n:
        if cur.weekday() <= 4:
            out.append(cur)
        cur += timedelta(days=1)
    return out


class TestSessionSpan:
    def test_span_is_inclusive(self) -> None:
        idx = _index([date(2026, 1, d) for d in (5, 6, 7, 8, 9)])
        assert session_span(idx, date(2026, 1, 5), date(2026, 1, 9)) == 5
        assert session_span(idx, date(2026, 1, 5), date(2026, 1, 5)) == 1

    def test_a_date_the_market_never_traded_is_unassessable_not_zero(self) -> None:
        """⭐ `None`, not 0 and not an exception — the three cases must stay distinct.

        Returning 0 would read as "no gap" and silently pass a window the guard could not
        actually judge, which is the zero-sentinel mistake this codebase keeps finding.
        """
        idx = _index([date(2026, 1, 5), date(2026, 1, 6)])
        assert session_span(idx, date(2026, 1, 1), date(2026, 1, 6)) is None
        assert session_span(idx, date(2026, 1, 5), date(2026, 1, 31)) is None


class TestWindowHasHoles:
    def test_a_contiguous_window_is_clean(self) -> None:
        idx = _index([date(2026, 1, 1) + timedelta(days=i) for i in range(300)])
        first, last = date(2026, 1, 1), date(2026, 1, 1) + timedelta(days=299)
        assert window_has_holes(idx, first, last, 300) is False

    def test_the_922_day_market_wide_hole_is_caught(self) -> None:
        """⛔⛔ THE REGRESSION TEST FOR A DEFECT THIS GUARD SHIPPED WITH.

        The first version tested observed SESSIONS only, and a full-corpus run then flagged
        3 trades where the previous endpoint-based guard flagged 38. The reason is
        structural: during `ohlcv_1d`'s 922-day hole NOBODY has bars, so those dates are
        absent from the observed calendar entirely and the window looks perfectly
        contiguous in session terms — ~300 sessions for 300 rows. Only the WALL CLOCK
        reveals it.

        ⭐ The general lesson: a hole is invisible to exactly the instrument that defines
        "normal" using the same data the hole is missing from.
        """
        # 150 sessions each side of the real hole, nothing in between — which is precisely
        # what the observed calendar looks like across that window.
        before = [date(2020, 6, 1) + timedelta(days=i) for i in range(150)]
        after = [date(2023, 7, 3) + timedelta(days=i) for i in range(150)]
        idx = _index(before + after)
        assert session_span(idx, before[0], after[-1]) == 300, (
            "the session calendar genuinely cannot see this hole — that is the point"
        )
        assert window_has_holes(idx, before[0], after[-1], 300) is True, (
            "...and the calendar-day test must catch it anyway"
        )

    def test_a_normal_300_session_window_is_not_flagged_by_the_calendar_test(self) -> None:
        """The canary for the second test: 300 REAL sessions span ~420 days, under the cap.

        ⚠ Weekdays only — a fixture of consecutive calendar days is not a session calendar,
        and using one is what made the first draft of this very test fail.
        """
        days = _weekdays(date(2024, 1, 1), 300)
        idx = _index(days)
        assert (days[-1] - days[0]).days < 300 * 1.75
        assert window_has_holes(idx, days[0], days[-1], 300) is False

    def test_a_per_name_hole_inside_the_window_is_caught(self) -> None:
        """⭐⭐ The case the OLD guard structurally could not see.

        Both endpoints sit well inside the modern contiguous block — the old endpoint test
        would pass it — but the name only has 300 bars across 516 sessions.
        """
        idx = _index([date(2024, 1, 1) + timedelta(days=i) for i in range(800)])
        first = date(2024, 1, 1)
        last = first + timedelta(days=515)
        assert window_has_holes(idx, first, last, 300) is True

    def test_tolerance_absorbs_a_stray_missing_session(self) -> None:
        """A trading halt or a late listing must not flag an otherwise clean window."""
        idx = _index([date(2026, 1, 1) + timedelta(days=i) for i in range(400)])
        assert window_has_holes(idx, date(2026, 1, 1), date(2026, 1, 1) + timedelta(days=302),
                                300) is False   # 303 sessions / 300 rows = 1.0%
        assert window_has_holes(idx, date(2026, 1, 1), date(2026, 1, 1) + timedelta(days=320),
                                300) is True    # 321 / 300 = 7%

    def test_it_fails_open_on_an_unassessable_endpoint(self) -> None:
        """A guard that cannot see is not evidence of a hole — matches every overlay here.

        ⚠ The calendar-day test runs FIRST and needs no index, so this fixture has to keep
        the wall-clock span normal: an unassessable SESSION span must fail open, but a
        27-year span for 300 rows is a hole whether or not the index can see the endpoints.
        """
        days = _weekdays(date(2026, 1, 1), 300)
        idx = _index(days)
        missing = days[-1] + timedelta(days=1)   # a date the calendar has never seen
        assert missing not in idx
        assert window_has_holes(idx, days[0], missing, 300) is False


class TestObservedCalendar:
    async def test_it_reads_the_dates_the_market_actually_produced(
        self, db: AsyncSession
    ) -> None:
        """⚠ Deliberately NOT `trading_days_between`: that derives the calendar from
        `nse_holidays`, which is measured incomplete for 2019–2020 (7 rows against ≥17
        holidays). A missing holiday reads as a trading day and inflates every span."""
        from datetime import UTC, datetime

        stock = await make_stock(db, symbol="SPANCO")
        kept = [date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 6)]  # 3/4 and 3/5 absent
        for d in kept:
            db.add(OhlcvDaily(
                time=datetime(d.year, d.month, d.day, tzinfo=UTC), stock_id=stock.id,
                open=1, high=1, low=1, close=1, volume=1, is_complete=True,
            ))
        await db.commit()

        idx = await observed_session_index(db)
        assert set(idx) == set(kept)
        assert session_span(idx, kept[0], kept[-1]) == 3
        # 3 rows spanning 3 observed sessions is clean; the absent calendar days are
        # absent for EVERYONE, so they are not a hole in this name's history.
        assert window_has_holes(idx, kept[0], kept[-1], 3) is False
