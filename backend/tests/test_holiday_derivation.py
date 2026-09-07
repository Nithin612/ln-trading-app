"""Deriving NSE holidays from bhavcopy gaps — the guard against fabricating them.

⚠ Regression tests for a real corruption on 2026-09-07. `seed_nse_holidays.py` marks any
weekday with no bars as a market closure. That is sound over CONTIGUOUS data and wrong the
moment there is a hole: after the dev database was restored, `ohlcv_1d` held a 6-day
backfill smoke run in 2020 plus 2023-07-03 onward, and the seeder recorded **896 holidays**
for a market that closes ~13 times a year. 850 rows had to be deleted by hand.

Trading-day arithmetic sets signal validity windows (swing 5 trading days, positional 30),
so a fabricated holiday silently changes when signals expire. It is a correctness bug.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_nse_holidays import _MAX_CLOSURE_RUN, derive_closures  # noqa: E402


def _weekdays(lo: date, hi: date) -> set[date]:
    out, d = set(), lo
    while d <= hi:
        if d.weekday() <= 4:
            out.add(d)
        d += timedelta(days=1)
    return out


class TestRealClosures:
    def test_single_missing_weekday_is_a_holiday(self) -> None:
        lo, hi = date(2026, 1, 5), date(2026, 1, 9)  # Mon-Fri
        sessions = _weekdays(lo, hi) - {date(2026, 1, 7)}
        closures, skipped = derive_closures(lo, hi, sessions)
        assert list(closures) == [date(2026, 1, 7)]
        assert skipped == []

    def test_weekends_are_never_holidays(self) -> None:
        """A Saturday is not a closure — the exchange is simply not open."""
        lo, hi = date(2026, 1, 5), date(2026, 1, 16)
        closures, _ = derive_closures(lo, hi, _weekdays(lo, hi))
        assert closures == {}

    def test_a_festival_run_abutting_a_weekend_still_counts(self) -> None:
        """Thu+Fri closed, then the weekend, then Mon closed = 3 missing weekdays across
        5 calendar days. That is a plausible NSE closure and must NOT be discarded."""
        lo, hi = date(2026, 1, 5), date(2026, 1, 16)
        missing = {date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 12)}
        closures, skipped = derive_closures(lo, hi, _weekdays(lo, hi) - missing)
        assert set(closures) == missing
        assert skipped == []

    def test_run_exactly_at_the_limit_is_kept(self) -> None:
        lo, hi = date(2026, 1, 5), date(2026, 1, 30)
        missing = set(sorted(_weekdays(date(2026, 1, 5), date(2026, 1, 9)))[:_MAX_CLOSURE_RUN])
        closures, skipped = derive_closures(lo, hi, _weekdays(lo, hi) - missing)
        assert set(closures) == missing, "the boundary belongs to closures, not gaps"
        assert skipped == []


class TestDataGapsAreNotHolidays:
    def test_a_long_hole_is_reported_not_recorded(self) -> None:
        """⭐ The 2026-09-07 corruption, in miniature: two islands of data with a long hole
        between them. The hole must produce ZERO holidays."""
        lo, hi = date(2026, 1, 5), date(2026, 3, 31)
        sessions = _weekdays(date(2026, 1, 5), date(2026, 1, 9)) | _weekdays(
            date(2026, 3, 23), date(2026, 3, 31)
        )
        closures, skipped = derive_closures(lo, hi, sessions)

        assert closures == {}, "a data gap must not become holidays"
        assert len(skipped) == 1
        gap_lo, gap_hi, n = skipped[0]
        assert gap_lo == date(2026, 1, 12) and gap_hi == date(2026, 3, 20)
        assert n > _MAX_CLOSURE_RUN

    def test_run_one_past_the_limit_is_skipped(self) -> None:
        lo, hi = date(2026, 1, 5), date(2026, 1, 30)
        missing = set(sorted(_weekdays(lo, hi))[:_MAX_CLOSURE_RUN + 1])
        closures, skipped = derive_closures(lo, hi, _weekdays(lo, hi) - missing)
        assert closures == {}
        assert len(skipped) == 1 and skipped[0][2] == _MAX_CLOSURE_RUN + 1

    def test_real_closures_survive_alongside_a_gap(self) -> None:
        """A gap elsewhere in the span must not suppress genuine holidays — the fix has to
        discard the hole, not the whole derivation."""
        lo, hi = date(2026, 1, 5), date(2026, 4, 30)
        holiday = date(2026, 1, 7)
        sessions = (
            _weekdays(date(2026, 1, 5), date(2026, 1, 16))
            | _weekdays(date(2026, 4, 1), date(2026, 4, 30))
        ) - {holiday}
        closures, skipped = derive_closures(lo, hi, sessions)

        assert list(closures) == [holiday]
        assert len(skipped) == 1, "the hole is reported separately"

    def test_the_canary_the_old_code_would_fail(self) -> None:
        """Explicit canary. The pre-fix code marked EVERY missing weekday, so on this span
        it returned ~60 holidays. Anything above the real rate means the guard is gone."""
        lo, hi = date(2026, 1, 5), date(2026, 3, 31)
        sessions = _weekdays(date(2026, 1, 5), date(2026, 1, 9))
        closures, _ = derive_closures(lo, hi, sessions)
        assert len(closures) == 0, (
            "old behaviour recorded every missing weekday as a market closure — "
            "896 fabricated holidays on the real database"
        )
