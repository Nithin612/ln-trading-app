"""The gate / hypothesis register — H4, and the trials counter it makes possible — U4.

Constraint #8 makes Claude the owner of the review calendar and requires raising each item
unprompted. That calendar was prose in `docs/PHASES.md`, which meant `N` in `E[max SR]` was
a hand-picked 20 — the deflation is the whole point of the bar and its most important input
was never measured.

These tests keep the register honest against the code it describes, so it cannot quietly
drift out of date the way the status block did on 2026-08-08.
"""

import pytest
from app.core.config import Settings
from app.services import gate_register as gr
from app.services.deflated_sharpe import DEFAULT_TRIALS


class TestRegisterIntegrity:
    def test_keys_are_unique(self) -> None:
        keys = [h.key for h in gr.REGISTER]
        assert len(keys) == len(set(keys))

    def test_every_entry_states_a_verdict_and_a_bar(self) -> None:
        """An entry with no verdict is a hypothesis nobody closed, which is the state this
        register exists to make impossible to lose track of."""
        for h in gr.REGISTER:
            assert h.verdict.strip(), h.key
            assert h.bar.strip(), h.key
            assert h.prediction.strip(), h.key

    def test_closed_items_carry_no_review_trigger(self) -> None:
        """A DECIDED_NO item with a live trigger would be re-raised forever — `sl_atr`'s
        20-trade trigger was explicitly WITHDRAWN when the count stopped being the
        constraint."""
        assert gr.by_status(gr.Status.DECIDED_NO)
        for h in gr.by_status(gr.Status.DECIDED_NO):
            if h.key == "profit_lock_breakeven":
                continue  # closed AS SPECIFIED, but an ADR-denominated variant is a new trial
            assert h.review_due is None, f"{h.key} is decided but still asks to be re-checked"

    def test_the_reverted_pair_is_recorded(self) -> None:
        """Both reversals stay visible: a programme that forgets its failures re-runs them,
        and these two are why the whole multiple-testing apparatus exists."""
        reverted = {h.key for h in gr.by_status(gr.Status.REVERTED)}
        assert reverted == {"regime_adx", "rr_min"}


class TestTrialsCounter:
    def test_counts_failures_too(self) -> None:
        """A trial count that drops its failures is the exact selection bias the deflation
        corrects for — a reverted gate consumed a trial precisely BECAUSE we adopted it."""
        for key in ("regime_adx", "rr_min", "entry_sl_atr", "confidence_gate_raise"):
            h = next(x for x in gr.REGISTER if x.key == key)
            assert h.counts_as_trial, f"{key} was searched and must count"

    def test_rules_and_safety_rails_do_not_count(self) -> None:
        """`entry_diversity` implements hard constraint #2 and could not have been rejected
        on returns; the notional cap bounds catastrophe and makes no claim about edge.
        Neither inflates a best-of-N Sharpe."""
        for key in ("entry_diversity", "notional_cap"):
            h = next(x for x in gr.REGISTER if x.key == key)
            assert not h.counts_as_trial, f"{key} is not a searched partition"

    def test_the_count_is_the_number_of_trial_entries(self) -> None:
        assert gr.trials_attempted() == sum(1 for h in gr.REGISTER if h.counts_as_trial)
        assert gr.trials_attempted() > 0

    def test_render_states_the_lower_bound_caveat(self) -> None:
        """⭐ Without it, "observed 15 < assumed 20" reads as "the bar is conservative",
        which does not follow: one entry is one HYPOTHESIS and most were tried at several
        thresholds, each of which is its own trial."""
        out = "\n".join(gr.render_lines(assumed_trials=20))
        assert "LOWER BOUND" in out
        assert "does NOT follow" in out

    def test_render_says_it_changes_nothing(self) -> None:
        out = "\n".join(gr.render_lines(assumed_trials=DEFAULT_TRIALS))
        assert "REPORT, not a change" in out
        assert "DEFAULT_TRIALS" in out

    @pytest.mark.parametrize(
        ("assumed", "expect"), [(1, "too LENIENT"), (10_000, "stricter")]
    )
    def test_render_names_which_way_the_gap_runs(self, assumed: int, expect: str) -> None:
        assert expect in "\n".join(gr.render_lines(assumed_trials=assumed))


class TestRegisterMatchesReality:
    """The register describes the code; a test says so, or it drifts."""

    def test_every_moded_gate_in_settings_appears_in_the_register(self) -> None:
        """A gate can be shipped with a `*_gate_mode` knob and never registered — that is
        precisely how a trial escapes the count."""
        registered = {h.key for h in gr.REGISTER}
        # settings knob -> register key
        expected = {
            "regime_gate_mode": "regime_adx",
            "entry_diversity_gate_mode": "entry_diversity",
            "entry_sl_atr_gate_mode": "entry_sl_atr",
            "circuit_gate_mode": "circuit",
            "sector_rs_gate_mode": "sector_rs",
            "market_regime_gate_mode": "market_regime",
            "liquidity_gate_mode": "liquidity",
            "chase_gate_mode": "chase",
            "rr_gate_mode": "rr_min",
        }
        knobs = {n for n in Settings.model_fields if n.endswith("_gate_mode")}
        assert knobs == set(expected), (
            f"a gate-mode knob was added or removed: {knobs ^ set(expected)} — register it "
            "and map it here, or its trial escapes the count"
        )
        for knob, key in expected.items():
            assert key in registered, f"{knob} has no register entry"

    def test_due_for_review_is_the_open_set(self) -> None:
        due = gr.due_for_review()
        assert all(h.review_due is not None for h in due)
        assert len(due) == sum(1 for h in gr.REGISTER if h.review_due is not None)
