"""Volume confirmation factor.

Current candle volume ≥ 1.5× 20-period average → +0.5 (confirms whatever else fired).
Below average or contracting → 0.0 (neutral, not a counter-signal on its own).

Score match SIGNAL_ENGINE.md §2.3.
"""

import pandas as pd

from app.analysis.types import FactorResult

_WEIGHT = 10
_MULTIPLIER_THRESHOLD = 1.5
_AVG_PERIOD = 20


def volume_factor(candles: pd.DataFrame) -> FactorResult:
    if len(candles) < _AVG_PERIOD + 1:
        return FactorResult("VOLUME", _WEIGHT, 0.0, "insufficient data for volume factor")

    avg_vol = float(candles["volume"].iloc[-_AVG_PERIOD - 1 : -1].mean())
    curr_vol = float(candles["volume"].iloc[-1])

    if avg_vol == 0:
        return FactorResult("VOLUME", _WEIGHT, 0.0, "average volume is zero")

    ratio = curr_vol / avg_vol
    if ratio >= _MULTIPLIER_THRESHOLD:
        return FactorResult(
            "VOLUME", _WEIGHT, +0.5,
            f"Volume surge: {curr_vol:,.0f} = {ratio:.2f}× 20-period avg {avg_vol:,.0f}",
            ["indicator", "volume"],
        )
    return FactorResult(
        "VOLUME", _WEIGHT, 0.0,
        f"Volume normal: {curr_vol:,.0f} = {ratio:.2f}× avg (need {_MULTIPLIER_THRESHOLD}×)",
    )
