"""Multi-candlestick pattern detectors.

Scores match SIGNAL_ENGINE.md §2.2 exactly.
All detectors operate on the *last N candles* of the passed DataFrame.
"""

import pandas as pd

from app.analysis.types import PatternResult


def _is_green(c: pd.Series) -> bool:
    return float(c["close"]) >= float(c["open"])


def _is_red(c: pd.Series) -> bool:
    return float(c["close"]) < float(c["open"])


def _body_top(c: pd.Series) -> float:
    return max(float(c["open"]), float(c["close"]))


def _body_bot(c: pd.Series) -> float:
    return min(float(c["open"]), float(c["close"]))


def detect_engulfing(candles: pd.DataFrame) -> PatternResult:
    """Bullish/Bearish Engulfing — second candle body fully covers prior body."""
    if len(candles) < 2:
        return PatternResult(False, 0.0, "need ≥2 candles", "ENGULFING")
    prev, curr = candles.iloc[-2], candles.iloc[-1]

    if _is_red(prev) and _is_green(curr):
        if _body_bot(curr) <= _body_bot(prev) and _body_top(curr) >= _body_top(prev):
            return PatternResult(
                True, +0.9,
                "Bullish Engulfing curr_body covers prev_body",
                "BULLISH_ENGULFING",
            )
    if _is_green(prev) and _is_red(curr):
        if _body_top(curr) >= _body_top(prev) and _body_bot(curr) <= _body_bot(prev):
            return PatternResult(
                True, -0.9,
                "Bearish Engulfing curr_body covers prev_body",
                "BEARISH_ENGULFING",
            )
    return PatternResult(False, 0.0, "no engulfing pattern", "ENGULFING")


def detect_harami(candles: pd.DataFrame) -> PatternResult:
    """Bullish/Bearish Harami — small candle inside prior body."""
    if len(candles) < 2:
        return PatternResult(False, 0.0, "need ≥2 candles", "HARAMI")
    prev, curr = candles.iloc[-2], candles.iloc[-1]

    inside = _body_bot(curr) >= _body_bot(prev) and _body_top(curr) <= _body_top(prev)
    if not inside:
        return PatternResult(False, 0.0, "second candle not inside first body", "HARAMI")

    if _is_red(prev) and _is_green(curr):
        return PatternResult(True, +0.5, "Bullish Harami", "BULLISH_HARAMI")
    if _is_green(prev) and _is_red(curr):
        return PatternResult(True, -0.5, "Bearish Harami", "BEARISH_HARAMI")
    return PatternResult(False, 0.0, "harami colors don't match", "HARAMI")


def detect_piercing_dark_cloud(candles: pd.DataFrame) -> PatternResult:
    """Piercing Pattern (bullish) or Dark Cloud Cover (bearish)."""
    if len(candles) < 2:
        return PatternResult(False, 0.0, "need ≥2 candles", "PIERCING_DCC")
    prev, curr = candles.iloc[-2], candles.iloc[-1]

    prev_body_mid = (_body_bot(prev) + _body_top(prev)) / 2

    # Piercing: red → green opening below prev close, closing > 50% into red body
    if _is_red(prev) and _is_green(curr):
        if (float(curr["open"]) < float(prev["close"]) and
                float(curr["close"]) > prev_body_mid and
                float(curr["close"]) < float(prev["open"])):
            return PatternResult(
                True, +0.7,
                f"Piercing Pattern closes {float(curr['close']):.2f} > mid {prev_body_mid:.2f}",
                "PIERCING_PATTERN",
            )

    # Dark Cloud Cover: green → red opening above prev close, closing < 50% into green body
    if _is_green(prev) and _is_red(curr):
        if (float(curr["open"]) > float(prev["close"]) and
                float(curr["close"]) < prev_body_mid and
                float(curr["close"]) > float(prev["open"])):
            return PatternResult(
                True, -0.7,
                f"Dark Cloud Cover closes {float(curr['close']):.2f} < mid {prev_body_mid:.2f}",
                "DARK_CLOUD_COVER",
            )
    return PatternResult(False, 0.0, "no piercing/dark-cloud pattern", "PIERCING_DCC")


def detect_morning_evening_star(candles: pd.DataFrame) -> PatternResult:
    """Morning Star (bullish) or Evening Star (bearish) — 3-candle patterns.

    Spec §2.2 requires the star's real body to GAP fully beyond the first
    candle's real body (adjudicated 2026-07-05, item G — without it 78% of
    detections were false and the ±0.95 score dominated pattern selection).
    """
    if len(candles) < 3:
        return PatternResult(False, 0.0, "need ≥3 candles", "STAR")
    first, star, third = candles.iloc[-3], candles.iloc[-2], candles.iloc[-1]

    first_body_mid = (_body_bot(first) + _body_top(first)) / 2

    # Morning Star: red → small star gapping below first body → green closing
    # > 50% into first red
    if _is_red(first) and _is_green(third):
        star_small = abs(float(star["close"]) - float(star["open"])) < abs(
            float(first["close"]) - float(first["open"])
        ) * 0.5
        gaps_down = _body_top(star) < _body_bot(first)
        third_recovers = float(third["close"]) > first_body_mid
        if star_small and gaps_down and third_recovers:
            return PatternResult(
                True, +0.95,
                f"Morning Star third_close={float(third['close']):.2f} > mid={first_body_mid:.2f}",
                "MORNING_STAR",
            )

    # Evening Star: green → small star gapping above first body → red closing
    # < 50% into first green
    if _is_green(first) and _is_red(third):
        star_small = abs(float(star["close"]) - float(star["open"])) < abs(
            float(first["close"]) - float(first["open"])
        ) * 0.5
        gaps_up = _body_bot(star) > _body_top(first)
        third_drops = float(third["close"]) < first_body_mid
        if star_small and gaps_up and third_drops:
            return PatternResult(
                True, -0.95,
                f"Evening Star third_close={float(third['close']):.2f} < mid={first_body_mid:.2f}",
                "EVENING_STAR",
            )
    return PatternResult(False, 0.0, "no star pattern", "STAR")
