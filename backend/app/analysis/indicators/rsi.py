"""RSI indicator — level signal and divergence detection.

Uses pandas-ta for calculation; never home-rolled.
Scores match SIGNAL_ENGINE.md §2.3.
"""

import pandas as pd
import pandas_ta as ta

from app.analysis.types import FactorResult

_WEIGHT = 10


def _compute_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    result = ta.rsi(close, length=length)
    if result is None:
        return pd.Series(dtype=float)
    return result


def rsi_level_factor(candles: pd.DataFrame) -> FactorResult:
    """RSI level: between 30–50 and rising → +0.6; between 50–70 and falling → -0.6."""
    rsi = _compute_rsi(candles["close"])
    if len(rsi.dropna()) < 2:
        return FactorResult("RSI_LEVEL", _WEIGHT, 0.0, "insufficient data for RSI")

    last = float(rsi.iloc[-1])
    prev = float(rsi.iloc[-2])

    if 30 <= last <= 50 and last > prev:
        score = +0.6
        explanation = f"RSI={last:.1f} in 30-50 and rising from {prev:.1f}"
    elif 50 < last <= 70 and last < prev:
        score = -0.6
        explanation = f"RSI={last:.1f} in 50-70 and falling from {prev:.1f}"
    elif last < 30:
        score = +0.4
        explanation = f"RSI={last:.1f} oversold (below 30)"
    elif last > 70:
        score = -0.4
        explanation = f"RSI={last:.1f} overbought (above 70)"
    else:
        score = 0.0
        explanation = f"RSI={last:.1f} neutral zone"

    return FactorResult("RSI_LEVEL", _WEIGHT, score, explanation, ["indicator"])


def rsi_divergence_factor(candles: pd.DataFrame, lookback: int = 10) -> FactorResult:
    """Bullish divergence: price makes lower low but RSI makes higher low.
    Bearish divergence: price makes higher high but RSI makes lower high.
    """
    if len(candles) < lookback + 1:
        return FactorResult("RSI_DIVERGENCE", _WEIGHT, 0.0, "insufficient data for divergence")

    window = candles.iloc[-(lookback + 1):]
    rsi = _compute_rsi(candles["close"])
    if len(rsi.dropna()) < lookback + 1:
        return FactorResult("RSI_DIVERGENCE", _WEIGHT, 0.0, "insufficient RSI for divergence")

    rsi_window = rsi.iloc[-(lookback + 1):]
    close_window = window["close"].astype(float)

    price_low_now = float(close_window.iloc[-1])
    price_low_prev = float(close_window.iloc[:-1].min())
    rsi_low_now = float(rsi_window.iloc[-1])
    rsi_low_prev = float(rsi_window.iloc[:-1].min())

    price_high_now = float(close_window.iloc[-1])
    price_high_prev = float(close_window.iloc[:-1].max())
    rsi_high_now = float(rsi_window.iloc[-1])
    rsi_high_prev = float(rsi_window.iloc[:-1].max())

    if price_low_now < price_low_prev and rsi_low_now > rsi_low_prev:
        return FactorResult(
            "RSI_DIVERGENCE", _WEIGHT, +0.8,
            f"Bullish divergence: price LL ({price_low_now:.2f}<{price_low_prev:.2f}) "
            f"but RSI HL ({rsi_low_now:.1f}>{rsi_low_prev:.1f})",
            ["indicator", "divergence"],
        )
    if price_high_now > price_high_prev and rsi_high_now < rsi_high_prev:
        return FactorResult(
            "RSI_DIVERGENCE", _WEIGHT, -0.8,
            f"Bearish divergence: price HH ({price_high_now:.2f}>{price_high_prev:.2f}) "
            f"but RSI LH ({rsi_high_now:.1f}<{rsi_high_prev:.1f})",
            ["indicator", "divergence"],
        )
    return FactorResult("RSI_DIVERGENCE", _WEIGHT, 0.0, "no RSI divergence detected")
