"""ADX + DI indicator — trend strength filter.

ADX > 25 and +DI > -DI → +0.6 (bullish with trend strength).
ADX > 25 and -DI > +DI → -0.6 (bearish with trend strength).
ADX < 20 → weak trend flag (used by classifier to require +5% confidence).

Scores match SIGNAL_ENGINE.md §2.3.
"""

import pandas as pd
import pandas_ta as ta

from app.analysis.types import FactorResult

_WEIGHT = 5


def adx_factor(candles: pd.DataFrame, length: int = 14) -> FactorResult:
    result = ta.adx(candles["high"], candles["low"], candles["close"], length=length)
    if result is None or result.dropna().empty:
        return FactorResult("ADX", _WEIGHT, 0.0, "insufficient data for ADX")

    adx_col = [c for c in result.columns if c.startswith("ADX_")][0]
    dmp_col = [c for c in result.columns if c.startswith("DMP_")][0]
    dmn_col = [c for c in result.columns if c.startswith("DMN_")][0]

    adx = float(result[adx_col].iloc[-1])
    dmp = float(result[dmp_col].iloc[-1])
    dmn = float(result[dmn_col].iloc[-1])

    if adx > 25:
        if dmp > dmn:
            return FactorResult(
                "ADX", _WEIGHT, +0.6,
                f"ADX={adx:.1f} trending; +DI={dmp:.1f} > -DI={dmn:.1f} bullish",
                ["indicator"],
            )
        return FactorResult(
            "ADX", _WEIGHT, -0.6,
            f"ADX={adx:.1f} trending; -DI={dmn:.1f} > +DI={dmp:.1f} bearish",
            ["indicator"],
        )
    if adx < 20:
        return FactorResult(
            "ADX", _WEIGHT, 0.0,
            f"ADX={adx:.1f} weak trend (< 20) — requires +5% confidence",
            ["weak_trend"],
        )
    return FactorResult(
        "ADX", _WEIGHT, 0.0,
        f"ADX={adx:.1f} moderate (20-25), no strong directional signal",
    )


def adx_is_strong(candles: pd.DataFrame, length: int = 14) -> bool:
    """True when ADX > 40 — allows reduced confidence threshold (65%)."""
    result = ta.adx(candles["high"], candles["low"], candles["close"], length=length)
    if result is None or result.dropna().empty:
        return False
    adx_col = [c for c in result.columns if c.startswith("ADX_")][0]
    return float(result[adx_col].iloc[-1]) > 40


def adx_is_weak(candles: pd.DataFrame, length: int = 14) -> bool:
    """True when ADX < 20 — signals require +5% extra confidence."""
    result = ta.adx(candles["high"], candles["low"], candles["close"], length=length)
    if result is None or result.dropna().empty:
        return False
    adx_col = [c for c in result.columns if c.startswith("ADX_")][0]
    return float(result[adx_col].iloc[-1]) < 20
