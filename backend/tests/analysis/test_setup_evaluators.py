"""Setup-condition evaluator goldens (Phase 2 slice 5).

Hand-computed fixtures per testing.md. Setups gate confluence-passed
suggestions (AND semantics, direction-aware) and FAIL CLOSED when their
context is missing — a suggestion is dropped, never guessed.
"""

import pandas as pd
import pytest
from app.profiles.setups import (
    SETUP_EVALUATORS,
    SetupContext,
    evaluate_conditions,
)
from app.schemas.profile import KNOWN_SETUP_TYPES


def _daily(*rows: tuple[float, float, float, float]) -> pd.DataFrame:
    df = pd.DataFrame(
        [{"open": o, "high": h, "low": lo, "close": c, "volume": 10_000} for o, h, lo, c in rows]
    )
    df.index = pd.date_range("2026-06-01", periods=len(df), freq="D", tz="UTC")
    return df


def test_registry_matches_schema_types() -> None:
    assert set(SETUP_EVALUATORS) == KNOWN_SETUP_TYPES


class TestPdhBreakout:
    # prev day: high 110, low 98 · today closes 111.5 (above PDH)
    WINDOW = _daily((100, 105, 99, 104), (104, 110, 98, 106), (107, 112, 105, 111.5))

    def test_buy_needs_close_above_pdh(self) -> None:
        v = SETUP_EVALUATORS["pdh_breakout"](self.WINDOW, {}, SetupContext(direction="BUY"))
        assert v.passed
        assert v.context == {"close": 111.5, "pdh": 110.0}

    def test_buy_fails_below_pdh(self) -> None:
        window = _daily((100, 105, 99, 104), (104, 110, 98, 106), (107, 109, 105, 108))
        v = SETUP_EVALUATORS["pdh_breakout"](window, {}, SetupContext(direction="BUY"))
        assert not v.passed

    def test_sell_checks_pdl_side(self) -> None:
        window = _daily((100, 105, 99, 104), (104, 110, 98, 106), (99, 100, 95, 96))
        v = SETUP_EVALUATORS["pdh_breakout"](window, {}, SetupContext(direction="SELL"))
        assert v.passed  # 96 < PDL 98

    def test_intraday_uses_ctx_prev_day(self) -> None:
        ctx = SetupContext(
            direction="BUY", prev_day={"open": 1, "high": 200.0, "low": 1, "close": 1}
        )
        v = SETUP_EVALUATORS["pdh_breakout"](self.WINDOW, {}, ctx)
        assert not v.passed  # ctx PDH 200 overrides the window-derived 110


class TestPdlBreakdown:
    def test_short_only(self) -> None:
        window = _daily((100, 105, 99, 104), (104, 110, 98, 106), (99, 100, 95, 96))
        buy = SETUP_EVALUATORS["pdl_breakdown"](window, {}, SetupContext(direction="BUY"))
        assert not buy.passed
        sell = SETUP_EVALUATORS["pdl_breakdown"](window, {}, SetupContext(direction="SELL"))
        assert sell.passed


class TestOpeningGap:
    def test_gap_up_for_buy(self) -> None:
        # prev close 100, today opens 103 → +3% ≥ 2%
        window = _daily((98, 101, 97, 100), (103, 106, 102, 105))
        v = SETUP_EVALUATORS["opening_gap"](window, {}, SetupContext(direction="BUY"))
        assert v.passed
        assert v.context["gap_pct"] == pytest.approx(3.0)

    def test_small_gap_fails(self) -> None:
        window = _daily((98, 101, 97, 100), (101, 106, 100, 105))  # +1%
        v = SETUP_EVALUATORS["opening_gap"](window, {}, SetupContext(direction="BUY"))
        assert not v.passed

    def test_custom_threshold_and_sell_side(self) -> None:
        window = _daily((98, 101, 97, 100), (99.4, 99.5, 95, 96))  # −0.6% gap
        v = SETUP_EVALUATORS["opening_gap"](
            window, {"min_gap_pct": 0.5}, SetupContext(direction="SELL")
        )
        assert v.passed


class TestRelativeStrength:
    def test_outperformance_for_buy(self) -> None:
        # stock +10% over 3 sessions, benchmark +2% → excess +8
        window = _daily(
            (100, 101, 99, 100), (101, 103, 100, 103),
            (103, 106, 102, 106), (106, 111, 105, 110),
        )
        bench = pd.Series([100.0, 100.5, 101.0, 102.0], index=window.index)
        ctx = SetupContext(direction="BUY", benchmark_closes=bench)
        v = SETUP_EVALUATORS["relative_strength"](
            window, {"lookback": 3, "min_excess_pct": 5.0}, ctx
        )
        assert v.passed
        assert v.context["excess_pct"] == pytest.approx(8.0)

    def test_fails_closed_without_benchmark(self) -> None:
        window = _daily((100, 101, 99, 100), (101, 103, 100, 103))
        v = SETUP_EVALUATORS["relative_strength"](window, {}, SetupContext(direction="BUY"))
        assert not v.passed
        assert "unavailable" in v.context["reason"]


