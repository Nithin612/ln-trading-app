"""Fibonacci retracement level detector.

Auto-draws fib from last major swing high → swing low (uptrend retrace) or vice versa.
Scores match SIGNAL_ENGINE.md §2.6.
"""

import pandas as pd

from app.analysis.types import FactorResult

_WEIGHT = 5
_FIB_LEVELS = {
    0.500: +0.4,
    0.618: +0.6,
    0.786: +0.4,
}
_FULL_RETRACE_SCORE = -0.5
_PROXIMITY_PCT = 0.005   # 0.5% tolerance


def _find_last_swing_high_low(candles: pd.DataFrame, n: int = 5) -> tuple[float, float]:
    """Return (swing_high_price, swing_low_price) over the full window."""
    highs = candles["high"].astype(float)
    lows = candles["low"].astype(float)
    return float(highs.max()), float(lows.min())


def fibonacci_factor(candles: pd.DataFrame, swing_n: int = 5) -> FactorResult:
    """Score based on proximity of current close to key Fibonacci retracement levels.

    Swing high/low are computed on prior candles (excluding the current one)
    to avoid look-ahead bias in backtest.
    """
    if len(candles) < 20:
        return FactorResult("FIBONACCI", _WEIGHT, 0.0, "insufficient data for Fibonacci")

    # Use all but the last candle for swing levels
    prior = candles.iloc[:-1]
    swing_high, swing_low = _find_last_swing_high_low(prior, swing_n)
    swing_range = swing_high - swing_low
    if swing_range <= 0:
        return FactorResult("FIBONACCI", _WEIGHT, 0.0, "zero swing range")

    close = float(candles["close"].iloc[-1])

    # Retracement levels (from high, pulling back toward low)
    fib_prices = {ratio: swing_high - ratio * swing_range for ratio in _FIB_LEVELS}

    best_score = 0.0
    best_expl = "No Fibonacci level nearby"

    for ratio, fib_price in fib_prices.items():
        if fib_price <= 0:
            continue
        if abs(close - fib_price) / fib_price <= _PROXIMITY_PCT:
            score = _FIB_LEVELS[ratio]
            expl = (
                f"Price {close:.2f} near Fib {ratio:.3f} retrace at {fib_price:.2f} "
                f"(swing {swing_low:.2f}→{swing_high:.2f})"
            )
            if abs(score) > abs(best_score):
                best_score = score
                best_expl = expl

    # Full retrace: price breaks below swing_low
    if close < swing_low:
        return FactorResult(
            "FIBONACCI", _WEIGHT, _FULL_RETRACE_SCORE,
            f"Price {close:.2f} < swing low {swing_low:.2f} — trend invalidated",
            ["structure"],
        )

    return FactorResult("FIBONACCI", _WEIGHT, best_score, best_expl, ["structure"])
