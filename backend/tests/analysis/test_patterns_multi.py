"""Golden-value tests for multi-candlestick pattern detectors."""

import pandas as pd
import pytest
from app.analysis.patterns.multi import (
    detect_engulfing,
    detect_harami,
    detect_morning_evening_star,
    detect_piercing_dark_cloud,
)


def _candles(*rows: tuple[float, float, float, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"open": o, "high": h, "low": lo, "close": c, "volume": 1000} for o, h, lo, c in rows]
    )


class TestEngulfing:
    def test_bullish_engulfing(self) -> None:
        # prev: red (open 110, close 100); curr: green (open 95, close 115)
        # curr body covers prev body: bot_curr=95 ≤ bot_prev=100, top_curr=115 ≥ top_prev=110
        df = _candles((110, 115, 95, 100), (95, 120, 90, 115))
        r = detect_engulfing(df)
        assert r.detected and r.score == pytest.approx(+0.9)
        assert "BULLISH" in r.name

    def test_bearish_engulfing(self) -> None:
        # prev: green (open 100, close 110); curr: red (open 115, close 95)
        df = _candles((100, 115, 95, 110), (115, 120, 90, 95))
        r = detect_engulfing(df)
        assert r.detected and r.score == pytest.approx(-0.9)
        assert "BEARISH" in r.name

    def test_partial_cover_not_engulfing(self) -> None:
        # curr green but doesn't fully cover prev body
        df = _candles((110, 115, 95, 100), (98, 108, 97, 107))
        r = detect_engulfing(df)
        assert not r.detected

    def test_need_two_candles(self) -> None:
        df = _candles((100, 110, 90, 105))
        r = detect_engulfing(df)
        assert not r.detected


class TestHarami:
    def test_bullish_harami(self) -> None:
        # prev: red (open 115, close 95), curr: small green inside
        df = _candles((115, 120, 90, 95), (100, 110, 99, 108))
        r = detect_harami(df)
        assert r.detected and r.score == pytest.approx(+0.5)

    def test_bearish_harami(self) -> None:
        # prev: green (open 95, close 115), curr: small red inside
        df = _candles((95, 120, 90, 115), (108, 112, 98, 100))
        r = detect_harami(df)
        assert r.detected and r.score == pytest.approx(-0.5)

    def test_outside_bar_not_harami(self) -> None:
        df = _candles((110, 115, 100, 105), (95, 120, 90, 115))
        r = detect_harami(df)
        assert not r.detected


class TestPiercingDarkCloud:
    def test_piercing_pattern(self) -> None:
        # prev: red (open 110, close 100, mid=105)
        # curr: green opens below 100 (prev close), closes above 105
        df = _candles((110, 115, 98, 100), (97, 112, 96, 107))
        r = detect_piercing_dark_cloud(df)
        assert r.detected and r.score == pytest.approx(+0.7)
        assert "PIERCING" in r.name

    def test_dark_cloud_cover(self) -> None:
        # prev: green (open 100, close 110, mid=105)
        # curr: red opens above 110, closes below 105
        df = _candles((100, 112, 98, 110), (113, 115, 99, 103))
        r = detect_piercing_dark_cloud(df)
        assert r.detected and r.score == pytest.approx(-0.7)
        assert "DARK_CLOUD" in r.name

    def test_no_pattern(self) -> None:
        # curr green but doesn't close above midpoint
        df = _candles((110, 115, 98, 100), (97, 103, 96, 102))
        r = detect_piercing_dark_cloud(df)
        assert not r.detected


class TestMorningEveningStar:
    def test_morning_star(self) -> None:
        # first: big red (open 120, close 100, body=20)
        # star: small body (open 98, close 99, body=1 < 10)
        # third: green closes above mid (110 > 110 = midpoint 110)
        df = _candles(
            (120, 125, 98, 100),   # big red
            (98, 100, 97, 99),     # small star
            (100, 116, 99, 115),   # big green recovering
        )
        r = detect_morning_evening_star(df)
        assert r.detected and r.score == pytest.approx(+0.95)
        assert "MORNING" in r.name

    def test_evening_star(self) -> None:
        # first: big green (open 100, close 120, body=20)
        # star: small body
        # third: big red closes below mid (105 < 110 midpoint)
        df = _candles(
            (100, 122, 98, 120),   # big green
            (121, 123, 120, 121),  # small star
            (120, 121, 99, 103),   # big red dropping
        )
        r = detect_morning_evening_star(df)
        assert r.detected and r.score == pytest.approx(-0.95)
        assert "EVENING" in r.name

    def test_insufficient_candles(self) -> None:
        df = _candles((100, 110, 90, 105), (98, 108, 96, 107))
        r = detect_morning_evening_star(df)
        assert not r.detected
