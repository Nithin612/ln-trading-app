"""Queue item 1 — a delivery (CNC) product cannot carry a short position.

⛔⛔ **The regression for a loss that has already happened.** On 2026-09-18 four SELL
signals were clicked, four short positions opened, and the book closed −₹5,054. The
measurement that followed (M92) attributed only −₹221 of that to execution displacement
and −₹4,501 to the signals being wrong — but the four trades had a defect prior to either
number: **on a cash-delivery account they could not have been placed at all.** Nothing in
the system said so. `restrictions.py` declared fourteen gates and none referenced a
settlement product; `product_for_classification` existed and every call site was a
CHARGING site. The product was resolved to bill the trade and never to refuse it.

⭐ **What these tests are really pinning is the FLEXIBILITY requirement** (user, Q-A:
*"we need to build a flexible system for both"*). The rule is not "no shorts". It asks the
fee model which product settles this classification and refuses the short only on
delivery — so the day intraday capital is funded and MIS classifications become
tradeable, the same rule admits them with no code change. `test_an_intraday_short_is_
permitted_which_is_the_whole_flexibility_requirement` is that half, and it is the test
that must not be deleted when someone decides shorts are simply banned.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.models.signal import Signal
from app.signals import restrictions
from app.signals.restrictions import EnforcedBy
from app.trading.fees import PRODUCTS, product_for_classification

_NOW = datetime.now(tz=UTC)

#: ⚠ Anchored to THIS file, never the CWD — a relative "app" resolves differently
#: under `pytest tests/` and `pytest backend/tests/`, and an rglob over the wrong
#: directory finds nothing and passes vacuously.
_APP = Path(__file__).resolve().parent.parent / "app"

#: ⚠ EVERY moded gate off. A block surviving this config can only have come from an
#: `always_on` rule, which is the safety property under test — not from some other gate
#: happening to reject the same signal for an unrelated reason.
_ALL_OFF = dict.fromkeys(restrictions.MODED_GATES, "off")


def _cfg() -> restrictions.RestrictionConfig:
    return restrictions.RestrictionConfig(
        modes=dict(_ALL_OFF),
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


def _signal(direction: str = "SELL", classification: str = "swing") -> Signal:
    """An UNSAVED signal — the registry is pure, so no DB is needed.

    ⚠ Levels are set consistently for a SHORT (stop above entry, target below). A
    long-shaped SELL would be refused by `through_stop`/`rr` for a different reason, and a
    test that cannot tell the two apart proves nothing about this gate.
    """
    return Signal(
        stock_id=1,
        direction=direction,
        classification=classification,
        timeframe="1d",
        entry_price="100.0000",
        stop_loss="105.0000" if direction == "SELL" else "95.0000",
        take_profit="85.0000" if direction == "SELL" else "115.0000",
        suggested_qty=10,
        confidence_pct=80,
        factor_scores={
            "PRICE_VS_EMA": {"weight": 20, "score": -0.8, "explanation": "below"},
            "MACD_HISTOGRAM": {"weight": 15, "score": -0.6, "explanation": "bear"},
        },
        headline="SETTLEMENT TEST",
        status="active",
        validity_until=_NOW + timedelta(days=5),
        created_at=_NOW,
    )


def _check(direction: str, classification: str, side: str) -> restrictions.Outcome:
    ctx = restrictions.RestrictionContext(
        signal=_signal(direction, classification),
        side=side,
        as_of=_NOW,
        allow_offmarket=True,
        available=frozenset(),
    )
    return restrictions.check(ctx, _cfg(), enforced_by=EnforcedBy.OVERLAY)


# ── The defect itself ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("classification", ["swing", "positional"])
def test_a_delivery_short_is_refused(classification: str) -> None:
    """⛔ The four shorts of 2026-09-18 were `swing`. This is the rule that would have
    refused them, and it is the reason the user sees."""
    out = _check("SELL", classification, "SELL")

    assert out.blocked is True
    assert out.gate == restrictions.GATE_SETTLEMENT
    assert out.reason is not None
    assert "delivery" in out.reason.lower() and "short" in out.reason.lower()


def test_the_live_book_would_have_been_refused() -> None:
    """⭐ The regression stated in the terms of the incident: every one of the four
    positions that lost ₹5,054 was a delivery-classified SELL."""
    for symbol_classification in ("swing", "swing", "swing", "swing"):
        assert _check("SELL", symbol_classification, "SELL").blocked is True


# ── The flexibility half — do not delete this when "banning shorts" ───────────

@pytest.mark.parametrize("classification", ["intraday", "scalp"])
def test_an_intraday_short_is_permitted_which_is_the_whole_flexibility_requirement(
    classification: str,
) -> None:
    """⭐⭐ The user's Q-A answer was BOTH products, not one: *"we need to build a
    flexible system for both"*. An MIS short is squared off the same session and settles
    fine, so this rule must not touch it. If this test is ever changed to expect a block,
    the rule has silently become "no shorts" and the MIS half of the account is dead.

    ⚠ These classifications are not reachable from the order path TODAY (the intraday
    profiles run in shadow and the order path admits `status == 'active'` only) — which
    is precisely why the property needs a test rather than a live observation.
    """
    out = _check("SELL", classification, "SELL")

    assert out.blocked is False, (
        f"{classification} settles as MIS and CAN be shorted — this rule has become a "
        "blanket short ban and broken the flexible-for-both requirement"
    )


def test_every_product_the_fee_model_knows_is_covered() -> None:
    """⭐ The guard against the mapping and the rule drifting apart. The gate does not
    restate which classifications are delivery — it asks `product_for_classification` —
    so the assertion is the IMPLICATION, checked for both products the fee model
    declares. A new product added to `PRODUCTS` fails here until it is judged."""
    assert set(PRODUCTS) == {"delivery", "intraday"}, "PRODUCTS changed — judge the new one"

    for classification in ("swing", "positional", "intraday", "scalp"):
        is_delivery = product_for_classification(classification) == "delivery"
        blocked = _check("SELL", classification, "SELL").blocked
        assert blocked is is_delivery, (
            f"{classification}: fees say {product_for_classification(classification)} "
            f"but the gate {'blocks' if blocked else 'allows'} a short — the restriction "
            "has stopped reading the fee model and is restating the mapping"
        )


# ── Scope: what it must NOT touch ─────────────────────────────────────────────

@pytest.mark.parametrize("classification", ["swing", "positional", "intraday", "scalp"])
def test_a_buy_is_never_touched(classification: str) -> None:
    """A long settles on delivery by definition — that is what delivery IS."""
    assert _check("BUY", classification, "BUY").blocked is False


def test_it_judges_the_order_side_not_the_signal_direction() -> None:
    """⚠ The gate asks what the ORDER does, not what the signal recommends. A BUY order
    placed against a SELL signal opens no short and must not be refused by this rule —
    and a SELL order is a short whatever the signal said."""
    assert _check("SELL", "swing", "BUY").blocked is False
    assert _check("BUY", "swing", "SELL").blocked is True


# ── The safety property ───────────────────────────────────────────────────────

def test_there_is_no_knob_that_re_admits_a_delivery_short() -> None:
    """⭐ `always_on`, asserted the way U11 and V3 assert it. The R:R floor was promoted
    on an identity argument and reverted within a week because its premise was empirical;
    this premise is a settlement fact, and a `settlement_gate_mode = off` would silently
    re-admit a trade the exchange will not settle. Every gate above ran with mode `off`
    in these tests and the block still fired — that IS the property."""
    assert restrictions.GATE_SETTLEMENT not in restrictions.MODED_GATES

    rule = next(r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_SETTLEMENT)
    assert rule.always_on is True
    assert rule.enforced_by is EnforcedBy.OVERLAY, (
        "OVERLAY, not BROKER: this is OUR refusal. BROKER means the paper broker rejects "
        "it downstream, and the order path deliberately skips those to avoid double-"
        "rejecting — so a BROKER settlement rule would never run on the order path."
    )


def test_it_needs_no_context_so_it_can_never_be_unassessed() -> None:
    """⭐ The reason this rule required no new context loader, and the property that
    keeps it off the `unassessed` list: classification and side are already in hand. A
    gate that cannot be judged reports 'unknown', and an unknown here would render an
    enabled Buy button on an unsettleable trade."""
    rule = next(r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_SETTLEMENT)
    assert rule.requires == frozenset()
    assert rule.requires_any == frozenset()

    out = _check("SELL", "swing", "SELL")
    assert restrictions.GATE_SETTLEMENT not in out.unassessed


def test_settlement_outranks_every_setup_gate() -> None:
    """⭐ Ordering is a user-facing contract: 'you cannot settle this' must beat 'this
    setup is poor'. A delivery short is not a worse trade, it is not a trade.

    ⚠ Only the recorded human withdrawal (U11) and universe membership (V3) come first —
    both are also statements about whether the name is tradeable at all.
    """
    ids = [r.gate for r in restrictions.REGISTRY]
    settlement = ids.index(restrictions.GATE_SETTLEMENT)

    assert settlement == 2, f"settlement moved to position {settlement}: {ids}"
    assert ids[:2] == [restrictions.GATE_QUARANTINE, restrictions.GATE_UNIVERSE]
    for later in (
        restrictions.GATE_RR, restrictions.GATE_ENTRY_QUALITY, restrictions.GATE_CHASE,
        restrictions.GATE_CIRCUIT, restrictions.GATE_LIQUIDITY,
    ):
        assert settlement < ids.index(later), f"{later} now reports before settlement"


def test_the_display_path_shows_the_same_refusal_as_the_order_path() -> None:
    """⛔ The 2026-09-02 defect class: 41 of 204 listed signals showed a Buy button that
    could only 409. `eligibility.preview` passes `side=signal.direction`, so a SELL signal
    previews as a SELL — this asserts the two paths agree on the reason VERBATIM, which is
    what makes the 13 live SELL signals render `⊘ blocked` with no frontend change."""
    from app.signals import eligibility

    signal = _signal("SELL", "swing")
    preview = eligibility.preview(
        signal,
        modes=dict(_ALL_OFF),
        allow_offmarket=True,
        min_scoring_factors=2,
        max_dominant_share=Decimal("0.9"),
        min_sl_atr_mult=Decimal("1.0"),
    )

    order = _check("SELL", "swing", "SELL")
    assert preview.blocked is True
    assert preview.gate == order.gate == restrictions.GATE_SETTLEMENT
    assert preview.reason == order.reason, (
        "the list and the order path disagree about why — that is the display/order "
        "divergence this registry exists to make impossible"
    )


# ── The bypass this gate has, found while building it ─────────────────────────

def test_the_only_entry_paths_are_the_two_we_know_about() -> None:
    """⛔⛔ **A LATENT BYPASS, recorded rather than silently fixed.**

    Found while verifying this rule's scope. `place_paper_order` has exactly two callers:

    * `api/v1/trading.place_order` — the Buy button. It runs `risk_engine.evaluate`, which
      walks the A38 registry, and raises before reaching the broker. **The settlement gate
      is enforced here**, which is why the 13 live SELL signals are refused.
    * `broker/paper_adapter.submit` — the Phase-7.2 BrokerAdapter port. It imports neither
      `risk_engine` nor `restrictions` and calls `place_paper_order` **directly**, so it
      would bypass the settlement gate and every other overlay.

    ⚠ **Not a live hole today: nothing constructs the adapter** (7.2 is built-not-wired,
    the same defect class as the ledger the item-2 lint is named after). It becomes one the
    moment 7.3's order FSM wires it — and the bypass would be silent, because the adapter
    returns a REJECTED `Ack` rather than raising, so an un-run gate is indistinguishable
    from a gate that passed.

    ⭐ This test is the tripwire, not the fix. The fix belongs to **Phase 7.1**, whose
    stated job is a single RiskEngine gate that every execution path goes through — doing
    it here would mean designing that seam inside an unrelated commit. If this assertion
    fails because a third caller appeared, that caller must run the registry first.
    """
    callers: set[str] = set()
    for path in sorted(_APP.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name == "place_paper_order":
                    callers.add(str(path.relative_to(_APP.parent)))

    assert callers == {"app/broker/paper_adapter.py", "app/api/v1/trading.py"}, (
        f"the set of entry paths changed: {sorted(callers)}. Every caller of "
        "place_paper_order must run the A38 registry first, or it silently bypasses the "
        "settlement gate and every other overlay."
    )


def test_the_adapter_still_does_not_run_the_registry_so_nobody_assumes_it_does() -> None:
    """⭐ The other half of the tripwire, and it is deliberately asserted in the NEGATIVE.

    A comment saying "the adapter does not gate" rots. This fails the day someone wires
    the registry into `paper_adapter`, which is the moment the note above — and the
    Phase-7.1 task it defers to — must be revisited rather than left claiming a hole that
    has since been closed.
    """
    src = (_APP / "broker" / "paper_adapter.py").read_text()

    assert "risk_engine" not in src and "restrictions" not in src, (
        "paper_adapter now references the risk engine — good, but update the bypass note "
        "in test_the_only_entry_paths_are_the_two_we_know_about, which still documents it "
        "as ungated"
    )
