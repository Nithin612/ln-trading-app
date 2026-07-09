"""Shared session-context math (Phase-3 pre-work).

One implementation feeds BOTH the walk-forward runner and the live
pipeline; these hand-computed fixtures pin its semantics so neither side
can drift (8c-5b lesson). Pure — no DB, no clocks.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from app.profiles.session_context import (
    SCREEN_925_READY,
    pct_change_at_925,
    prev_session_map,
    prev_session_ohlc_for_window,
    session_ohlc,
)

IST = ZoneInfo("Asia/Kolkata")

D1, D2, D3 = date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8)


def _ist(d: date, hh: int, mm: int) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=IST)


class TestSessionOhlc:
    def test_aggregates_first_open_max_high_min_low_last_close(self) -> None:
        dates = [D1, D1, D1, D2, D2]
        out = session_ohlc(
            dates,
            [100.0, 101.0, 99.0, 105.0, 104.0],  # open
            [102.0, 106.0, 101.0, 107.0, 105.0],  # high
            [99.0, 100.5, 96.0, 104.0, 101.0],  # low
            [101.0, 100.0, 98.0, 104.5, 103.0],  # close
        )
        assert out == {
            D1: {"open": 100.0, "high": 106.0, "low": 96.0, "close": 98.0},
            D2: {"open": 105.0, "high": 107.0, "low": 101.0, "close": 103.0},
        }


class TestPrevSessionMap:
    def test_maps_each_session_to_prior_and_sorts(self) -> None:
        a = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}
        b = {"open": 3.0, "high": 4.0, "low": 2.5, "close": 3.5}
        c = {"open": 5.0, "high": 6.0, "low": 4.5, "close": 5.5}
        # deliberately unsorted insertion order — the map must sort
        out = prev_session_map({D2: b, D1: a, D3: c})
        assert out == {D2: a, D3: b}  # earliest session absent


class TestPrevSessionOhlcForWindow:
    def test_returns_middle_session_for_three_session_window(self) -> None:
        dates = [D1, D1, D2, D2, D3]
        prev = prev_session_ohlc_for_window(
            dates,
            [100.0, 101.0, 105.0, 104.0, 110.0],
            [102.0, 103.0, 108.0, 106.0, 111.0],
            [99.0, 100.0, 104.0, 101.0, 109.0],
            [101.0, 102.0, 106.0, 103.0, 110.5],
        )
        assert prev == {"open": 105.0, "high": 108.0, "low": 101.0, "close": 103.0}

    def test_fails_closed_with_two_sessions(self) -> None:
        """With two sessions the previous one is the window's EARLIEST —
        a 300-bar-capped live window may have truncated its early bars, so
        a half-session PDH must never be served."""
        dates = [D1, D1, D2]
        assert (
            prev_session_ohlc_for_window(
                dates, [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]
            )
            is None
        )

    def test_fails_closed_on_empty(self) -> None:
        assert prev_session_ohlc_for_window([], [], [], [], []) is None


class TestPctChangeAt925:
    def test_hand_computed_change_vs_prev_session_close(self) -> None:
        dates = [D1, D1, D1, D2, D2, D2]
        times = [
            _ist(D1, 9, 15), _ist(D1, 9, 20), _ist(D1, 15, 25),
            _ist(D2, 9, 15), _ist(D2, 9, 20), _ist(D2, 15, 25),
        ]
        closes = [100.0, 101.0, 102.0, 103.0, 104.04, 105.0]
        out = pct_change_at_925(dates, times, closes)
        # D1 has no prior close → absent; D2: 09:20 bar close vs 102.0
        assert set(out) == {D2}
        assert out[D2] == pytest.approx(2.0)

    def test_last_early_bar_wins_not_first(self) -> None:
        dates = [D1, D2, D2]
        times = [_ist(D1, 15, 25), _ist(D2, 9, 15), _ist(D2, 9, 20)]
        closes = [100.0, 99.0, 100.45]
        out = pct_change_at_925(dates, times, closes)
        assert out[D2] == pytest.approx(0.45)  # the 09:20 bar, not the 09:15

    def test_session_without_early_bar_absent(self) -> None:
        dates = [D1, D2]
        times = [_ist(D1, 15, 25), _ist(D2, 10, 0)]  # D2 opens late (gap-fill hole)
        closes = [100.0, 104.0]
        assert pct_change_at_925(dates, times, closes) == {}

    def test_bars_after_cutoff_do_not_leak_in(self) -> None:
        """A 09:25-starting bar closes at 09:30 — using it would be
        look-ahead. Only bars STARTING at/before 09:20 feed the screen."""
        dates = [D1, D2, D2]
        times = [_ist(D1, 15, 25), _ist(D2, 9, 20), _ist(D2, 9, 25)]
        closes = [100.0, 101.0, 150.0]
        out = pct_change_at_925(dates, times, closes)
        assert out[D2] == pytest.approx(1.0)  # 101 vs 100 — never 150

    def test_zero_prev_close_skipped(self) -> None:
        dates = [D1, D2]
        times = [_ist(D1, 15, 25), _ist(D2, 9, 20)]
        closes = [0.0, 104.0]
        assert pct_change_at_925(dates, times, closes) == {}

    def test_cutoff_constant_is_920(self) -> None:
        """The screen is born when the 09:20-starting bar CLOSES (09:25);
        both engines gate on this same constant."""
        assert SCREEN_925_READY == time(9, 20)
