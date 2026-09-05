"""Exhaustive-enum mapping tests — T7.

We have already been burned by exactly this failure: *"v1's `unassessed` tripwire was
IMAGINARY — 3 of 8 modes passed"*. An enumeration that was not exhaustively handled, with
no test that could notice.

The rule these enforce: **every variant of an enumeration is handled, the handling is
deterministically ordered, and adding a variant without handling it fails the suite.** Each
test below derives its expectations from the declaration rather than restating it, so it
breaks when the vocabulary grows — which is the only way this class of test earns its keep.
"""

from typing import Literal, get_args, get_origin

from app.core.config import Settings
from app.signals import restrictions as rx


def _gate_mode_fields() -> dict[str, tuple[str, ...]]:
    """Every settings field whose type is a gate-mode Literal, and its allowed values."""
    out: dict[str, tuple[str, ...]] = {}
    for name, field in Settings.model_fields.items():
        ann = field.annotation
        if get_origin(ann) is Literal and name.endswith("_mode"):
            out[name] = tuple(str(a) for a in get_args(ann))
    return out


class TestGateModeVocabulary:
    def test_every_moded_setting_uses_the_declared_vocabulary(self) -> None:
        """⭐ The T7 tripwire. Eight `*_gate_mode` settings each declare the Literal
        independently; nothing ties them to `_effective_mode`'s handling. Add a fourth mode
        to one knob and it falls through as "off" — silently, on the order path."""
        fields = _gate_mode_fields()
        assert fields, "no gate-mode settings found — has the naming convention changed?"
        for name, values in fields.items():
            assert set(values) == set(rx.GATE_MODES), (
                f"{name} declares {values!r} but the vocabulary is {rx.GATE_MODES!r} — "
                "extend GATE_MODES and _effective_mode together, or the new mode is "
                "silently treated as 'off'"
            )

    def test_effective_mode_handles_every_single_variant(self) -> None:
        for mode in rx.GATE_MODES:
            assert rx._effective_mode(mode) == mode

    def test_effective_mode_is_exhaustive_and_ordered_over_every_pair(self) -> None:
        """The precedence lattice, written out rather than derived from the code under
        test. This is where the `"off"` truthiness bug lived: `div or sl` returns "off"
        whenever diversity is off, because "off" is a non-empty string."""
        strength = {"off": 0, "shadow": 1, "active": 2}
        assert set(strength) == set(rx.GATE_MODES), "extend the lattice with the vocabulary"
        for a in rx.GATE_MODES:
            for b in rx.GATE_MODES:
                expected = a if strength[a] >= strength[b] else b
                assert rx._effective_mode(a, b) == expected, f"({a}, {b})"

    def test_the_truthiness_trap_specifically(self) -> None:
        """Regression: `"off" or "shadow"` evaluates to `"off"`. The strongest mode must
        win regardless of argument order."""
        assert rx._effective_mode("off", "shadow") == "shadow"
        assert rx._effective_mode("shadow", "off") == "shadow"
        assert rx._effective_mode("off", "active") == "active"

    def test_an_unknown_mode_degrades_to_off_rather_than_crashing(self) -> None:
        """Pinning current behaviour, not endorsing it: an unrecognised mode is treated as
        off. That is the safe direction on an order path, and it is exactly why the
        vocabulary test above matters — nothing else would notice."""
        assert rx._effective_mode("enabled") == "off"


class TestEnforcedByIsExhaustive:
    def test_every_variant_appears_in_the_registry(self) -> None:
        """A new `EnforcedBy` member with no rule using it means a path nobody walks."""
        used = {r.enforced_by for r in rx.REGISTRY}
        assert used == set(rx.EnforcedBy), (
            f"unused EnforcedBy variants: {set(rx.EnforcedBy) - used}"
        )

    def test_both_paths_partition_the_registry(self) -> None:
        """OVERLAY is the order path, BROKER the preview's own pre-fill rejections. Every
        rule belongs to exactly one, or a gate is either double-rejected or unenforced."""
        overlay = [r for r in rx.REGISTRY if r.enforced_by is rx.EnforcedBy.OVERLAY]
        broker = [r for r in rx.REGISTRY if r.enforced_by is rx.EnforcedBy.BROKER]
        assert len(overlay) + len(broker) == len(rx.REGISTRY)
        assert overlay and broker


class TestRegistryIsDeterministic:
    def test_gate_names_are_unique(self) -> None:
        names = [r.gate for r in rx.REGISTRY]
        assert len(names) == len(set(names)), "a duplicated gate name makes order ambiguous"

    def test_order_is_stable_across_reads(self) -> None:
        """Both paths walk this tuple, so the reason a user sees first must not depend on
        iteration luck."""
        assert [r.gate for r in rx.REGISTRY] == [r.gate for r in rx.REGISTRY]
        assert isinstance(rx.REGISTRY, tuple), "a list could be mutated at import time"

    def test_the_order_is_pinned(self) -> None:
        """⭐ The order IS the contract — both paths walk this tuple, so it decides which
        reason a user sees first, and a contract test asserts the list equals the order
        path's 409 detail. Pin it as a golden list so any reordering is a deliberate,
        reviewed change rather than a side effect.

        Note this deliberately does NOT assert "broker rules come last", which the
        registry's own comment implies but the declaration contradicts: `offmarket` is a
        BROKER rule declared FIRST, because the absence of a price is its trigger. A test
        written to that comment passes vacuously; this one cannot.
        """
        assert [r.gate for r in rx.REGISTRY] == [
            "offmarket",
            "regime_gate",
            "circuit_gate",
            "entry_quality",
            "rr_gate",
            "sector_rs_gate",
            "market_regime_gate",
            "liquidity_gate",
            "chase_gate",
            "through_stop",
        ]
