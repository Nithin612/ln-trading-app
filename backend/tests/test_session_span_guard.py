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

    def test_the_922_day_hole_is_caught_without_being_named(self) -> None:
        """⭐ The whole point: the old constants are gone and the hole is still caught."""
        days = [date(2020, 1, 1) + timedelta(days=i) for i in range(150)]
        days += [date(2023, 7, 3) + timedelta(days=i) for i in range(150)]
        idx = _index(days)
        assert window_has_holes(idx, days[0], days[-1], 300) is False, (
            "the INDEX is contiguous by construction — span 300 for 300 rows"
        )
        # …but a window that spans the real-calendar gap does NOT have 300 rows in it.
        # Simulate the real shape: 300 rows drawn from a calendar that has 1,200 sessions.
        wide = _index([date(2020, 1, 1) + timedelta(days=i) for i in range(1200)])
        assert window_has_holes(wide, date(2020, 1, 1), date(2023, 4, 14), 300) is True

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
        """A guard that cannot see is not evidence of a hole — matches every overlay here."""
        idx = _index([date(2026, 1, 5), date(2026, 1, 6)])
        assert window_has_holes(idx, date(1999, 1, 1), date(2026, 1, 6), 300) is False


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
