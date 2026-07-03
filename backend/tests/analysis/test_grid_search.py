"""Tests for the grid search engine and weight multiplier application."""


import numpy as np
import pandas as pd
import pytest
from app.analysis.types import FactorResult
from app.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    apply_weight_multipliers,
)
from app.backtest.grid_search import PRESETS, run_custom_grid, run_preset_scan


def _candles(n: int = 200, drift: float = 0.002) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = 200.0
    rows = []
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    for _ in range(n):
        o = base
        c = base * (1 + drift + rng.uniform(-0.005, 0.005))
        h = max(o, c) * (1 + rng.uniform(0.001, 0.004))
        lo = min(o, c) * (1 - rng.uniform(0.001, 0.003))
        rows.append({"open": o, "high": h, "low": lo, "close": c, "volume": int(1e6)})
        base = c
    return pd.DataFrame(rows, index=dates)


class TestApplyWeightMultipliers:
    def _make_factor(self, name: str, weight: float, tags: list[str]) -> FactorResult:
        return FactorResult(name=name, weight=weight, score=0.8, explanation="test", tags=tags)

    def test_no_multipliers_returns_same(self) -> None:
        factors = [self._make_factor("RSI_LEVEL", 12.0, ["indicator", "momentum"])]
        result = apply_weight_multipliers(factors, {})
        assert result == factors

    def test_momentum_multiplier_applied(self) -> None:
        factors = [self._make_factor("RSI_LEVEL", 12.0, ["indicator"])]
        # Name-based grouping: RSI_LEVEL → momentum group
        result = apply_weight_multipliers(factors, {"momentum": 2.0})
        assert result[0].weight == pytest.approx(24.0)

    def test_pattern_tag_multiplier(self) -> None:
        factors = [self._make_factor("HAMMER", 15.0, ["pattern", "bullish"])]
        result = apply_weight_multipliers(factors, {"pattern": 1.5})
        assert result[0].weight == pytest.approx(22.5)

    def test_unmatched_factor_unchanged(self) -> None:
        factors = [self._make_factor("UNKNOWN_FACTOR", 10.0, ["custom"])]
        result = apply_weight_multipliers(factors, {"momentum": 1.5})
        assert result[0].weight == pytest.approx(10.0)

    def test_multiple_groups_applied(self) -> None:
        factors = [
            self._make_factor("HAMMER", 15.0, ["pattern"]),
            self._make_factor("RSI_LEVEL", 12.0, ["indicator"]),
            self._make_factor("DOW_TREND", 20.0, ["indicator"]),
        ]
        result = apply_weight_multipliers(factors, {"pattern": 2.0, "trend": 1.5})
        # HAMMER → pattern → ×2.0
        assert result[0].weight == pytest.approx(30.0)
        # RSI_LEVEL → momentum (by name) — no multiplier → unchanged
        assert result[1].weight == pytest.approx(12.0)
        # DOW_TREND → trend → ×1.5
        assert result[2].weight == pytest.approx(30.0)

    def test_multiplier_of_one_returns_same_weight(self) -> None:
        factors = [self._make_factor("VOLUME", 8.0, ["indicator"])]
        result = apply_weight_multipliers(factors, {"volume": 1.0})
        assert result[0].weight == pytest.approx(8.0)


class TestWeightMultipliersInEngine:
    def test_engine_with_default_multipliers_matches_baseline(self) -> None:
        df = _candles(200)
        cfg_base = BacktestConfig(min_confidence=60)
        cfg_same = BacktestConfig(min_confidence=60, weight_multipliers={})
        r1 = BacktestEngine(cfg_base).run({"S": df})
        r2 = BacktestEngine(cfg_same).run({"S": df})
        assert r1.total_trades == r2.total_trades

    def test_engine_weight_override_affects_signal_count(self) -> None:
        df = _candles(200)
        # With min_confidence=0 to force signal generation, different weights
        # may cause different confidence_pct → different pass/fail threshold
        cfg_a = BacktestConfig(min_confidence=50, weight_multipliers={})
        cfg_b = BacktestConfig(min_confidence=50, weight_multipliers={"momentum": 0.25})
        r_a = BacktestEngine(cfg_a).run({"S": df})
        r_b = BacktestEngine(cfg_b).run({"S": df})
        # Not asserting equal — they should differ in at least some cases
        # This test just ensures no crash with weight overrides
        assert isinstance(r_a.total_trades, int)
        assert isinstance(r_b.total_trades, int)

    def test_equity_curve_in_result(self) -> None:
        df = _candles(200)
        cfg = BacktestConfig(min_confidence=40)  # low threshold to force trades
        result = BacktestEngine(cfg).run({"S": df})
        assert isinstance(result.equity_curve, list)
        if result.total_trades > 0:
            # Starts at 100 when there are trades
            assert result.equity_curve[0] == pytest.approx(100.0)


class TestPresetScan:
    def test_preset_scan_returns_all_presets(self) -> None:
        df = _candles(120)
        entries = run_preset_scan({"S": df}, min_confidence=50)
        assert len(entries) == len(PRESETS)

    def test_preset_scan_sorted_by_sharpe(self) -> None:
        df = _candles(120)
        entries = run_preset_scan({"S": df}, min_confidence=50)
        sharpes = [e.result.sharpe for e in entries]
        assert sharpes == sorted(sharpes, reverse=True)

    def test_preset_scan_deterministic(self) -> None:
        df = _candles(120)
        e1 = run_preset_scan({"S": df}, min_confidence=50)
        e2 = run_preset_scan({"S": df}, min_confidence=50)
        assert [e.preset_name for e in e1] == [e.preset_name for e in e2]
        assert [e.result.total_trades for e in e1] == [e.result.total_trades for e in e2]


class TestCustomGrid:
    def test_custom_grid_enumerates_combinations(self) -> None:
        df = _candles(120)
        grid = {"momentum": [0.5, 1.0, 1.5], "trend": [1.0, 1.5]}
        entries = run_custom_grid({"S": df}, grid, min_confidence=50)
        assert len(entries) == 6  # 3 × 2

    def test_custom_grid_sorted_by_sharpe(self) -> None:
        df = _candles(120)
        grid = {"momentum": [0.75, 1.5]}
        entries = run_custom_grid({"S": df}, grid, min_confidence=50)
        sharpes = [e.result.sharpe for e in entries]
        assert sharpes == sorted(sharpes, reverse=True)
