"""Degenerate-ratio hygiene — H6.

A ratio whose denominator goes to zero has three honest outcomes and the codebase
used to conflate them: UNDEFINED must be `None` (a zero-risk signal is *not
assessable*, not *the worst possible reward:risk*), OFF-SCALE must be clamped AND
marked (the `RR≈228` artifact must not read as a real 50:1 setup), NORMAL is the
number.

The load-bearing rule these pin is **clamp what you REPORT, never what you
DECIDE** — every gate below computes its verdict from the raw ratio and only
clamps the value it stamps.
"""

from decimal import Decimal, DivisionByZero

import pytest
from app.core.ratios import (
    MAX_R,
    MAX_RR,
    WINSOR_R,
    clamp_ratio,
    clamp_ratio_f,
    format_ratio,
    is_capped,
    safe_ratio,
    safe_ratio_f,
)

D = Decimal


class TestSafeRatio:
    def test_normal_division_is_exact_decimal(self) -> None:
        assert safe_ratio(D("6"), D("4")) == D("1.5")

    @pytest.mark.parametrize("den", [D(0), D("-0"), None])
    def test_undefined_is_none_not_zero(self, den) -> None:
        """The whole point: `0.0` for 'no ratio' is the same number the code prints
        for 'the worst possible ratio', so the two became indistinguishable."""
        assert safe_ratio(D("5"), den) is None

    def test_absent_numerator_is_none(self) -> None:
        assert safe_ratio(None, D("2")) is None

    def test_zero_numerator_is_a_real_zero(self) -> None:
        """0/5 IS defined and IS zero — it must not be swept in with undefined."""
        assert safe_ratio(D(0), D("5")) == D(0)

    def test_never_raises_where_bare_division_would(self) -> None:
        """Decimal/0 raises DivisionByZero — it does NOT produce inf. Guarding
        before the division is what keeps a fail-open gate fail-open."""
        with pytest.raises(DivisionByZero):
            D("5") / D(0)
        assert safe_ratio(D("5"), D(0)) is None

    def test_cap_clamps_and_keeps_sign(self) -> None:
        assert safe_ratio(D("1000"), D("1"), cap=D("50")) == D("50")
        assert safe_ratio(D("-1000"), D("1"), cap=D("50")) == D("-50")

    def test_float_twin_has_the_same_contract(self) -> None:
        assert safe_ratio_f(6.0, 4.0) == 1.5
        assert safe_ratio_f(5.0, 0.0) is None
        assert safe_ratio_f(1000.0, 1.0, cap=50.0) == 50.0


class TestClampAndFormat:
    def test_clamp_is_a_no_op_without_a_cap(self) -> None:
        assert clamp_ratio(D("12345"), None) == D("12345")
        assert clamp_ratio_f(12345.0, None) == 12345.0

    def test_is_capped_marks_only_the_artifacts(self) -> None:
        assert is_capped(D("50"), MAX_RR) is True
        assert is_capped(D("49.99"), MAX_RR) is False
        assert is_capped(None, MAX_RR) is False
        assert is_capped(D("2"), None) is False

    def test_format_keeps_the_three_cases_visually_distinct(self) -> None:
        assert format_ratio(None) == "—"
        assert format_ratio(D("2.14"), cap=MAX_RR) == "2.14"
        assert format_ratio(D("228.06"), cap=MAX_RR) == ">50"
        assert format_ratio(D("-228.06"), cap=MAX_RR) == "->50"

    def test_format_without_a_cap_never_claims_one(self) -> None:
        assert format_ratio(D("228.06")) == "228.06"


class TestConstants:
    def test_the_caps_sit_above_every_threshold_that_reads_them(self) -> None:
        """MAX_RR must exceed every rr floor in the codebase, or clamping a REPORTED
        value could flip a DECISION — the one thing H6 must not do."""
        from app.signals.rr_guard import evaluate
        from app.trading.position_health import HealthParams

        assert MAX_RR > Decimal("1.0")  # rr_guard default rr_min
        assert float(MAX_RR) > HealthParams().rr_floor
        # and the default gate really does use 1.0
        assert evaluate(
            entry=D("100"), stop_loss=D("95"), take_profit=D("110")
        ).rr_min == D("1.0")

    def test_the_three_constants_are_three_different_jobs(self) -> None:
        """They were four literals in four modules, two disagreeing by 1000×.
        Consolidating them must NOT have collapsed them into one number."""
        assert WINSOR_R == 10.0  # statistical winsor on a MEAN
        assert MAX_RR == Decimal("50")  # reporting bound on R:R
        assert MAX_R == Decimal("9999.999")  # Numeric(7,3) column bound
        assert MAX_RR < MAX_R


