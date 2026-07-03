"""Grid search over factor weight multipliers to find best strategy configurations.

Usage:
    from app.backtest.grid_search import PRESETS, run_preset_scan

    results = run_preset_scan(candles_by_stock)
    # returns list of (preset_name, BacktestResult) sorted by Sharpe desc
"""

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from app.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

# ── Named presets ─────────────────────────────────────────────────────────────
# Each preset defines weight multipliers for the six factor groups.
# Groups: pattern, trend, momentum, volume, structure, institutional

PRESETS: dict[str, dict[str, float]] = {
    "balanced": {},  # all multipliers = 1.0 (default)
    "momentum_heavy": {
        "momentum": 1.5,
        "pattern": 0.75,
        "trend": 0.75,
        "structure": 0.75,
    },
    "pattern_heavy": {
        "pattern": 1.75,
        "momentum": 0.75,
        "volume": 0.75,
    },
    "trend_following": {
        "trend": 1.5,
        "momentum": 1.25,
        "structure": 0.75,
        "institutional": 0.5,
    },
    "structure_focused": {
        "structure": 1.5,
        "trend": 1.25,
        "momentum": 0.75,
        "volume": 0.75,
    },
    "volume_confirmed": {
        "volume": 1.75,
        "pattern": 1.25,
        "momentum": 1.0,
        "structure": 0.75,
    },
    "institutional_led": {
        "institutional": 2.0,
        "trend": 1.25,
        "momentum": 0.75,
        "pattern": 0.75,
    },
}


@dataclass
class GridSearchEntry:
    preset_name: str
    weight_multipliers: dict[str, float]
    result: BacktestResult


def run_preset_scan(
    candles_by_stock: dict[str, pd.DataFrame],
    timeframe: str = "1d",
    capital: Decimal = Decimal("100000"),
    risk_pct: Decimal = Decimal("2"),
    min_confidence: int = 70,
    presets: dict[str, dict[str, float]] | None = None,
) -> list[GridSearchEntry]:
    """Run all named presets on the given universe and return ranked results.

    Results are sorted by Sharpe descending, then by win_rate descending.
    """
    if presets is None:
        presets = PRESETS

    entries: list[GridSearchEntry] = []
    for name, multipliers in presets.items():
        cfg = BacktestConfig(
            timeframe=timeframe,
            capital=capital,
            risk_pct=risk_pct,
            min_confidence=min_confidence,
            weight_multipliers=multipliers,
        )
        result = BacktestEngine(cfg).run(candles_by_stock)
        entries.append(GridSearchEntry(
            preset_name=name,
            weight_multipliers=multipliers,
            result=result,
        ))

    entries.sort(key=lambda e: (e.result.sharpe, e.result.win_rate_pct), reverse=True)
    return entries


def run_custom_grid(
    candles_by_stock: dict[str, pd.DataFrame],
    param_grid: dict[str, list[float]],
    timeframe: str = "1d",
    capital: Decimal = Decimal("100000"),
    risk_pct: Decimal = Decimal("2"),
    min_confidence: int = 70,
) -> list[GridSearchEntry]:
    """Enumerate all combinations in param_grid and return ranked results.

    param_grid example:
        {"momentum": [0.75, 1.0, 1.5], "trend": [1.0, 1.5]}
    Produces 3×2 = 6 combinations.
    """
    import itertools

    groups = list(param_grid.keys())
    value_lists = [param_grid[g] for g in groups]

    entries: list[GridSearchEntry] = []
    for values in itertools.product(*value_lists):
        multipliers = dict(zip(groups, values, strict=True))
        label = "_".join(f"{g}{v}" for g, v in multipliers.items())
        cfg = BacktestConfig(
            timeframe=timeframe,
            capital=capital,
            risk_pct=risk_pct,
            min_confidence=min_confidence,
            weight_multipliers=multipliers,
        )
        result = BacktestEngine(cfg).run(candles_by_stock)
        entries.append(GridSearchEntry(
            preset_name=label,
            weight_multipliers=multipliers,
            result=result,
        ))

    entries.sort(key=lambda e: (e.result.sharpe, e.result.win_rate_pct), reverse=True)
    return entries
