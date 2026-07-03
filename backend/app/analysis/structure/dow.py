"""Dow Theory trend structure detector.

Computes swing highs/lows and determines trend direction.
Scores match SIGNAL_ENGINE.md §2.4.
"""

import pandas as pd

from app.analysis.types import FactorResult

_WEIGHT = 20


def _find_swing_highs(highs: pd.Series, n: int) -> list[int]:
    """Return indices that are swing highs (high > N candles on each side)."""
    idx = []
    for i in range(n, len(highs) - n):
        window = highs.iloc[i - n : i + n + 1]
        if float(highs.iloc[i]) == float(window.max()):
            idx.append(i)
    return idx


def _find_swing_lows(lows: pd.Series, n: int) -> list[int]:
    """Return indices that are swing lows (low < N candles on each side)."""
    idx = []
    for i in range(n, len(lows) - n):
        window = lows.iloc[i - n : i + n + 1]
        if float(lows.iloc[i]) == float(window.min()):
            idx.append(i)
    return idx


def dow_trend_factor(candles: pd.DataFrame, lookback: int = 20, swing_n: int = 3) -> FactorResult:
    """Determine Dow Theory trend from swing highs and lows.

    swing_n=3 for intraday, 5 for daily — caller sets this.
    """
    if len(candles) < lookback + swing_n * 2 + 1:
        return FactorResult("DOW_TREND", _WEIGHT, 0.0, "insufficient data for Dow trend")

    window = candles.iloc[-lookback:]
    highs = window["high"].astype(float).reset_index(drop=True)
    lows = window["low"].astype(float).reset_index(drop=True)

    swing_hi_idx = _find_swing_highs(highs, swing_n)
    swing_lo_idx = _find_swing_lows(lows, swing_n)

    if len(swing_hi_idx) < 2 or len(swing_lo_idx) < 2:
        return FactorResult(
            "DOW_TREND", _WEIGHT, 0.0,
            f"Not enough swing points: {len(swing_hi_idx)} highs, {len(swing_lo_idx)} lows",
        )

    # Use last two swing highs and lows
    sh1, sh2 = swing_hi_idx[-2], swing_hi_idx[-1]
    sl1, sl2 = swing_lo_idx[-2], swing_lo_idx[-1]

    hh = float(highs.iloc[sh2]) > float(highs.iloc[sh1])
    hl = float(lows.iloc[sl2]) > float(lows.iloc[sl1])
    lh = float(highs.iloc[sh2]) < float(highs.iloc[sh1])
    ll = float(lows.iloc[sl2]) < float(lows.iloc[sl1])

    # Check for recent trend break (last 3 candles reversal)
    last3_hi = float(candles["high"].iloc[-3:].max())
    last3_lo = float(candles["low"].iloc[-3:].min())
    last_swing_hi = float(highs.iloc[sh2])
    last_swing_lo = float(lows.iloc[sl2])

    if hh and hl:
        # Check if recent candles broke the uptrend
        if last3_lo < last_swing_lo:
            return FactorResult(
                "DOW_TREND", _WEIGHT, -0.35,
                "Uptrend recently broken (recent low < last swing low) — trend flip signal",
                ["structure"],
            )
        return FactorResult(
            "DOW_TREND", _WEIGHT, +0.7,
            f"Confirmed uptrend: HH ({highs.iloc[sh1]:.2f}→{highs.iloc[sh2]:.2f}) "
            f"and HL ({lows.iloc[sl1]:.2f}→{lows.iloc[sl2]:.2f})",
            ["structure"],
        )

    if lh and ll:
        if last3_hi > last_swing_hi:
            return FactorResult(
                "DOW_TREND", _WEIGHT, +0.35,
                "Downtrend recently broken (recent high > last swing high) — trend flip signal",
                ["structure"],
            )
        return FactorResult(
            "DOW_TREND", _WEIGHT, -0.7,
            f"Confirmed downtrend: LH ({highs.iloc[sh1]:.2f}→{highs.iloc[sh2]:.2f}) "
            f"and LL ({lows.iloc[sl1]:.2f}→{lows.iloc[sl2]:.2f})",
            ["structure"],
        )

    return FactorResult(
        "DOW_TREND", _WEIGHT, 0.0,
        "Mixed swing structure — sideways market",
        ["structure"],
    )
