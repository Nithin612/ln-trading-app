"""U10/U15/U17 — the confidence-breakdown reconstruction (app/signals/confidence_explain).

Read-only reconstruction of a committed signal's confluence arithmetic from its stored
`factor_scores`. The load-bearing property is the divisor: abstaining factors (score == 0)
are EXCLUDED from the denominator — the SRTL surface. The parity test proves the
reconstruction reproduces the frozen scorer's own confidence_pct exactly.
"""

import numpy as np
import pandas as pd
from app.analysis.confluence import score_from_factors
from app.analysis.types import FactorResult
from app.signals.confidence_explain import explain


def _fs(*entries: tuple[str, float, float, str]) -> dict[str, dict[str, object]]:
    """Build a stored `factor_scores` payload: (name, weight, score, explanation)."""
    return {
        name: {"weight": weight, "score": score, "explanation": expl}
        for name, weight, score, expl in entries
    }


def _trending_up(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = 100.0
    rows = []
    for _ in range(n):
        o = base
        c = base * (1.003 + rng.uniform(-0.002, 0.002))
        h = max(o, c) * (1 + rng.uniform(0.001, 0.004))
        lo = min(o, c) * (1 - rng.uniform(0.001, 0.002))
        rows.append(
            {"open": o, "high": h, "low": lo, "close": c,
             "volume": int(1e6 + rng.integers(-1e5, 1e5))}
        )
        base = c
    return pd.DataFrame(rows)


def _choppy(n: int = 200) -> pd.DataFrame:
    """A directionless, mean-reverting tape → low ADX → the scorer's weak-trend floor (+5 over a
    0 min), so most random panels resolve instead of being gated to None."""
    rng = np.random.default_rng(7)
    base = 100.0
    rows = []
    for _ in range(n):
        o = base
        c = base * (1 + rng.uniform(-0.006, 0.006))
        h = max(o, c) * (1 + rng.uniform(0.0, 0.003))
        lo = min(o, c) * (1 - rng.uniform(0.0, 0.003))
        rows.append(
            {"open": o, "high": h, "low": lo, "close": c,
             "volume": int(1e6 + rng.integers(-1e5, 1e5))}
        )
        base = c
    return pd.DataFrame(rows)


class TestSrtlSurface:
    def test_single_scoring_factor_reads_its_own_score(self) -> None:
        """The SRTL failure: one 0.8 factor + abstainers normalises to 80%, NOT diluted."""
        b = explain(
            _fs(
                ("RSI_DIVERGENCE", 15, 0.8, "bullish divergence"),
                ("ADX", 15, 0.0, "no trend"),
                ("EMA_STACK", 12, 0.0, "flat"),
            )
        )
        assert b is not None
        # numerator counts every factor (abstainers contribute 0); denominator counts
        # ONLY the scoring factor's weight — the two 0-score factors drop out.
        assert b.numerator == 12.0        # 15 * 0.8
        assert b.denominator == 15.0      # abstainers excluded
        assert b.normalized == 0.8
        assert b.confidence_pct == 80      # clears the ≥70 gate on one factor
        assert len(b.scoring) == 1
        assert {a.name for a in b.abstained} == {"ADX", "EMA_STACK"}

    def test_same_factors_all_voting_needs_much_more_agreement_for_80(self) -> None:
        """Contrast: with all three scoring, 80% requires the whole panel to agree."""
        b = explain(
            _fs(
                ("RSI_DIVERGENCE", 15, 0.8, ""),
                ("ADX", 15, 0.8, ""),
                ("EMA_STACK", 12, 0.8, ""),
            )
        )
        assert b is not None
        assert b.denominator == 42.0
        assert b.confidence_pct == 80
        assert len(b.scoring) == 3
        assert b.abstained == []


class TestArithmetic:
    def test_sell_direction_and_signed_contributions(self) -> None:
        b = explain(_fs(("DOW_TREND", 20, -0.7, "downtrend"), ("MACD_CROSS", 10, -0.6, "")))
        assert b is not None
        assert b.direction == "SELL"
        assert b.normalized < 0
        assert all(c.contribution < 0 for c in b.scoring)

    def test_scoring_sorted_by_absolute_contribution(self) -> None:
        b = explain(
            _fs(
                ("SMALL", 5, 0.5, ""),      # 2.5
                ("BIG", 20, 0.9, ""),       # 18.0
                ("MID", 10, 0.7, ""),       # 7.0
            )
        )
        assert b is not None
        assert [c.name for c in b.scoring] == ["BIG", "MID", "SMALL"]

    def test_abstainers_sorted_by_weight(self) -> None:
        b = explain(
            _fs(
                ("SCORER", 10, 0.8, ""),
                ("LIGHT", 5, 0.0, ""),
                ("HEAVY", 20, 0.0, ""),
            )
        )
        assert b is not None
        assert [a.name for a in b.abstained] == ["HEAVY", "LIGHT"]


class TestFailOpen:
    def test_none_and_empty(self) -> None:
        assert explain(None) is None
        assert explain({}) is None
        assert explain("not a dict") is None

    def test_all_abstained_is_none(self) -> None:
        """Degenerate divisor — the frozen engine treats this as no signal too."""
        assert explain(_fs(("A", 10, 0.0, ""), ("B", 5, 0.0, ""))) is None

    def test_malformed_entry_is_none_not_raise(self) -> None:
        assert explain({"A": {"weight": 10}}) is None           # missing score
        assert explain({"A": "not a dict"}) is None
        assert explain({"A": {"weight": "x", "score": 1}}) is None  # unparseable

    def test_non_finite_score_is_none_not_raise(self) -> None:
        """A NaN/Inf score must fail open BEFORE the int() truncation, not 500 the endpoint.

        Unreachable via Postgres JSONB (which rejects NaN/Infinity), but the "never raises"
        contract has to hold regardless (quant-verifier, 2026-09-09)."""
        assert explain(_fs(("A", 10, float("nan"), ""), ("B", 5, 0.5, ""))) is None
        assert explain(_fs(("A", 10, float("inf"), ""), ("B", 5, 0.5, ""))) is None
        assert explain({"A": {"weight": float("inf"), "score": 0.8, "explanation": ""}}) is None


class TestParityWithFrozenScorer:
    def test_reconstruction_reproduces_frozen_confidence_exactly(self) -> None:
        """explain() over the STORED payload == the frozen scorer's own confidence_pct.

        Mirrors how signal_service persists factor_scores (score rounded to 4dp, from the
        VOLUME-ADJUSTED factor list). Includes an abstaining factor and VOLUME so both the
        divisor exclusion and the stored-adjusted-score paths are exercised end to end.
        """
        factors = [
            FactorResult("DOW_TREND", 20, +0.9, "uptrend"),
            FactorResult("PRICE_VS_EMA", 15, +0.85, "close>50>200"),
            FactorResult("MACD_CROSS", 10, +0.9, "bullish cross"),
            FactorResult("SR_ZONE", 10, +0.9, "demand zone"),
            FactorResult("RSI_DIVERGENCE", 10, +0.9, "bullish divergence"),
            FactorResult("VOLUME", 10, +0.6, "1.8× avg"),   # adjusted → +0.5 by the scorer
            FactorResult("ADX", 5, 0.0, "no trend"),        # abstains
            FactorResult("FIBONACCI", 5, 0.0, "n/a"),       # abstains
        ]
        candles = _trending_up(200)
        result = score_from_factors(factors, candles, min_confidence=70)
        assert result is not None, "test factors must clear the gate for a parity check"

        # Persist exactly as app/services/signal_service.py does.
        stored = {
            f.name: {"weight": f.weight, "score": round(f.score, 4), "explanation": f.explanation}
            for f in result.factors
        }
        b = explain(stored)
        assert b is not None
        assert b.confidence_pct == result.confidence_pct
        assert b.direction == result.direction
        assert b.normalized == round(result.normalized_score, 10) or abs(
            b.normalized - result.normalized_score
        ) < 1e-9
        # VOLUME stored at its adjusted +0.5, and both zero-score factors excluded.
        assert b.denominator == 75.0
        assert {a.name for a in b.abstained} == {"ADX", "FIBONACCI"}
        vol = next(c for c in b.scoring if c.name == "VOLUME")
        assert vol.score == 0.5

    def test_reconstruction_matches_frozen_across_random_panels(self) -> None:
        """Sweep many random factor panels through the real scorer and assert the reconstruction
        reproduces its confidence_pct AND direction for EVERY non-gated result.

        This is the regression canary for the compensated-summation bug (quant-verifier,
        2026-09-09): a naive `+=` fold disagrees with the frozen `sum()` at ~1e-14 and flips
        int()-truncated confidence by 1 on ~0.27% of panels. Choppy candles keep the ADX gate's
        floor low so most panels resolve. Factor names avoid VOLUME/MULTIBAGGER (no §3 adjustment),
        so the stored score == injected score exactly (round-to-4dp is a no-op at ≤4dp)."""
        rng = np.random.default_rng(20260909)
        candles = _choppy(200)
        checked = 0
        for _ in range(800):
            k = int(rng.integers(3, 9))
            factors = [
                FactorResult(f"F{i}", float(rng.integers(5, 21)),
                             round(float(rng.uniform(-1.0, 1.0)), 4), "")
                for i in range(k)
            ]
            result = score_from_factors(factors, candles, min_confidence=0)
            if result is None:
                continue
            stored = {
                f.name: {"weight": f.weight, "score": round(f.score, 4),
                         "explanation": f.explanation}
                for f in result.factors
            }
            b = explain(stored)
            assert b is not None
            assert b.confidence_pct == result.confidence_pct
            assert b.direction == result.direction
            checked += 1
        # Guard against the sweep passing vacuously (all panels gated to None).
        assert checked >= 100
