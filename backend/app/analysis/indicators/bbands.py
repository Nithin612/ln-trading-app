"""Bollinger Bands indicator.

Bullish: close touches lower band then closes back inside on next candle → +0.5.
Bearish: close touches upper band then closes back inside on next candle → -0.5.

Scores match SIGNAL_ENGINE.md §2.3.
"""

import pandas as pd
import pandas_ta as ta

from app.analysis.types import FactorResult

_WEIGHT = 10


def bbands_factor(candles: pd.DataFrame, length: int = 20, std: float = 2.0) -> FactorResult:
    result = ta.bbands(candles["close"], length=length, std=std)  # type: ignore[arg-type]
    if result is None or len(result.dropna()) < 2:
        return FactorResult("BBANDS", _WEIGHT, 0.0, "insufficient data for Bollinger Bands")

    lower_col = [c for c in result.columns if c.startswith("BBL_")][0]
    upper_col = [c for c in result.columns if c.startswith("BBU_")][0]
    mid_col   = [c for c in result.columns if c.startswith("BBM_")][0]

    lower_prev = float(result[lower_col].iloc[-2])
    upper_prev = float(result[upper_col].iloc[-2])
    close_prev = float(candles["close"].iloc[-2])
    close_now  = float(candles["close"].iloc[-1])
    lower_now  = float(result[lower_col].iloc[-1])
    upper_now  = float(result[upper_col].iloc[-1])
    mid_now    = float(result[mid_col].iloc[-1])

    # Touch lower band, then recover inside
    if close_prev <= lower_prev and close_now > lower_now:
        return FactorResult(
            "BBANDS", _WEIGHT, +0.5,
            f"BB bullish reversal: prev close {close_prev:.2f} ≤ lower {lower_prev:.2f}, "
            f"now {close_now:.2f} > lower {lower_now:.2f}",
            ["indicator"],
        )
    # Touch upper band, then pull back inside
    if close_prev >= upper_prev and close_now < upper_now:
        return FactorResult(
            "BBANDS", _WEIGHT, -0.5,
            f"BB bearish reversal: prev close {close_prev:.2f} ≥ upper {upper_prev:.2f}, "
            f"now {close_now:.2f} < upper {upper_now:.2f}",
            ["indicator"],
        )
    return FactorResult(
        "BBANDS", _WEIGHT, 0.0,
        f"No BB reversal signal. Close={close_now:.2f}, mid={mid_now:.2f}",
    )


def atr_pct_of_price(candles: pd.DataFrame, length: int = 14) -> float:
    """ATR as % of last close price — used by classifier to flag volatile regimes."""
    result = ta.atr(candles["high"], candles["low"], candles["close"], length=length)
    if result is None or result.dropna().empty:
        return 0.0
    close = float(candles["close"].iloc[-1])
    if close == 0:
        return 0.0
    return float(result.iloc[-1]) / close * 100
