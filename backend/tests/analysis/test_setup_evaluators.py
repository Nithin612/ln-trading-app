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

    def test_exact_tie_breaks_by_symbol_not_insertion_order(self) -> None:
        """Live and walk-forward pools have different dict insertion
        orders; an exact pct tie must rank identically on both sides
        (bug-hunter LOW, 2026-07-09) — alphabetically-earlier symbol wins."""
        for cross_section in (
            {"BBB": 0.5, "AAA": 0.5, "CCC": 0.1},
            {"AAA": 0.5, "BBB": 0.5, "CCC": 0.1},  # reversed insertion
        ):
            ctx_a = SetupContext(direction="BUY", symbol="AAA", cross_section=cross_section)
            ctx_b = SetupContext(direction="BUY", symbol="BBB", cross_section=cross_section)
            assert SETUP_EVALUATORS["top_gainer_925"](self.WINDOW, {"top_n": 1}, ctx_a).passed
            assert not SETUP_EVALUATORS["top_gainer_925"](self.WINDOW, {"top_n": 1}, ctx_b).passed

    def test_sell_side_ranks_losers_first(self) -> None:
        ctx = SetupContext(
            direction="SELL",
            symbol="DDD",
            cross_section={"AAA": 1.0, "DDD": -3.0, "EEE": -1.0},
        )
        v = SETUP_EVALUATORS["top_gainer_925"](self.WINDOW, {"top_n": 1}, ctx)
        assert v.passed


def _intraday(*rows: tuple[float, float, float, float], freq: str = "5min") -> pd.DataFrame:
    """Two-session intraday window: half the bars on 2026-06-02, half on
    2026-06-03, both starting 09:15 IST (03:45 UTC)."""
    half = len(rows) // 2
    idx = list(pd.date_range("2026-06-02 03:45", periods=half, freq=freq, tz="UTC")) + list(
        pd.date_range("2026-06-03 03:45", periods=len(rows) - half, freq=freq, tz="UTC")
    )
    df = pd.DataFrame(
        [{"open": o, "high": h, "low": lo, "close": c, "volume": 1000} for o, h, lo, c in rows]
    )
    df.index = pd.DatetimeIndex(idx)
    return df


class TestPrevDayFailClosed:
    """Phase-3 pre-work regression (quant-verifier MEDIUM, 2026-07-07):
    on an intraday window without ctx.prev_day, the old code fell back to
    iloc[-2] — the previous BAR — so "PDH breakout" gated on a five-minute
    range and passed almost anything. It must fail closed instead."""

    # rising 5m bars: decision close 102.4 > previous BAR high 101.9, so
    # the old fallback PASSED this window; true prev-day context is absent.
    WINDOW = _intraday(
        (100.0, 100.5, 99.8, 100.2),
        (100.2, 100.8, 100.0, 100.6),
        (100.6, 101.0, 100.4, 100.9),
        (101.0, 101.5, 100.9, 101.4),
        (101.4, 101.9, 101.2, 101.8),
        (101.8, 102.5, 101.6, 102.4),
    )

    @pytest.mark.parametrize("setup", ["pdh_breakout", "pdl_breakdown", "opening_gap"])
    def test_intraday_window_without_ctx_fails_closed(self, setup: str) -> None:
        direction = "SELL" if setup == "pdl_breakdown" else "BUY"
        v = SETUP_EVALUATORS[setup](self.WINDOW, {}, SetupContext(direction=direction))
        assert not v.passed
        assert "no previous session" in v.context["reason"]

    def test_intraday_window_with_ctx_prev_day_still_evaluates(self) -> None:
        ctx = SetupContext(
            direction="BUY",
            prev_day={"open": 100.0, "high": 101.0, "low": 99.6, "close": 100.0},
        )
        v = SETUP_EVALUATORS["pdh_breakout"](self.WINDOW, {}, ctx)
        assert v.passed  # close 102.4 > true PDH 101.0
        assert v.context["pdh"] == 101.0

    def test_hourly_bars_count_as_intraday(self) -> None:
        window = _intraday(
            (100.0, 100.5, 99.8, 100.2),
            (100.2, 100.8, 100.0, 100.6),
            (100.6, 101.0, 100.4, 100.9),
            (101.0, 101.5, 100.9, 101.4),
            (101.4, 101.9, 101.2, 101.8),
            (101.8, 102.5, 101.6, 102.4),
            freq="1h",
        )
        v = SETUP_EVALUATORS["pdh_breakout"](window, {}, SetupContext(direction="BUY"))
        assert not v.passed

    def test_daily_windows_keep_the_iloc_fallback(self) -> None:
        # 1d windows still derive prev day from the second-to-last row —
        # the walk-forward's 1d goldens replay through this exact path.
        window = _daily((100, 105, 99, 104), (104, 110, 98, 106), (107, 112, 105, 111.5))
        v = SETUP_EVALUATORS["pdh_breakout"](window, {}, SetupContext(direction="BUY"))
        assert v.passed
        assert v.context["pdh"] == 110.0


class TestOpeningGapSessionOpen:
    """Phase-3 pre-work fix: on intraday windows the gap is measured at the
    SESSION open (first bar of the decision session), not the decision
    bar's own open — the old code silently used the latter."""

    PREV = {"open": 99.0, "high": 100.5, "low": 98.5, "close": 100.0}

    def test_gap_measured_at_first_bar_of_session(self) -> None:
        # session opens 103 (+3% vs prev close 100) then fades; decision
        # bar opens 100.5 (+0.5%) — the OLD code failed this window.
        window = _intraday(
            (99.5, 100.2, 99.0, 100.0),
            (100.0, 100.6, 99.8, 100.0),  # prev session
            (103.0, 103.5, 102.0, 102.2),  # session open bar: gap +3%
            (102.2, 102.4, 100.4, 100.6),
            (100.5, 101.0, 100.2, 100.8),  # decision bar opens 100.5
        )
        # 2 bars day one, 3 bars day two
        v = SETUP_EVALUATORS["opening_gap"](
            window, {}, SetupContext(direction="BUY", prev_day=self.PREV)
        )
        assert v.passed
        assert v.context["gap_pct"] == pytest.approx(3.0)

    def test_mid_session_pop_is_not_an_opening_gap(self) -> None:
        # session opens flat (+0.5%); decision bar opens 103 — the OLD
        # code called this a 3% opening gap.
        window = _intraday(
            (99.5, 100.2, 99.0, 100.0),
            (100.0, 100.6, 99.8, 100.0),
            (100.5, 101.0, 100.2, 100.8),  # session open bar: gap +0.5%
            (100.8, 103.2, 100.6, 103.0),
            (103.0, 103.6, 102.8, 103.4),  # decision bar opens 103
        )
        v = SETUP_EVALUATORS["opening_gap"](
            window, {}, SetupContext(direction="BUY", prev_day=self.PREV)
        )
        assert not v.passed
        assert v.context["gap_pct"] == pytest.approx(0.5)

    def test_daily_windows_unchanged(self) -> None:
        window = _daily((98, 101, 97, 100), (103, 106, 102, 105))
        v = SETUP_EVALUATORS["opening_gap"](window, {}, SetupContext(direction="BUY"))
        assert v.passed
        assert v.context["gap_pct"] == pytest.approx(3.0)


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
