"""Tests for structural analysis: Dow Theory, S/R levels, Fibonacci, Institutional flow."""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from app.analysis.structure.dow import dow_trend_factor
from app.analysis.structure.fibonacci import fibonacci_factor
from app.analysis.structure.institutional import fii_dii_factor
from app.analysis.structure.levels import detect_sr_levels, sr_zone_factor


def _zigzag_up(cycles: int = 8) -> pd.DataFrame:
    """Clear HH/HL zigzag uptrend: N candles up, then 2 candles retrace, repeat."""
    rows = []
    base = 100.0
    for _ in range(cycles):
        for _ in range(5):  # up candles
            o = base
            c = base * 1.015
            h = c * 1.005
            lo = o * 0.997
            rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000})
            base = c
        for _ in range(2):  # retrace candles
            o = base
            c = base * 0.990
            h = o * 1.002
            lo = c * 0.997
            rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000})
            base = c
    return pd.DataFrame(rows)


def _trending_up(n: int = 60) -> pd.DataFrame:
    """Alias for compatibility — returns zigzag uptrend."""
    return _zigzag_up(cycles=max(4, n // 7))


def _zigzag_down(cycles: int = 8) -> pd.DataFrame:
    """Clear LH/LL zigzag downtrend."""
    rows = []
    base = 200.0
    for _ in range(cycles):
        for _ in range(5):  # down candles
            o = base
            c = base * 0.985
            h = o * 1.003
            lo = c * 0.995
            rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000})
            base = c
        for _ in range(2):  # recovery candles
            o = base
            c = base * 1.010
            h = c * 1.003
            lo = o * 0.998
            rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000})
            base = c
    return pd.DataFrame(rows)


def _trending_down(n: int = 60) -> pd.DataFrame:
    """Alias for compatibility — returns zigzag downtrend."""
    return _zigzag_down(cycles=max(4, n // 7))


def _flat_ranging(n: int = 60) -> pd.DataFrame:
    """Flat candles oscillating around 100."""
    rng = np.random.default_rng(3)
    rows = []
    for _ in range(n):
        o = 100 + rng.uniform(-1, 1)
        c = 100 + rng.uniform(-1, 1)
        h = max(o, c) + rng.uniform(0, 0.5)
        lo = min(o, c) - rng.uniform(0, 0.5)
        rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000})
    return pd.DataFrame(rows)


class TestDowTheory:
    def test_uptrend_detected(self) -> None:
        df = _trending_up(60)
        r = dow_trend_factor(df)
        assert r.name == "DOW_TREND"
        assert r.weight == 20
        assert r.score > 0, f"Expected positive score for uptrend, got {r.score}"

    def test_downtrend_detected(self) -> None:
        df = _trending_down(60)
        r = dow_trend_factor(df)
        assert r.score < 0, f"Expected negative score for downtrend, got {r.score}"

    def test_insufficient_data(self) -> None:
        # Only 5 candles — far too few for swing detection
        rows = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000}] * 5
        df = pd.DataFrame(rows)
        r = dow_trend_factor(df)
        assert r.score == 0.0

    def test_score_in_range(self) -> None:
        for df in [_zigzag_up(8), _zigzag_down(8), _flat_ranging(60)]:
            r = dow_trend_factor(df)
            assert -1.0 <= r.score <= 1.0


class TestSrLevels:
    def test_sr_level_detection(self) -> None:
        # Create candles with repeated swing highs at ~110
        rows = []
        for idx in range(40):
            base = 100.0
            c = 95 + (idx % 3) * 7.5
            rows.append({
                "open": base, "high": c + 1, "low": c - 1, "close": c, "volume": 1_000_000,
            })
        df = pd.DataFrame(rows)
        levels = detect_sr_levels(df, n=2)
        # Just verify it returns a list (may be empty if not enough strength)
        assert isinstance(levels, list)

    def test_sr_zone_factor_neutral_no_zones(self) -> None:
        df = _flat_ranging(30)
        r = sr_zone_factor(df)
        assert r.name == "SR_ZONE"
        assert -1.0 <= r.score <= 1.0

    def test_sr_zone_factor_weight(self) -> None:
        df = _trending_up(60)
        r = sr_zone_factor(df)
        assert r.weight == 10


class TestFibonacci:
    def test_insufficient_data(self) -> None:
        rows = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000}] * 5
        df = pd.DataFrame(rows)
        r = fibonacci_factor(df)
        assert r.score == 0.0

    def test_at_618_level(self) -> None:
        # Construct candles where price sits exactly at 0.618 retrace
        # Swing high = 200, swing low = 100 → 0.618 retrace = 200 - 0.618*100 = 138.2
        rows = []
        for idx in range(30):
            close = 200 - idx * 3.0  # declining
            rows.append({
                "open": close + 1, "high": close + 2, "low": close - 1, "close": close,
                "volume": 1_000_000,
            })
        # Last candle near 138.2
        rows[-1]["close"] = 138.5
        rows[-1]["open"] = 139.0
        rows[-1]["high"] = 140.0
        rows[-1]["low"] = 137.0
        df = pd.DataFrame(rows)
        r = fibonacci_factor(df, swing_n=3)
        assert r.name == "FIBONACCI"
        assert r.weight == 5

    def test_full_retrace_bearish(self) -> None:
        # Prior 24 candles establish swing_low = 99, swing_high = 101
        rows = []
        base_row = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000_000}
        for _ in range(24):
            rows.append(base_row.copy())
        # Last candle closes below prior swing_low of 99
        rows.append({"open": 95.0, "high": 96.0, "low": 91.0, "close": 92.0, "volume": 1_000_000})
        df = pd.DataFrame(rows)
        r = fibonacci_factor(df)
        # swing_high=101, swing_low=99 from prior; close=92 < 99 → full retrace
        assert r.score == pytest.approx(-0.5)

    def test_score_in_range(self) -> None:
        df = _trending_up(30)
        r = fibonacci_factor(df)
        assert -1.0 <= r.score <= 1.0


class TestInstitutionalFlow:
    def test_fii_strong_buy(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("3000"),
            dii_net_5d=Decimal("500"),
        )
        assert r.score == pytest.approx(+0.5)

    def test_fii_strong_sell(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("-3000"),
            dii_net_5d=Decimal("500"),
        )
        assert r.score < 0

    def test_both_buying(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("2500"),
            dii_net_5d=Decimal("2000"),
        )
        assert r.score == pytest.approx(+0.7)

    def test_dii_absorbing(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("-2500"),
            dii_net_5d=Decimal("2000"),
        )
        # FII selling > threshold → -0.5; DII absorbing → +0.3 → net -0.2
        assert r.score == pytest.approx(-0.2, abs=0.01)

    def test_block_deal_buy_adds(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("2500"),
            dii_net_5d=Decimal("0"),
            stock_block_deal_net_cr=Decimal("100"),
        )
        assert r.score >= 0.5  # fii buy + block buy

    def test_neutral_flows(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("100"),
            dii_net_5d=Decimal("100"),
        )
        assert r.score == 0.0  # below thresholds, not both buying since both < 2000/1500

    def test_clamped_to_one(self) -> None:
        r = fii_dii_factor(
            fii_net_5d=Decimal("9000"),
            dii_net_5d=Decimal("9000"),
            stock_block_deal_net_cr=Decimal("9000"),
        )
        assert r.score <= 1.0