class TestRrGuardReportsCappedButDecidesRaw:
    """`app/signals/rr_guard.py` — the R:R eligibility overlay."""

    def test_tiny_stop_reports_the_cap_and_says_so(self) -> None:
        from app.signals.rr_guard import evaluate

        # ₹0.04 stop, ₹9 target ⇒ raw R:R 225 — the live RR≈228 archetype.
        v = evaluate(entry=D("237.30"), stop_loss=D("237.26"), take_profit=D("246.30"))
        assert v.rr == MAX_RR
        assert v.rr_capped is True
        assert v.blocked is False  # 225 is nowhere near the 1.0 floor
        assert v.as_payload()["rr_capped"] is True

    def test_a_normal_ratio_is_untouched_and_unmarked(self) -> None:
        from app.signals.rr_guard import evaluate

        v = evaluate(entry=D("100"), stop_loss=D("95"), take_profit=D("110"))
        assert v.rr == D("2")
        assert v.rr_capped is False

    def test_the_block_decision_is_taken_on_the_raw_ratio(self) -> None:
        """A blocked signal (R:R < 1) is far below the cap, so this is really a
        canary: if someone ever computes `blocked` from the clamped value, a cap
        set below a floor would silently unblock everything."""
        from app.signals.rr_guard import evaluate

        v = evaluate(entry=D("100"), stop_loss=D("90"), take_profit=D("105"))
        assert v.rr == D("0.5") and v.blocked is True


class TestDedupRankingCannotBeWonByAnArtifact:
    def test_capped_artifact_does_not_outrank_a_real_signal(self) -> None:
        """`_reward_risk` is a dedup tiebreaker, so it must return a number — but an
        uncapped 228 let a 4-paise stop beat every genuine candidate."""
        from types import SimpleNamespace

        from app.api.v1.signals import _reward_risk

        artifact = SimpleNamespace(
            entry_price=D("237.30"), stop_loss=D("237.26"), take_profit=D("246.30")
        )
        genuine = SimpleNamespace(
            entry_price=D("100"), stop_loss=D("95"), take_profit=D("400")
        )
        assert _reward_risk(artifact) == float(MAX_RR)
        assert _reward_risk(genuine) == float(MAX_RR)  # both clamp → created_at decides

    def test_zero_risk_signal_sorts_last(self) -> None:
        from types import SimpleNamespace

        from app.api.v1.signals import _reward_risk

        s = SimpleNamespace(entry_price=D("100"), stop_loss=D("100"), take_profit=D("110"))
        assert _reward_risk(s) == 0.0


class TestPositionHealthReportsCappedButCutsRaw:
    """`app/trading/position_health.py` — `rr_remaining` reaches the API
    (`app/schemas/trading.py`) and therefore the UI."""

    def _assess(self, *, price, stop_loss, take_profit):
        from datetime import UTC, datetime

        from app.trading.position_health import assess_position_health

        return assess_position_health(
            side="LONG",
            entry=D("100"),
            current_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime_er=None,
            validity_until=None,
            now=datetime(2026, 9, 5, tzinfo=UTC),
        )

    def test_rr_remaining_is_clamped_before_it_reaches_the_api(self) -> None:
        """A long a paise above its stop has a genuinely enormous remaining R:R —
        correct (little left to lose, much left to gain) and correctly not a cut,
        but it used to render as a five-figure "reward:risk" in the UI."""
        h = self._assess(price=D("95.01"), stop_loss=D("95"), take_profit=D("120"))
        assert h.rr_remaining == pytest.approx(float(MAX_RR))

    def test_a_genuinely_inverted_position_is_still_cut(self) -> None:
        """The clamp must not have swallowed the RR_INVERTED cut — it fires on the
        RAW ratio."""
        from app.trading.position_health import HealthVerdict

        h = self._assess(price=D("99"), stop_loss=D("90"), take_profit=D("101"))
        assert h.rr_remaining == pytest.approx(2 / 9)
        assert h.verdict is HealthVerdict.CUT
