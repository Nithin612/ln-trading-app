"""A38 — the composed restriction registry.

`test_eligibility_preview.py` covers what each gate DECIDES. This file covers the
structural properties that made the composition worth building: that both paths walk one
list, that a new rule lands on every path without anyone remembering, and that a gate
which cannot be judged is reported rather than assumed clear.

Those are exactly the properties the previous arrangement asserted in a comment and did
not have — bug-hunter found the original `unassessed` tripwire was imaginary because it
only ever checked one gate. A property held by data the composer reads is testable; a
property held by a comment is not.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.signal import Signal
from app.signals import eligibility, restrictions
from app.signals.restrictions import EnforcedBy

_ALL_OFF = dict.fromkeys(restrictions.MODED_GATES, "off")


def _cfg(**over: str) -> restrictions.RestrictionConfig:
    modes = dict(_ALL_OFF)
    modes.update(over)
    return restrictions.RestrictionConfig(
        modes=modes,
        min_scoring_factors=2,
        max_dominant_share=Decimal("0.9"),
        min_sl_atr_mult=Decimal("1.0"),
        rr_min=Decimal("1.0"),
        max_chase_r=Decimal("0.33"),
        circuit_proximity_pct=Decimal("1.5"),
        sector_rs_lookback=20,
        sector_rs_min_excess_pct=Decimal("0"),
        market_regime_dma_period=200,
        market_regime_dma_buffer_pct=Decimal("0"),
        market_regime_vix_threshold=Decimal("20"),
        market_regime_market_symbol="NIFTY50",
        liquidity_lookback=20,
        liquidity_min_traded_value=Decimal("0"),
    )


def _signal(**kw: object) -> Signal:
    """An UNSAVED signal — the registry is pure, so no DB is needed."""
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = dict(
        stock_id=1,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="100.0000",
        stop_loss="95.0000",
        take_profit="115.0000",
        suggested_qty=100,
        confidence_pct=80,
        # Two scoring factors: clears the ACTIVE diversity rule, so tests that are not
        # about diversity are not accidentally blocked by it.
        factor_scores={"RSI": {"score": 0.8, "weight": 1.0}, "MACD": {"score": 0.7, "weight": 1.0}},
        headline="BUY TEST",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
        regime="trending (ADX≥25)",
    )
    defaults.update(kw)
    return Signal(**defaults)


def _ctx(**kw: object) -> restrictions.RestrictionContext:
    base: dict[str, object] = dict(
        signal=_signal(), side="LONG", as_of=datetime.now(tz=UTC), allow_offmarket=True,
        available=frozenset({restrictions.CTX_MARKET_PRICE}), market_price=Decimal("100"),
    )
    base.update(kw)
    return restrictions.RestrictionContext(**base)  # type: ignore[arg-type]


class TestRegistryIsCoherent:
    def test_every_moded_gate_is_reachable_from_the_registry(self) -> None:
        """`config_from_settings` and the registry must not drift: a mode with no rule is
        a knob that does nothing, and a rule with no mode raises a KeyError at runtime."""
        reachable: set[str] = set()
        for r in restrictions.REGISTRY:
            if r.gate == restrictions.GATE_ENTRY_QUALITY:
                reachable |= {restrictions.GATE_DIVERSITY, restrictions.GATE_SL_ATR}
            elif r.enforced_by is EnforcedBy.OVERLAY:
                reachable.add(r.gate)
        assert reachable == set(restrictions.MODED_GATES)

    def test_config_from_settings_supplies_every_moded_gate(self) -> None:
        cfg = restrictions.config_from_settings()
        for gate in restrictions.MODED_GATES:
            assert cfg.mode(gate) in ("off", "shadow", "active"), gate

    def test_gate_ids_are_unique(self) -> None:
        ids = [r.gate for r in restrictions.REGISTRY]
        assert len(ids) == len(set(ids))

    def test_a_missing_mode_raises_rather_than_defaulting_to_off(self) -> None:
        """Silently defaulting is how a gate goes quiet. Strictness is the safety net."""
        cfg = restrictions.RestrictionConfig(
            modes={}, min_scoring_factors=2, max_dominant_share=Decimal("0.9"),
            min_sl_atr_mult=Decimal("1.0"), rr_min=Decimal("1.0"), max_chase_r=Decimal("0.33"),
            circuit_proximity_pct=Decimal("1.5"), sector_rs_lookback=20,
            sector_rs_min_excess_pct=Decimal("0"), market_regime_dma_period=200,
            market_regime_dma_buffer_pct=Decimal("0"), market_regime_vix_threshold=Decimal("20"),
            market_regime_market_symbol="NIFTY50", liquidity_lookback=20,
            liquidity_min_traded_value=Decimal("0"),
        )
        with pytest.raises(KeyError):
            restrictions.check(_ctx(), cfg)


class TestOffIsATrueNoOp:
    def test_all_off_yields_no_judgements_and_no_stamps(self) -> None:
        out = restrictions.check(_ctx(), _cfg(), enforced_by=EnforcedBy.OVERLAY)
        assert out.blocked is False
        assert out.judgements == ()
        assert out.stamps() == {}

    def test_a_shadow_gate_stamps_but_does_not_block(self) -> None:
        """Shadow must leave a verdict on the order — that footprint is the entire
        forward-evidence mechanism — while never rejecting."""
        out = restrictions.check(
            _ctx(), _cfg(**{restrictions.GATE_RR: "shadow"}), enforced_by=EnforcedBy.OVERLAY
        )
        assert out.blocked is False
        assert "rr_gate" in out.stamps()


class TestTheFixtureItself:
    def test_the_two_factor_fixture_really_clears_the_active_diversity_rule(self) -> None:
        """A canary on the test data. If `factor_scores` ever stops being read as two
        SCORING factors, every test above would still pass — while silently exercising a
        blocked signal. Pin it: with diversity ACTIVE this fixture must go through."""
        out = restrictions.check(
            _ctx(), _cfg(**{restrictions.GATE_DIVERSITY: "active"}),
            enforced_by=EnforcedBy.OVERLAY,
        )
        assert out.blocked is False, out.reason

    def test_a_single_factor_signal_is_blocked_by_the_same_rule(self) -> None:
        """The other half of the canary — proves the check above can fail."""
        one = _signal(
            factor_scores={
                "RSI_DIVERGENCE": {"weight": 20, "score": 0.8},
                "MACD_CROSS": {"weight": 15, "score": 0.0},
            }
        )
        out = restrictions.check(
            _ctx(signal=one), _cfg(**{restrictions.GATE_DIVERSITY: "active"}),
            enforced_by=EnforcedBy.OVERLAY,
        )
        assert out.blocked is True
        assert out.gate == restrictions.GATE_ENTRY_QUALITY


class TestRegressionsFromReview:
    """Two HIGH defects quant-verifier found in the first cut of this module. Both were
    invisible to the suite as written, so each gets a test that fails on the old code."""

    @pytest.mark.parametrize(
        ("diversity", "sl_atr"),
        [("off", "shadow"), ("shadow", "off"), ("off", "active"), ("shadow", "shadow")],
    )
    def test_entry_quality_stamps_whenever_either_half_is_on(
        self, diversity: str, sl_atr: str
    ) -> None:
        """`"off" or "shadow"` returns `"off"` — a non-empty string is TRUTHY. That tagged
        the judgement off, `check` dropped it, and the `entry_quality` stamp silently
        stopped being written for `diversity=off, sl_atr=shadow`. That stamp is the whole
        forward-evidence mechanism for the sl_atr sidecar: the gate ran and recorded
        nothing. Canary — the old expression returns "off" for the first case."""
        out = restrictions.check(
            _ctx(),
            _cfg(**{restrictions.GATE_DIVERSITY: diversity, restrictions.GATE_SL_ATR: sl_atr}),
            enforced_by=EnforcedBy.OVERLAY,
        )
        assert "entry_quality" in out.stamps(), f"no stamp for {diversity=} {sl_atr=}"

    def test_effective_mode_prefers_active_then_shadow_then_off(self) -> None:
        assert restrictions._effective_mode("off", "shadow") == "shadow"
        assert restrictions._effective_mode("shadow", "active") == "active"
        assert restrictions._effective_mode("off", "off") == "off"

    def test_through_stop_is_judged_on_a_fill_when_there_is_no_live_price(self) -> None:
        """`requires` is an AND, so declaring `{market_price}` skipped the rule entirely
        whenever only a modelled fill was supplied — and a void setup reported CLEAR.
        `requires_any` fixes it. Canary: on the old code this returned blocked=False."""
        out = restrictions.check(
            _ctx(
                market_price=None,
                fill_price=Decimal("94"),  # through the 95 stop
                available=frozenset({restrictions.CTX_FILL_PRICE}),
            ),
            _cfg(),
        )
        assert out.blocked is True
        assert out.gate == restrictions.GATE_THROUGH_STOP

    def test_through_stop_still_works_from_the_live_price_alone(self) -> None:
        out = restrictions.check(_ctx(market_price=Decimal("94")), _cfg())
        assert out.blocked is True
        assert out.gate == restrictions.GATE_THROUGH_STOP

    def test_through_stop_is_unassessable_with_neither_price(self) -> None:
        out = restrictions.check(_ctx(market_price=None, available=frozenset()), _cfg())
        assert restrictions.GATE_THROUGH_STOP in out.unassessed
        assert out.blocked is False

    def test_allow_offmarket_has_no_permissive_default(self) -> None:
        """A safety field that defaults permissive is one refactor away from being wrong:
        `allow_offmarket_entry` defaults FALSE on the user."""
        with pytest.raises(TypeError):
            restrictions.RestrictionContext(  # type: ignore[call-arg]
                signal=_signal(), side="LONG", as_of=datetime.now(tz=UTC)
            )


class TestTheDisplayPathCannotReachFabricatedThresholds:
    """`eligibility.preview` supplies stand-in thresholds for the gates it cannot judge,
    set to BLOCK everything so a mistake is loud.

    ⚠ The first version of this class could not fail. One test asserted
    `not r.requires <= LIST_AVAILABLE` *guarded by* `if r.gate in UNCOVERED_GATES` — but
    `UNCOVERED_GATES` is DEFINED by that predicate, so the assertion was a tautology for
    every possible value of `LIST_AVAILABLE` (bug-hunter proved it across all 128 subsets).
    The other ran `preview` with every mode `off`, so every judge short-circuited before a
    threshold was read. Both stayed green under exactly the change they claimed to guard.
    These assert the ACTUAL partition instead, so widening `LIST_AVAILABLE` fails them."""

    def test_the_reachable_partition_is_pinned_by_name(self) -> None:
        """Pin WHICH rules a list row can satisfy. Widening `LIST_AVAILABLE` — the change
        the stand-in comment warns about — changes this set and fails here."""
        reachable = {
            r.gate
            for r in restrictions.REGISTRY
            if r.enforced_by is EnforcedBy.OVERLAY and r.requires <= eligibility.LIST_AVAILABLE
        }
        assert reachable == {
            restrictions.GATE_REGIME,
            restrictions.GATE_ENTRY_QUALITY,
            restrictions.GATE_RR,
            restrictions.GATE_CHASE,
        }

    def test_stand_ins_are_unread_with_every_gate_active_not_merely_off(self) -> None:
        """All-off proves nothing — every judge short-circuits before reading a threshold.
        Turn everything ON: the uncovered gates must land in `unassessed`, and whatever
        blocks must never be one of them (which would mean a stand-in was read)."""
        v = eligibility.preview(
            _signal(),
            modes=dict.fromkeys(restrictions.MODED_GATES, "active"),
            market_price=Decimal("100"),
            atr=Decimal("2"),
            min_scoring_factors=2,
            max_dominant_share=Decimal("0.9"),
            min_sl_atr_mult=Decimal("0.01"),
        )
        assert set(v.unassessed) >= set(eligibility.UNCOVERED_GATES), v.unassessed
        assert v.gate not in eligibility.UNCOVERED_GATES, (
            f"{v.gate} was judged on the display path against a stand-in threshold"
        )

    def test_what_preview_supplies_never_exceeds_what_list_available_claims(self) -> None:
        """The derivation of COVERED/UNCOVERED assumes these are the same set. If `preview`
        could declare a key `LIST_AVAILABLE` omits, a rule needing it would be reported as
        uncovered while actually being judged against a stand-in."""
        v = eligibility.preview(
            _signal(),
            modes=dict.fromkeys(restrictions.MODED_GATES, "off"),
            market_price=Decimal("100"),
            fill_price=Decimal("100"),
            atr=Decimal("2"),
            min_scoring_factors=2,
            max_dominant_share=Decimal("0.9"),
            min_sl_atr_mult=Decimal("1.0"),
        )
        assert v.blocked is False
        # All three of the keys preview can declare must be inside LIST_AVAILABLE.
        for key in (
            restrictions.CTX_MARKET_PRICE,
            restrictions.CTX_FILL_PRICE,
            restrictions.CTX_ATR,
        ):
            assert key in eligibility.LIST_AVAILABLE, key


class TestEnforcementSite:
    def test_the_order_path_does_not_run_the_brokers_own_rejections(self) -> None:
        """`place_paper_order` enforces off-market and through-stop itself; running them
        in the overlay chain too would reject twice with two different HTTP codes."""
        out = restrictions.check(
            _ctx(market_price=None, available=frozenset(), allow_offmarket=False),
            _cfg(),
            enforced_by=EnforcedBy.OVERLAY,
        )
        assert out.blocked is False

    def test_the_display_path_does_run_them(self) -> None:
        out = restrictions.check(
            _ctx(market_price=None, available=frozenset(), allow_offmarket=False), _cfg()
        )
        assert out.blocked is True
        assert out.gate == restrictions.GATE_OFFMARKET


class TestAssessabilityIsDerivedNotRemembered:
    """The structural claim: `requires` is data the composer reads, so a gate that cannot
    be judged is reported automatically — no one has to remember to extend a list."""

    def test_an_active_gate_missing_its_context_is_named_not_passed(self) -> None:
        out = restrictions.check(
            _ctx(), _cfg(**{restrictions.GATE_LIQUIDITY: "active"})
        )
        assert restrictions.GATE_LIQUIDITY in out.unassessed
        assert out.blocked is False  # unknown, never blocked on uncertainty

    def test_a_shadow_gate_missing_its_context_is_not_named(self) -> None:
        """Shadow suppresses nothing, so naming it would cry wolf on every row."""
        out = restrictions.check(_ctx(), _cfg(**{restrictions.GATE_LIQUIDITY: "shadow"}))
        assert out.unassessed == ()

    def test_sl_atr_active_without_an_atr_is_named_even_though_its_gate_ran(self) -> None:
        """sl_atr hides inside entry-quality, whose own `requires` is empty because the
        DIVERSITY half needs nothing. Without this it would read as clear."""
        out = restrictions.check(_ctx(atr=None), _cfg(**{restrictions.GATE_SL_ATR: "active"}))
        assert f"{restrictions.GATE_ENTRY_QUALITY}.sl_atr" in out.unassessed

    def test_a_new_restriction_is_covered_with_no_other_change(self) -> None:
        """The whole point of A38. A rule added to the registry is judged, and reported
        when it cannot be judged, without touching the composer or either path."""
        marker = "future_gate"

        def judge(
            ctx: restrictions.RestrictionContext, cfg: restrictions.RestrictionConfig
        ) -> restrictions.Judgement:  # pragma: no cover — must never be reached
            raise AssertionError("judged despite unavailable context")

        newcomer = restrictions.Restriction(
            gate=marker, requires=frozenset({"some_context_nobody_loads"}),
            enforced_by=EnforcedBy.OVERLAY, judge=judge,
        )
        base = _cfg()
        cfg = replace(base, modes={**base.modes, marker: "active"})
        out = restrictions.check(
            _ctx(), cfg, restrictions=[*restrictions.REGISTRY, newcomer]
        )
        assert marker in out.unassessed
        assert out.blocked is False


class TestCompositionInvariants:
    def test_check_stops_at_the_first_block(self) -> None:
        """The old preview `return`ed at the first block and was structurally immune to a
        later rule raising. Continuing meant an exception from a rule AFTER the blocker
        escaped `preview`, and both display callers swallow that into a row identical to
        "verified clear" — a blocked signal rendering a live Buy button (bug-hunter)."""
        out = restrictions.check(
            _ctx(market_price=None, available=frozenset(), allow_offmarket=False),
            _cfg(**{restrictions.GATE_RR: "shadow", restrictions.GATE_CHASE: "shadow"}),
        )
        assert out.blocked is True
        assert out.gate == restrictions.GATE_OFFMARKET
        # offmarket is first in the registry, so nothing after it should have been judged.
        assert [j.gate for j in out.judgements] == [restrictions.GATE_OFFMARKET]

    def test_every_context_a_rule_needs_has_an_order_path_loader(self) -> None:
        """The order path used to key its loads on gate MODES, not on `requires` — so the
        hand-maintained sequence A38 set out to delete survived one level down. A rule
        needing an already-existing key was then silently skipped whenever the unrelated
        gate that owned that key was off. `trading.py` now asserts this at import; this
        test states the same contract where a reader will find it."""
        from app.signals.restriction_context import (  # noqa: PLC0415 — test-only
            _LOADABLE_CONTEXT,
        )

        needed: set[str] = set()
        for r in restrictions.REGISTRY:
            if r.enforced_by is not EnforcedBy.OVERLAY:
                continue
            needed |= r.requires | r.requires_any
            for _sub, _label, sub_needs in r.sub_requires:
                needed |= sub_needs
        assert needed <= _LOADABLE_CONTEXT, sorted(needed - _LOADABLE_CONTEXT)

    def test_a_sub_gate_context_gap_is_declared_not_hardcoded(self) -> None:
        """sl_atr's ATR need used to be a hardcoded branch in `_unassessed_gates` — the one
        gate whose assessability was not derived from data was the one that needed it most."""
        eq = [r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_ENTRY_QUALITY][0]
        assert eq.sub_requires == (
            (restrictions.GATE_SL_ATR, "entry_quality.sl_atr", frozenset({restrictions.CTX_ATR})),
        )


class TestPointInTime:
    def test_the_context_carries_an_explicit_as_of(self) -> None:
        """A backtest must be able to ask 'was this restricted ON THAT DATE' — the
        question the previous arrangement could not pose at all."""
        when = datetime(2024, 3, 1, tzinfo=UTC)
        ctx = _ctx(as_of=when)
        assert ctx.as_of == when
        # as_of is mandatory: there is no way to build a context without anchoring it.
        with pytest.raises(TypeError):
            restrictions.RestrictionContext(signal=_signal(), side="LONG")  # type: ignore[call-arg]


class TestEligibilityDerivesItsCoverageFromTheRegistry:
    def test_covered_and_uncovered_partition_the_moded_gates(self) -> None:
        assert set(eligibility.COVERED_GATES) | set(eligibility.UNCOVERED_GATES) == set(
            restrictions.MODED_GATES
        )
        assert not set(eligibility.COVERED_GATES) & set(eligibility.UNCOVERED_GATES)

    def test_uncovered_is_exactly_what_needs_context_a_list_cannot_supply(self) -> None:
        assert set(eligibility.UNCOVERED_GATES) == {
            restrictions.GATE_CIRCUIT,
            restrictions.GATE_SECTOR_RS,
            restrictions.GATE_MARKET_REGIME,
            restrictions.GATE_LIQUIDITY,
        }
