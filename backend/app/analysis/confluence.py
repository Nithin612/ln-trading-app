"""Confluence scorer — the heart of the signal engine.

Implements the algorithm from SIGNAL_ENGINE.md §3 exactly.
"""

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from app.analysis.indicators.adx import adx_factor, adx_is_strong, adx_is_weak
from app.analysis.indicators.bbands import bbands_factor
from app.analysis.indicators.ema import (
    ema_cross_factor,
    multibagger_ema_factor,
    price_vs_ema_factor,
)
from app.analysis.indicators.macd import macd_cross_factor, macd_histogram_factor
from app.analysis.indicators.rsi import rsi_divergence_factor, rsi_level_factor
from app.analysis.indicators.volume import volume_factor
from app.analysis.patterns.multi import (
    detect_engulfing,
    detect_harami,
    detect_morning_evening_star,
    detect_piercing_dark_cloud,
)
from app.analysis.patterns.single import (
    detect_hammer,
    detect_hanging_man,
    detect_marubozu,
    detect_shooting_star,
)
from app.analysis.structure.dow import dow_trend_factor
from app.analysis.structure.fibonacci import fibonacci_factor
from app.analysis.structure.institutional import fii_dii_factor
from app.analysis.structure.levels import sr_zone_factor
from app.analysis.types import FactorResult


@dataclass
class ConfluenceResult:
    direction: str          # 'BUY' | 'SELL'
    confidence_pct: int     # 0-100
    normalized_score: float # -1 to +1
    factors: list[FactorResult]
    triggering_patterns: list[str]
    triggering_indicators: list[str]
    is_multibagger: bool = False


def _best_pattern_factor(candles: pd.DataFrame, swing_n: int = 3) -> FactorResult:
    """Evaluate all patterns; return the single highest-magnitude result."""
    close = float(candles["close"].iloc[-1])
    window = candles.iloc[-20:] if len(candles) >= 20 else candles
    high_20 = float(window["high"].max())
    low_20 = float(window["low"].min())
    at_swing_low = abs(close - low_20) / low_20 <= 0.01 if low_20 > 0 else False
    at_swing_high = abs(close - high_20) / high_20 <= 0.01 if high_20 > 0 else False

    candidates = [
        detect_marubozu(candles),
        detect_hammer(candles, at_swing_low=at_swing_low),
        detect_hanging_man(candles, at_swing_high=at_swing_high),
        detect_shooting_star(candles, at_swing_high=at_swing_high),
        detect_engulfing(candles),
        detect_harami(candles),
        detect_piercing_dark_cloud(candles),
        detect_morning_evening_star(candles),
    ]

    best = max(candidates, key=lambda p: abs(p.score))
    tags = ["pattern", "bullish" if best.score > 0 else "bearish"] if best.detected else ["pattern"]
    return FactorResult(
        name=best.name,
        weight=15,
        score=best.score if best.detected else 0.0,
        explanation=best.explanation,
        tags=tags,
    )


def run_all_factors(
    candles: pd.DataFrame,
    timeframe: str = "1d",
    fii_net_5d: Decimal = Decimal("0"),
    dii_net_5d: Decimal = Decimal("0"),
    stock_block_deal_net_cr: Decimal = Decimal("0"),
) -> list[FactorResult]:
    """Run every factor and return the raw list of FactorResult objects."""
    swing_n = 3 if timeframe in ("1m", "5m", "15m") else 5

    close = float(candles["close"].iloc[-1])

    pattern_factor = _best_pattern_factor(candles, swing_n)
    bullish_pattern = pattern_factor.score > 0
    bearish_pattern = pattern_factor.score < 0

    vol_factor = volume_factor(candles)
    breakout_volume = vol_factor.score > 0

    factors: list[FactorResult] = [
        pattern_factor,
        dow_trend_factor(candles, lookback=20, swing_n=swing_n),
        ema_cross_factor(candles),
        price_vs_ema_factor(candles),
        rsi_level_factor(candles),
        rsi_divergence_factor(candles),
        macd_cross_factor(candles),
        macd_histogram_factor(candles),
        vol_factor,
        bbands_factor(candles),
        adx_factor(candles),
        sr_zone_factor(
            candles,
            current_price=close,
            bullish_pattern=bullish_pattern,
            bearish_pattern=bearish_pattern,
            breakout_volume_ok=breakout_volume,
        ),
        fibonacci_factor(candles, swing_n=swing_n),
        fii_dii_factor(fii_net_5d, dii_net_5d, stock_block_deal_net_cr),
    ]

    # Multibagger bonus (1d only)
    if timeframe == "1d":
        mb = multibagger_ema_factor(candles)
        if mb.score > 0:
            factors.append(mb)

    return factors


def score_from_factors(
    factors: list[FactorResult],
    candles: pd.DataFrame,
    min_confidence: int = 70,
) -> ConfluenceResult | None:
    """Score from a pre-built (and optionally weight-overridden) factor list.

    Separated from score_signal so BacktestEngine can inject custom weights.
    """
    total_weighted = sum(f.weight * f.score for f in factors)
    total_weight = sum(f.weight for f in factors if f.score != 0.0)

    if total_weight == 0:
        return None

    normalized = total_weighted / total_weight
    confidence_pct = int(abs(normalized) * 100)

    effective_min = min_confidence
    if adx_is_weak(candles):
        effective_min += 5
    elif adx_is_strong(candles):
        effective_min = max(65, min_confidence - 5)

    if confidence_pct < effective_min:
        return None

    direction = "BUY" if normalized > 0 else "SELL"

    triggering_patterns = [
        f.name for f in factors
        if "pattern" in f.tags and f.score != 0.0
    ]
    triggering_indicators = [
        f.name for f in factors
        if "indicator" in f.tags and f.score != 0.0
    ]

    is_multibagger = any(f.name == "MULTIBAGGER_EMA" and f.score > 0 for f in factors)

    return ConfluenceResult(
        direction=direction,
        confidence_pct=confidence_pct,
        normalized_score=normalized,
        factors=factors,
        triggering_patterns=triggering_patterns,
        triggering_indicators=triggering_indicators,
        is_multibagger=is_multibagger,
    )


def score_signal(
    candles: pd.DataFrame,
    timeframe: str = "1d",
    min_confidence: int = 70,
    fii_net_5d: Decimal = Decimal("0"),
    dii_net_5d: Decimal = Decimal("0"),
    stock_block_deal_net_cr: Decimal = Decimal("0"),
) -> ConfluenceResult | None:
    """Main entry point: run all factors and return a ConfluenceResult or None."""
    factors = run_all_factors(
        candles, timeframe, fii_net_5d, dii_net_5d, stock_block_deal_net_cr
    )
    return score_from_factors(factors, candles, min_confidence)
