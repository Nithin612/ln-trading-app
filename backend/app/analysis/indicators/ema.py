"""EMA-based indicators.

Covers:
  - EMA cross (20 crosses 50) — weight 15, score ±0.6
  - Price vs EMA structure (close > 50 EMA > 200 EMA) — weight 15, score ±0.5
  - Multibagger EMA setup (20 within 2% of 200 + breakout) — bonus weight 10, score +0.9

Scores match SIGNAL_ENGINE.md §2.3.
"""

import pandas as pd
import pandas_ta as ta

from app.analysis.types import FactorResult

_WEIGHT_CROSS = 15
_WEIGHT_STRUCTURE = 15
_WEIGHT_MULTIBAGGER = 10


def _ema(series: pd.Series, length: int) -> pd.Series:
    result = ta.ema(series, length=length)
    return result if result is not None else pd.Series(dtype=float)


def ema_cross_factor(candles: pd.DataFrame) -> FactorResult:
    """20 EMA crosses above/below 50 EMA."""
    ema20 = _ema(candles["close"], 20)
    ema50 = _ema(candles["close"], 50)

    if ema20.dropna().empty or ema50.dropna().empty or len(ema20) < 2:
        return FactorResult("EMA_CROSS", _WEIGHT_CROSS, 0.0, "insufficient data for EMA cross")

    e20_now, e20_prev = float(ema20.iloc[-1]), float(ema20.iloc[-2])
    e50_now, e50_prev = float(ema50.iloc[-1]), float(ema50.iloc[-2])

    if e20_prev <= e50_prev and e20_now > e50_now:
        return FactorResult(
            "EMA_CROSS", _WEIGHT_CROSS, +0.6,
            f"20 EMA golden cross above 50 EMA: {e20_now:.2f} > {e50_now:.2f}",
            ["indicator"],
        )
    if e20_prev >= e50_prev and e20_now < e50_now:
        return FactorResult(
            "EMA_CROSS", _WEIGHT_CROSS, -0.6,
            f"20 EMA death cross below 50 EMA: {e20_now:.2f} < {e50_now:.2f}",
            ["indicator"],
        )
    return FactorResult(
        "EMA_CROSS", _WEIGHT_CROSS, 0.0,
        f"No EMA cross: 20 EMA={e20_now:.2f}, 50 EMA={e50_now:.2f}",
    )


def price_vs_ema_factor(candles: pd.DataFrame) -> FactorResult:
    """Close > 50 EMA > 200 EMA → +0.5 (bullish structure)."""
    close_now = float(candles["close"].iloc[-1])
    ema50 = _ema(candles["close"], 50)
    ema200 = _ema(candles["close"], 200)

    if ema50.dropna().empty or ema200.dropna().empty:
        return FactorResult(
            "PRICE_VS_EMA", _WEIGHT_STRUCTURE, 0.0, "insufficient data for EMA structure"
        )

    e50 = float(ema50.iloc[-1])
    e200 = float(ema200.iloc[-1])

    if close_now > e50 > e200:
        return FactorResult(
            "PRICE_VS_EMA", _WEIGHT_STRUCTURE, +0.5,
            f"Bullish: close={close_now:.2f} > 50EMA={e50:.2f} > 200EMA={e200:.2f}",
            ["indicator"],
        )
    if close_now < e50 < e200:
        return FactorResult(
            "PRICE_VS_EMA", _WEIGHT_STRUCTURE, -0.5,
            f"Bearish: close={close_now:.2f} < 50EMA={e50:.2f} < 200EMA={e200:.2f}",
            ["indicator"],
        )
    return FactorResult(
        "PRICE_VS_EMA", _WEIGHT_STRUCTURE, 0.0,
        f"Mixed EMA structure: close={close_now:.2f}, 50EMA={e50:.2f}, 200EMA={e200:.2f}",
    )


def multibagger_ema_factor(candles: pd.DataFrame) -> FactorResult:
    """20 EMA within 2% of 200 EMA + breakout candle (green body ≥ 1.5× avg).

    Only meaningful on 1d timeframe. Returns bonus weight 10 when triggered.
    """
    ema20 = _ema(candles["close"], 20)
    ema200 = _ema(candles["close"], 200)

    if ema20.dropna().empty or ema200.dropna().empty:
        return FactorResult("MULTIBAGGER_EMA", _WEIGHT_MULTIBAGGER, 0.0, "insufficient EMA data")

    e20 = float(ema20.iloc[-1])
    e200 = float(ema200.iloc[-1])

    if e200 == 0:
        return FactorResult("MULTIBAGGER_EMA", _WEIGHT_MULTIBAGGER, 0.0, "200 EMA is zero")

    proximity_pct = abs(e20 - e200) / e200 * 100
    if proximity_pct > 2.0:
        return FactorResult(
            "MULTIBAGGER_EMA", _WEIGHT_MULTIBAGGER, 0.0,
            f"20 EMA not close to 200 EMA: gap={proximity_pct:.2f}%",
        )

    # Check breakout candle: green, body ≥ 1.5× recent average body
    c = candles.iloc[-1]
    body_now = abs(float(c["close"]) - float(c["open"]))
    avg_body = candles["close"].sub(candles["open"]).abs().iloc[-20:].mean()
    breakout = float(c["close"]) > float(c["open"]) and body_now >= 1.5 * float(avg_body)

    if breakout:
        return FactorResult(
            "MULTIBAGGER_EMA", _WEIGHT_MULTIBAGGER, +0.9,
            f"Multibagger setup: 20EMA≈200EMA (gap={proximity_pct:.2f}%) + breakout candle",
            ["indicator", "multibagger"],
        )
    return FactorResult(
        "MULTIBAGGER_EMA", _WEIGHT_MULTIBAGGER, 0.0,
        f"EMAs converging ({proximity_pct:.2f}%) but no breakout candle",
    )
