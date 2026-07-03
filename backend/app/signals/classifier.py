"""Signal classifier — maps timeframe + factor profile to classification.

Implements SIGNAL_ENGINE.md §4.
"""

from app.analysis.types import FactorResult


def classify_signal(
    timeframe: str,
    factors: list[FactorResult],
    is_multibagger: bool = False,
) -> str:
    """Return 'scalp' | 'intraday' | 'swing' | 'positional'."""
    if timeframe in ("1m", "5m"):
        return "scalp"
    if timeframe in ("15m", "1h"):
        return "intraday"
    if timeframe == "1d":
        if is_multibagger:
            return "positional"
        return "swing"
    if timeframe == "1w":
        return "positional"
    # fallback: intraday for unrecognized timeframes
    return "intraday"
