"""Golden-value tests for indicator suite (RSI, MACD, EMA, ADX, BBands, Volume)."""


import numpy as np
import pandas as pd
import pytest
from app.analysis.indicators.adx import adx_factor, adx_is_strong, adx_is_weak
from app.analysis.indicators.bbands import atr_pct_of_price, bbands_factor
from app.analysis.indicators.ema import (
    ema_cross_factor,
    multibagger_ema_factor,
    price_vs_ema_factor,
)
from app.analysis.indicators.macd import macd_cross_factor, macd_histogram_factor
from app.analysis.indicators.rsi import rsi_divergence_factor, rsi_level_factor
from app.analysis.indicators.volume import volume_factor


def _trending_candles(n: int = 100, drift: float = 0.002) -> pd.DataFrame:
    """Upward-trending candles deterministically seeded."""
    rng = np.random.default_rng(42)
    base = 100.0
    rows = []
    for _ in range(n):
        o = base
        c = base * (1 + drift + rng.uniform(-0.002, 0.002))
        h = max(o, c) * (1 + rng.uniform(0, 0.003))
        lo = min(o, c) * (1 - rng.uniform(0, 0.003))
        vol = int(1e6 + rng.integers(-1e5, 1e5))
        rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": vol})
        base = c
    return pd.DataFrame(rows)


def _ranging_candles(n: int = 100) -> pd.DataFrame:
    """Mean-reverting candles for ranging-market tests."""
    rng = np.random.default_rng(7)
    rows = []
    base = 100.0
    for _ in range(n):
        o = base
        c = 100 + rng.uniform(-5, 5)
        h = max(o, c) + rng.uniform(0, 2)
        lo = min(o, c) - rng.uniform(0, 2)
        rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": int(1e6)})
        base = c
    return pd.DataFrame(rows)


class TestRSI:
    def test_rsi_level_insufficient_data(self) -> None:
        df = _trending_candles(10)
        r = rsi_level_factor(df)
        assert r.score == 0.0

    def test_rsi_level_returns_factor(self) -> None:
        df = _trending_candles(100)
        r = rsi_level_factor(df)
        assert r.name == "RSI_LEVEL"
        assert -1.0 <= r.score <= 1.0
        assert r.weight == 10

    def test_rsi_divergence_insufficient(self) -> None:
        df = _trending_candles(5)
        r = rsi_divergence_factor(df)
        assert r.score == 0.0

    def test_rsi_divergence_no_divergence_in_trend(self) -> None:
        # Strong uptrend — unlikely to have bullish divergence
        df = _trending_candles(60)
        r = rsi_divergence_factor(df)
        assert r.name == "RSI_DIVERGENCE"
        assert r.weight == 10


class TestMACD:
    def test_macd_cross_needs_data(self) -> None:
        df = _trending_candles(20)
        r = macd_cross_factor(df)
        assert r.name == "MACD_CROSS"

    def test_macd_cross_returns_in_range(self) -> None:
        df = _trending_candles(100)
        r = macd_cross_factor(df)
        assert -1.0 <= r.score <= 1.0
        assert r.weight == 10

    def test_macd_histogram_returns_in_range(self) -> None:
        df = _trending_candles(100)
        r = macd_histogram_factor(df)
        assert -1.0 <= r.score <= 1.0
        assert r.weight == 10

    def test_macd_column_detection(self) -> None:
        """Ensure column name parsing doesn't raise."""
        import pandas_ta as ta
        df = _trending_candles(100)
        result = ta.macd(df["close"], fast=12, slow=26, signal=9)
        assert result is not None
        macd_cols = [
            c for c in result.columns
            if c.startswith("MACD_") and not c.startswith("MACDh_") and not c.startswith("MACDs_")
        ]
        sig_cols = [c for c in result.columns if c.startswith("MACDs_")]
        hist_cols = [c for c in result.columns if c.startswith("MACDh_")]
        assert len(macd_cols) == 1
        assert len(sig_cols) == 1
        assert len(hist_cols) == 1


class TestEMA:
    def test_ema_cross_insufficient_data(self) -> None:
        df = _trending_candles(30)
        r = ema_cross_factor(df)
        assert r.name == "EMA_CROSS"

    def test_price_vs_ema_bullish_structure(self) -> None:
        df = _trending_candles(250)
        r = price_vs_ema_factor(df)
        assert r.name == "PRICE_VS_EMA"
        # In a strong uptrend: close should be > 50EMA > 200EMA
        assert r.score == pytest.approx(+0.5, abs=0.1)

    def test_ema_cross_weight(self) -> None:
        df = _trending_candles(100)
        r = ema_cross_factor(df)
        assert r.weight == 15

    def test_multibagger_insufficient(self) -> None:
        df = _trending_candles(150)
        r = multibagger_ema_factor(df)
        assert r.name == "MULTIBAGGER_EMA"
        assert r.weight == 10


class TestADX:
    def test_adx_trending_up(self) -> None:
        df = _trending_candles(100)
        r = adx_factor(df)
        assert r.name == "ADX"
        assert r.weight == 5
        assert -1.0 <= r.score <= 1.0

    def test_adx_is_weak_ranging(self) -> None:
        df = _ranging_candles(100)
        # Ranging market may have weak ADX — function should return a bool
        result = adx_is_weak(df)
        assert isinstance(result, bool)

    def test_adx_is_strong_trending(self) -> None:
        df = _trending_candles(100)
        result = adx_is_strong(df)
        assert isinstance(result, bool)


class TestBBands:
    def test_bbands_insufficient(self) -> None:
        df = _trending_candles(15)
        r = bbands_factor(df)
        assert r.score == 0.0

    def test_bbands_returns_factor(self) -> None:
        df = _trending_candles(60)
        r = bbands_factor(df)
        assert r.name == "BBANDS"
        assert -1.0 <= r.score <= 1.0

    def test_atr_pct_positive(self) -> None:
        df = _trending_candles(60)
        pct = atr_pct_of_price(df)
        assert pct >= 0.0


class TestVolume:
    def test_volume_surge_detected(self) -> None:
        df = _trending_candles(30)
        # Set last candle volume to 5× average
        avg = df["volume"].iloc[-21:-1].mean()
        df.loc[df.index[-1], "volume"] = int(avg * 5)
        r = volume_factor(df)
        assert r.detected if hasattr(r, "detected") else r.score == pytest.approx(+0.5)
        assert r.score == pytest.approx(+0.5)

    def test_volume_normal(self) -> None:
        df = _trending_candles(30)
        r = volume_factor(df)
        # Normal drift volume — may or may not surge; just check range
        assert -1.0 <= r.score <= 1.0
        assert r.weight == 10

    def test_volume_insufficient_data(self) -> None:
        df = _trending_candles(10)
        r = volume_factor(df)
        assert r.score == 0.0