class TestFactorScore:
    WINDOW = _daily((100, 101, 99, 100), (101, 103, 100, 103))

    def test_buy_gate(self) -> None:
        ctx = SetupContext(direction="BUY", factors={"SR_ZONE": (10.0, 0.9)})
        v = SETUP_EVALUATORS["factor_score"](
            self.WINDOW, {"factor": "SR_ZONE", "min_score": 0.9}, ctx
        )
        assert v.passed

    def test_sell_gate_needs_negative(self) -> None:
        ctx = SetupContext(direction="SELL", factors={"SR_ZONE": (10.0, 0.9)})
        v = SETUP_EVALUATORS["factor_score"](
            self.WINDOW, {"factor": "SR_ZONE", "min_score": 0.9}, ctx
        )
        assert not v.passed

    def test_fails_closed_without_snapshot(self) -> None:
        v = SETUP_EVALUATORS["factor_score"](
            self.WINDOW, {"factor": "SR_ZONE"}, SetupContext(direction="BUY")
        )
        assert not v.passed

    def test_dc1_is_sr_zone_sugar(self) -> None:
        ctx = SetupContext(direction="BUY", factors={"SR_ZONE": (10.0, 0.85)})
        assert SETUP_EVALUATORS["dc1"](self.WINDOW, {}, ctx).passed
        ctx_low = SetupContext(direction="BUY", factors={"SR_ZONE": (10.0, 0.8)})
        assert not SETUP_EVALUATORS["dc1"](self.WINDOW, {}, ctx_low).passed


class TestOrbBreakout:
    def _session(self) -> pd.DataFrame:
        # 5m bars from 09:15 IST (03:45 UTC); OR(15m) = first three bars
        idx = pd.date_range("2026-06-02 03:45", periods=8, freq="5min", tz="UTC")
        rows = [
            (100, 101, 99.5, 100.5),
            (100.5, 101.5, 100, 101),
            (101, 102, 100.5, 101.5),  # OR high = 102, OR low = 99.5
            (101.5, 102.5, 101, 102),
            (102, 103, 101.5, 102.5),
            (102.5, 103.5, 102, 103),
            (103, 103.5, 102.5, 103.2),
            (103.2, 104, 103, 103.8),  # closes above OR high
        ]
        df = pd.DataFrame(
            [{"open": o, "high": h, "low": lo, "close": c, "volume": 1000} for o, h, lo, c in rows]
        )
        df.index = idx
        return df

    def test_breakout_above_opening_range(self) -> None:
        v = SETUP_EVALUATORS["orb_breakout"](self._session(), {}, SetupContext(direction="BUY"))
        assert v.passed
        assert v.context["or_high"] == 102.0

    def test_fails_closed_on_daily_bars(self) -> None:
        window = _daily((100, 101, 99, 100), (101, 103, 100, 103))
        v = SETUP_EVALUATORS["orb_breakout"](window, {}, SetupContext(direction="BUY"))
        assert not v.passed
        assert "intraday" in v.context["reason"]


class TestTopGainer925:
    WINDOW = _daily((100, 101, 99, 100), (101, 103, 100, 103))

    def test_top_gainer_passes_buy(self) -> None:
        ctx = SetupContext(
            direction="BUY",
            symbol="AAA",
            cross_section={"AAA": 4.2, "BBB": 1.0, "CCC": -2.0},
        )
        v = SETUP_EVALUATORS["top_gainer_925"](self.WINDOW, {"top_n": 2}, ctx)
        assert v.passed

    def test_loser_fails_buy_even_in_top_n(self) -> None:
        ctx = SetupContext(direction="BUY", symbol="CCC", cross_section={"CCC": -0.5})
        v = SETUP_EVALUATORS["top_gainer_925"](self.WINDOW, {"top_n": 5}, ctx)
        assert not v.passed  # wrong sign

    def test_fails_closed_without_snapshot(self) -> None:
        v = SETUP_EVALUATORS["top_gainer_925"](
            self.WINDOW, {}, SetupContext(direction="BUY", symbol="AAA")
        )
        assert not v.passed


class TestEvaluateConditions:
    WINDOW = _daily((100, 105, 99, 104), (104, 110, 98, 106), (107, 112, 105, 111.5))

    def test_and_semantics_with_evidence(self) -> None:
        ctx = SetupContext(direction="BUY", factors={"SR_ZONE": (10.0, 0.9)})
        passed, evidence = evaluate_conditions(
            [
                {"type": "pdh_breakout", "params": {}},
                {"type": "factor_score", "params": {"factor": "SR_ZONE", "min_score": 0.9}},
            ],
            self.WINDOW,
            ctx,
        )
        assert passed
        assert evidence["pdh_breakout"]["passed"] is True
        assert evidence["factor_score"]["passed"] is True

    def test_short_circuits_on_first_failure(self) -> None:
        ctx = SetupContext(direction="BUY")  # no factor snapshot
        passed, evidence = evaluate_conditions(
            [
                {"type": "factor_score", "params": {"factor": "SR_ZONE"}},
                {"type": "pdh_breakout", "params": {}},
            ],
            self.WINDOW,
            ctx,
        )
        assert not passed
        assert "factor_score" in evidence
        assert "pdh_breakout" not in evidence  # never evaluated

    def test_empty_conditions_pass(self) -> None:
        passed, evidence = evaluate_conditions([], self.WINDOW, SetupContext(direction="BUY"))
        assert passed
        assert evidence == {}
