"""Single-candlestick pattern detectors.

Scores match SIGNAL_ENGINE.md §2.1 exactly.
Each detector takes a DataFrame with columns [open, high, low, close, volume]
and returns a PatternResult for the *last* (most recent) candle.
"""

import pandas as pd

from app.analysis.types import PatternResult


def _body(row: pd.Series) -> float:
    return abs(float(row["close"]) - float(row["open"]))


def _range(row: pd.Series) -> float:
    return float(row["high"]) - float(row["low"])


def _upper_wick(row: pd.Series) -> float:
    return float(row["high"]) - max(float(row["open"]), float(row["close"]))


def _lower_wick(row: pd.Series) -> float:
    return min(float(row["open"]), float(row["close"])) - float(row["low"])


def detect_marubozu(candles: pd.DataFrame) -> PatternResult:
    """Body ≥ 95% of total range."""
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "MARUBOZU")
    ratio = _body(c) / rng
    if ratio >= 0.95:
        if float(c["close"]) >= float(c["open"]):
            return PatternResult(True, +0.8, f"Bullish Marubozu body={ratio:.2%}", "MARUBOZU_BULLISH")  # noqa: E501
        return PatternResult(True, -0.8, f"Bearish Marubozu body={ratio:.2%}", "MARUBOZU_BEARISH")
    return PatternResult(False, 0.0, f"body ratio {ratio:.2%} < 95%", "MARUBOZU")


def detect_doji(candles: pd.DataFrame) -> PatternResult:
    """Body ≤ 5% of total range — indecision signal."""
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "DOJI")
    ratio = _body(c) / rng
    if ratio <= 0.05:
        return PatternResult(True, 0.0, f"Doji body={ratio:.2%}", "DOJI")
    return PatternResult(False, 0.0, f"body ratio {ratio:.2%} > 5%", "DOJI")


def detect_spinning_top(candles: pd.DataFrame) -> PatternResult:
    """Body ≤ 30% of range with similar upper and lower wicks — indecision."""
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "SPINNING_TOP")
    body_ratio = _body(c) / rng
    uw = _upper_wick(c)
    lw = _lower_wick(c)
    if body_ratio <= 0.30 and uw > 0 and lw > 0:
        wick_symmetry = min(uw, lw) / max(uw, lw)
        if wick_symmetry >= 0.5:
            return PatternResult(
                True, 0.0, f"Spinning top body={body_ratio:.2%} sym={wick_symmetry:.2%}",
                "SPINNING_TOP",
            )
    return PatternResult(False, 0.0, "not a spinning top", "SPINNING_TOP")


def detect_hammer(candles: pd.DataFrame, at_swing_low: bool = False) -> PatternResult:
    """Body in upper third of range, lower wick ≥ 2× body.

    at_swing_low=True gives full credit (+0.7).
    Without location context the pattern scores as Paper Umbrella (+0.4).
    """
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "HAMMER")

    body = _body(c)
    lw = _lower_wick(c)
    uw = _upper_wick(c)
    body_top = max(float(c["open"]), float(c["close"]))
    body_in_upper_third = (body_top - float(c["low"])) >= (rng * 2 / 3)

    if body_in_upper_third and body > 0 and lw >= 2 * body and uw <= body:
        if at_swing_low:
            return PatternResult(
                True, +0.7, f"Hammer at swing low lw/body={lw/body:.1f}x", "HAMMER"
            )
        return PatternResult(
            True, +0.4, f"Paper Umbrella (no swing-low confirm) lw/body={lw/body:.1f}x",
            "PAPER_UMBRELLA",
        )
    return PatternResult(False, 0.0, "hammer shape not present", "HAMMER")


def detect_hanging_man(candles: pd.DataFrame, at_swing_high: bool = False) -> PatternResult:
    """Same shape as Hammer but at a swing high after uptrend."""
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "HANGING_MAN")

    body = _body(c)
    lw = _lower_wick(c)
    uw = _upper_wick(c)
    body_top = max(float(c["open"]), float(c["close"]))
    body_in_upper_third = (body_top - float(c["low"])) >= (rng * 2 / 3)

    if body_in_upper_third and body > 0 and lw >= 2 * body and uw <= body and at_swing_high:
        return PatternResult(
            True, -0.6, f"Hanging Man at swing high lw/body={lw/body:.1f}x", "HANGING_MAN"
        )
    return PatternResult(False, 0.0, "hanging man shape/context not present", "HANGING_MAN")


def detect_shooting_star(candles: pd.DataFrame, at_swing_high: bool = False) -> PatternResult:
    """Body in lower third, upper wick ≥ 2× body, at swing high."""
    c = candles.iloc[-1]
    rng = _range(c)
    if rng == 0:
        return PatternResult(False, 0.0, "zero-range candle", "SHOOTING_STAR")

    body = _body(c)
    uw = _upper_wick(c)
    lw = _lower_wick(c)
    body_bot = min(float(c["open"]), float(c["close"]))
    body_in_lower_third = (float(c["high"]) - body_bot) >= (rng * 2 / 3)

    if body_in_lower_third and body > 0 and uw >= 2 * body and lw <= body and at_swing_high:
        return PatternResult(
            True, -0.7, f"Shooting Star at swing high uw/body={uw/body:.1f}x", "SHOOTING_STAR"
        )
    return PatternResult(False, 0.0, "shooting star shape/context not present", "SHOOTING_STAR")
