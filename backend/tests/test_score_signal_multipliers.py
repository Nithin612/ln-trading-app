"""score_signal weight_multipliers seam (Phase-3 pre-work, closes the
slice-7 gap).

The services dispatch must reproduce the exact BacktestEngine sequence
(run_all_factors → apply_weight_multipliers → score_from_factors) so a
multiplier-carrying profile scores identically in the live pipeline and
the walk-forward. No DB — pure engine math on a deterministic fixture.
"""

import numpy as np
import pandas as pd
import pytest
from app.analysis.confluence import run_all_factors, score_from_factors
from app.backtest.engine import apply_weight_multipliers
from app.core.config import settings
from app.services.signal_service import score_signal

# Doubling the structure group keeps this fixture above the strong-ADX
# confidence floor (65) while visibly changing the outcome (68 → 67);
# heavier reshuffles push it under the floor and both paths return None,
# which would make the equality vacuous.
MULTIPLIERS = {"structure": 2.0}


def _trending_candles(n: int = 200) -> pd.DataFrame:
    """Seeded drift-plus-chop series that deterministically clears the
    confluence gate (BUY, confidence 68 at min_confidence=1) — pinned by
    an explicit not-None assertion in the tests, so an engine/pandas-ta
    change that stops it firing fails loudly instead of vacuously."""
    rng = np.random.default_rng(2)
    base, rows = 100.0, []
    for i in range(n):
        o = base
        c = base * (1 + 0.0005 + rng.uniform(-0.01, 0.01))
        rows.append(
            {
                "open": o,
                "high": max(o, c) * (1 + rng.uniform(0.001, 0.004)),
                "low": min(o, c) * (1 - rng.uniform(0.001, 0.004)),
                "close": c,
                "volume": int(1e6 * (1.5 if i > n - 6 else 1.0) + rng.integers(-1e5, 1e5)),
            }
        )
        base = c
    df = pd.DataFrame(rows)
    df.index = pd.date_range("2026-01-05", periods=n, freq="D", tz="UTC")
    return df


def _fields(result):
    return (
        result.direction,
        result.confidence_pct,
        result.normalized_score,
        [(f.name, f.weight, f.score) for f in result.factors],
    )


class TestMultiplierSeam:
    def test_matches_the_backtest_engine_sequence_exactly(self) -> None:
        candles = _trending_candles()
        via_service = score_signal(
            candles, timeframe="1d", min_confidence=1, weight_multipliers=MULTIPLIERS
        )
        reference = score_from_factors(
            apply_weight_multipliers(run_all_factors(candles, "1d"), MULTIPLIERS),
            candles,
            1,
        )
        assert via_service is not None and reference is not None
        assert _fields(via_service) == _fields(reference)
        # and the multipliers actually bit: trend weights differ from base
        base = score_signal(candles, timeframe="1d", min_confidence=1)
        assert base is not None
        base_weights = {f.name: f.weight for f in base.factors}
        assert any(
            f.weight != base_weights[f.name] for f in via_service.factors
        ), "multipliers were silently dropped"

    def test_empty_multipliers_identical_to_frozen_path(self) -> None:
        candles = _trending_candles()
        assert score_signal(candles, timeframe="1d", min_confidence=1) is not None
        assert _fields(
            score_signal(candles, timeframe="1d", min_confidence=1, weight_multipliers={})
        ) == _fields(score_signal(candles, timeframe="1d", min_confidence=1))

    def test_rust_engine_refuses_multipliers_on_the_tradecore_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tradecore.score_signal has no multiplier input — silently
        unscaled weights could flip decisions, so the 1d dispatch fails
        loud (same discipline as the flows guard)."""
        monkeypatch.setattr(settings, "engine_impl", "rust")
        with pytest.raises(NotImplementedError, match="weight_multipliers"):
            score_signal(
                _trending_candles(), timeframe="1d", weight_multipliers={"trend": 2.0}
            )

    def test_rust_intraday_fallback_still_applies_multipliers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Off-1d the python reference answers under ENGINE_IMPL=rust —
        and it CAN apply multipliers, so it must (bug-hunter LOW,
        2026-07-09: guarding first blacked out intraday multiplier
        profiles on a rust deployment)."""
        candles = _trending_candles()
        via_python = score_signal(
            candles, timeframe="15m", min_confidence=1, weight_multipliers=MULTIPLIERS
        )
        monkeypatch.setattr(settings, "engine_impl", "rust")
        via_rust_fallback = score_signal(
            candles, timeframe="15m", min_confidence=1, weight_multipliers=MULTIPLIERS
        )
        assert (via_rust_fallback is None) == (via_python is None)
        if via_python is not None and via_rust_fallback is not None:
            assert _fields(via_rust_fallback) == _fields(via_python)
