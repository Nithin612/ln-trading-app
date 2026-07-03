"""Support/Resistance and Demand/Supply zone detector.

S/R lines: swing highs/lows tested ≥2 times.
Zones: demand zone = last red candle before a breakout rally;
       supply zone = last green candle before a breakdown.

Scores match SIGNAL_ENGINE.md §2.5.
"""

from dataclasses import dataclass

import pandas as pd

from app.analysis.types import FactorResult

_WEIGHT = 10
_PROXIMITY_PCT = 0.005  # 0.5%
_MIN_STRENGTH = 2       # tested at least twice


@dataclass
class Zone:
    price_lower: float
    price_upper: float
    zone_type: str    # 'support' | 'resistance' | 'demand_zone' | 'supply_zone'
    strength: int = 1


def detect_sr_levels(candles: pd.DataFrame, n: int = 3) -> list[Zone]:
    """Return S/R zones where swing highs/lows were tested ≥ MIN_STRENGTH times."""
    highs = candles["high"].astype(float)
    lows = candles["low"].astype(float)

    # Collect all swing pivot prices
    resistance_prices: list[float] = []
    support_prices: list[float] = []

    for i in range(n, len(candles) - n):
        if float(highs.iloc[i]) == float(highs.iloc[i - n : i + n + 1].max()):
            resistance_prices.append(float(highs.iloc[i]))
        if float(lows.iloc[i]) == float(lows.iloc[i - n : i + n + 1].min()):
            support_prices.append(float(lows.iloc[i]))

    # Cluster nearby prices (within 0.5% of each other) and count touches
    def cluster(prices: list[float], zone_type: str) -> list[Zone]:
        if not prices:
            return []
        zones: list[Zone] = []
        sorted_p = sorted(prices)
        cluster_prices = [sorted_p[0]]
        for p in sorted_p[1:]:
            if (p - cluster_prices[0]) / cluster_prices[0] <= _PROXIMITY_PCT:
                cluster_prices.append(p)
            else:
                if len(cluster_prices) >= _MIN_STRENGTH:
                    mid = sum(cluster_prices) / len(cluster_prices)
                    zones.append(Zone(
                        price_lower=mid * (1 - _PROXIMITY_PCT),
                        price_upper=mid * (1 + _PROXIMITY_PCT),
                        zone_type=zone_type,
                        strength=len(cluster_prices),
                    ))
                cluster_prices = [p]
        if len(cluster_prices) >= _MIN_STRENGTH:
            mid = sum(cluster_prices) / len(cluster_prices)
            zones.append(Zone(
                price_lower=mid * (1 - _PROXIMITY_PCT),
                price_upper=mid * (1 + _PROXIMITY_PCT),
                zone_type=zone_type,
                strength=len(cluster_prices),
            ))
        return zones

    return cluster(resistance_prices, "resistance") + cluster(support_prices, "support")


def detect_demand_supply_zones(candles: pd.DataFrame) -> list[Zone]:
    """Demand zone: last red candle before a big green rally.
    Supply zone: last green candle before a big red drop.
    A 'big move' is defined as a candle body > 1.5× average body.
    """
    avg_body = candles["close"].sub(candles["open"]).abs().mean()
    zones: list[Zone] = []

    for i in range(1, len(candles)):
        curr = candles.iloc[i]
        prev = candles.iloc[i - 1]
        curr_body = abs(float(curr["close"]) - float(curr["open"]))
        is_big = curr_body > 1.5 * float(avg_body)

        # Demand zone: prev is red, curr is big green
        curr_green = float(curr["close"]) > float(curr["open"])
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        curr_red = float(curr["close"]) < float(curr["open"])
        if is_big and curr_green and prev_red:
            zones.append(Zone(
                price_lower=float(prev["low"]),
                price_upper=float(prev["high"]),
                zone_type="demand_zone",
            ))
        # Supply zone: prev is green, curr is big red
        if is_big and curr_red and prev_green:
            zones.append(Zone(
                price_lower=float(prev["low"]),
                price_upper=float(prev["high"]),
                zone_type="supply_zone",
            ))

    return zones


def sr_zone_factor(  # noqa: C901
    candles: pd.DataFrame,
    current_price: float | None = None,
    bullish_pattern: bool = False,
    bearish_pattern: bool = False,
    breakout_volume_ok: bool = False,
) -> FactorResult:
    """Score based on proximity to S/R zones and demand/supply zones."""
    if current_price is None:
        current_price = float(candles["close"].iloc[-1])

    sr_levels = detect_sr_levels(candles)
    ds_zones = detect_demand_supply_zones(candles)
    all_zones = sr_levels + ds_zones

    best_score = 0.0
    best_expl = "No active S/R zone near current price"

    for zone in all_zones:
        prox_lower = abs(current_price - zone.price_lower) / current_price
        prox_upper = abs(current_price - zone.price_upper) / current_price
        at_level = prox_lower <= _PROXIMITY_PCT or prox_upper <= _PROXIMITY_PCT or (
            zone.price_lower <= current_price <= zone.price_upper
        )
        if not at_level:
            continue

        if zone.zone_type == "support" and bullish_pattern:
            s = +0.8
            e = f"At support {zone.price_lower:.2f}-{zone.price_upper:.2f} with bullish pattern"
        elif zone.zone_type == "resistance" and bearish_pattern:
            s = -0.8
            e = f"At resistance {zone.price_lower:.2f}-{zone.price_upper:.2f} with bearish pattern"
        elif zone.zone_type == "demand_zone" and bullish_pattern:
            s = +0.85
            e = f"At demand zone {zone.price_lower:.2f}-{zone.price_upper:.2f} with reversal (DC1)"
        elif zone.zone_type == "supply_zone" and bearish_pattern:
            s = -0.85
            e = f"At supply zone {zone.price_lower:.2f}-{zone.price_upper:.2f} with reversal"
        elif zone.zone_type == "resistance" and breakout_volume_ok:
            s = +0.9
            e = f"RRBO breakout above resistance {zone.price_upper:.2f} with volume"
        elif zone.zone_type == "support" and breakout_volume_ok:
            s = -0.9
            e = f"Breakdown below support {zone.price_lower:.2f} with volume"
        else:
            continue

        if abs(s) > abs(best_score):
            best_score = s
            best_expl = e

    return FactorResult("SR_ZONE", _WEIGHT, best_score, best_expl, ["structure"])
