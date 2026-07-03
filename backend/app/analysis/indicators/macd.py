"""MACD indicator — cross and histogram signals.

Scores match SIGNAL_ENGINE.md §2.3.
Uses pandas-ta for calculation.
"""

import pandas as pd
import pandas_ta as ta

from app.analysis.types import FactorResult

_WEIGHT = 10


def macd_cross_factor(candles: pd.DataFrame) -> FactorResult:
    """MACD line crosses above/below signal line on the last candle."""
    result = ta.macd(candles["close"], fast=12, slow=26, signal=9)
    if result is None or len(result.dropna()) < 2:
        return FactorResult("MACD_CROSS", _WEIGHT, 0.0, "insufficient data for MACD")

    macd_col = [
        c for c in result.columns
        if c.startswith("MACD_") and not c.startswith("MACDh_") and not c.startswith("MACDs_")
    ][0]
    sig_col = [c for c in result.columns if c.startswith("MACDs_")][0]

    macd_now = float(result[macd_col].iloc[-1])
    macd_prev = float(result[macd_col].iloc[-2])
    sig_now = float(result[sig_col].iloc[-1])
    sig_prev = float(result[sig_col].iloc[-2])

    bullish_cross = macd_prev < sig_prev and macd_now >= sig_now
    bearish_cross = macd_prev > sig_prev and macd_now <= sig_now

    if bullish_cross:
        return FactorResult(
            "MACD_CROSS", _WEIGHT, +0.7,
            f"MACD bullish cross: MACD={macd_now:.4f} crossed above signal={sig_now:.4f}",
            ["indicator"],
        )
    if bearish_cross:
        return FactorResult(
            "MACD_CROSS", _WEIGHT, -0.7,
            f"MACD bearish cross: MACD={macd_now:.4f} crossed below signal={sig_now:.4f}",
            ["indicator"],
        )
    return FactorResult(
        "MACD_CROSS", _WEIGHT, 0.0,
        f"No MACD cross. MACD={macd_now:.4f} signal={sig_now:.4f}",
    )


def macd_histogram_factor(candles: pd.DataFrame) -> FactorResult:
    """Histogram rising from negative toward zero → +0.4; falling from positive → -0.4."""
    result = ta.macd(candles["close"], fast=12, slow=26, signal=9)
    if result is None or len(result.dropna()) < 2:
        return FactorResult("MACD_HISTOGRAM", _WEIGHT, 0.0, "insufficient data for MACD histogram")

    hist_col = [c for c in result.columns if c.startswith("MACDh_")][0]
    hist_now = float(result[hist_col].iloc[-1])
    hist_prev = float(result[hist_col].iloc[-2])

    if hist_now < 0 and hist_now > hist_prev:
        return FactorResult(
            "MACD_HISTOGRAM", _WEIGHT, +0.4,
            f"Histogram rising toward zero: {hist_prev:.4f} → {hist_now:.4f}",
            ["indicator"],
        )
    if hist_now > 0 and hist_now < hist_prev:
        return FactorResult(
            "MACD_HISTOGRAM", _WEIGHT, -0.4,
            f"Histogram falling from positive: {hist_prev:.4f} → {hist_now:.4f}",
            ["indicator"],
        )
    return FactorResult(
        "MACD_HISTOGRAM", _WEIGHT, 0.0,
        f"Histogram neutral: {hist_prev:.4f} → {hist_now:.4f}",
    )
