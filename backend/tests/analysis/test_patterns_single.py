"""Golden-value tests for single-candlestick pattern detectors."""

import pandas as pd
import pytest
from app.analysis.patterns.single import (
    detect_doji,
    detect_hammer,
    detect_hanging_man,
    detect_marubozu,
    detect_shooting_star,
    detect_spinning_top,
)


def _candle(
    open_: float, high: float, low: float, close: float, volume: int = 1000
) -> pd.DataFrame:
    return pd.DataFrame(
        [{"open": open_, "high": high, "low": low, "close": close, "volume": volume}]
    )


def _candles(*rows: tuple[float, float, float, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"open": o, "high": h, "low": lo, "close": c, "volume": 1000} for o, h, lo, c in rows]
    )


class TestMarubozu:
    def test_bullish_detected(self) -> None:
        # Body = 95, range = 100 → 95%
        df = _candle(100, 105, 99, 195)  # open 100 close 195 high 200 low 99 → oops
        # Let's construct properly: body = close-open = 95, range = high-low = 100
        df = _candle(100, 200, 100.5, 195)
        result = detect_marubozu(df)
        # body = 95, range = 99.5, ratio = 95.5% ≥ 95%
        assert result.detected
        assert result.score == pytest.approx(+0.8)
        assert "Bullish" in result.name or "BULLISH" in result.name

    def test_bearish_detected(self) -> None:
        # open=200, close=101 → body=99, high=200.5, low=100.5 → range=100, ratio=99%
        df = _candle(200, 200.5, 100.5, 101)
        result = detect_marubozu(df)
        assert result.detected
        assert result.score == pytest.approx(-0.8)

    def test_not_marubozu(self) -> None:
        # Body = 5, range = 50 → 10%
        df = _candle(100, 125, 75, 105)
        result = detect_marubozu(df)
        assert not result.detected
        assert result.score == 0.0

    def test_zero_range(self) -> None:
        df = _candle(100, 100, 100, 100)
        result = detect_marubozu(df)
        assert not result.detected


class TestDoji:
    def test_doji_detected(self) -> None:
        # open = close, so body = 0
        df = _candle(100, 105, 95, 100)
        result = detect_doji(df)
        assert result.detected
        assert result.score == 0.0

    def test_near_doji(self) -> None:
        # body = 0.5, range = 10 → 5% exactly
        df = _candle(100, 105, 95, 100.5)
        result = detect_doji(df)
        assert result.detected  # 5% == threshold

    def test_not_doji(self) -> None:
        df = _candle(100, 110, 90, 108)  # body=8, range=20 → 40%
        result = detect_doji(df)
        assert not result.detected


class TestSpinningTop:
    def test_spinning_top_detected(self) -> None:
        # body = 2, range = 20, so body_ratio = 10% ≤ 30%
        # uw = high - max(o,c) = 10 - 102 = hmm, let me think
        # open=99, close=101 (body=2), high=110, low=90 (range=20)
        # uw = 110 - 101 = 9, lw = 99 - 90 = 9, sym = 1.0 ≥ 0.5
        df = _candle(99, 110, 90, 101)
        result = detect_spinning_top(df)
        assert result.detected
        assert result.score == 0.0

    def test_asymmetric_not_spinning_top(self) -> None:
        # big upper wick, tiny lower wick — not symmetric
        df = _candle(99, 120, 98, 101)
        result = detect_spinning_top(df)
        assert not result.detected


class TestHammer:
    def test_hammer_at_swing_low(self) -> None:
        # body in upper third, lower wick >= 2x body
        # open=108, close=110 (body=2), high=110, low=100 (range=10)
        # body_top=110, body_bot=108
        # body_top - low = 10, range=10 → body in upper third ✓
        # lw = 108 - 100 = 8 = 4x body ✓, uw = 110-110 = 0 ≤ 2 ✓
        df = _candle(108, 110, 100, 110)
        result = detect_hammer(df, at_swing_low=True)
        assert result.detected
        assert result.score == pytest.approx(+0.7)
        assert "HAMMER" in result.name

    def test_paper_umbrella_no_context(self) -> None:
        df = _candle(108, 110, 100, 110)
        result = detect_hammer(df, at_swing_low=False)
        assert result.detected
        assert result.score == pytest.approx(+0.4)
        assert "PAPER_UMBRELLA" in result.name

    def test_not_hammer(self) -> None:
        # Body at lower third, not hammer
        df = _candle(100, 120, 99, 102)
        result = detect_hammer(df)
        assert not result.detected


class TestShootingStar:
    def test_shooting_star_at_high(self) -> None:
        # body in lower third, upper wick ≥ 2x body
        # open=100, close=102 (body=2), high=120, low=100 (range=20)
        # uw = 120 - 102 = 18 = 9x body ✓; lw = 100-100=0 ≤ 2 ✓
        # body_bot=100; high-body_bot = 20 = range ✓ (body in lower third)
        df = _candle(100, 120, 100, 102)
        result = detect_shooting_star(df, at_swing_high=True)
        assert result.detected
        assert result.score == pytest.approx(-0.7)

    def test_no_context_not_detected(self) -> None:
        df = _candle(100, 120, 100, 102)
        result = detect_shooting_star(df, at_swing_high=False)
        assert not result.detected


class TestHangingMan:
    def test_hanging_man_at_high(self) -> None:
        df = _candle(108, 110, 100, 110)
        result = detect_hanging_man(df, at_swing_high=True)
        assert result.detected
        assert result.score == pytest.approx(-0.6)

    def test_hanging_man_no_context(self) -> None:
        df = _candle(108, 110, 100, 110)
        result = detect_hanging_man(df, at_swing_high=False)
        assert not result.detected
