"""Item 24 — the position-count cap's justification, pinned to its source.

⛔ The cap of 3 was documented as though it were a universal rule. It is **conditional on
₹1 lakh and on the current modelled cost stack**, and the docs now say so with numbers
attached. ⚠ **Numbers in a comment rot** (W5: no hardcoded copy of a value that has an owner),
so this ties them to `fees.roundtrip_charges` — change the fee model and these fail, which is
the point.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.config import get_settings
from app.trading.fees import roundtrip_charges

CAPITAL = Decimal("100000")
PRICE = Decimal("500")


def _bps_for(n_positions: int) -> float:
    """Round-trip charges for ₹1L split `n` ways, as bps of the whole book."""
    qty = int((CAPITAL / n_positions) / PRICE)
    total, _ = roundtrip_charges(
        position_side="LONG", entry_price=PRICE, exit_price=PRICE,
        quantity=qty, product="delivery",
    )
    return float(total * n_positions) / float(CAPITAL) * 1e4


def test_friction_rises_monotonically_with_the_position_count() -> None:
    """⭐ And the reason is not risk: the DP charge is FLAT per delivery sell, so splitting
    capital multiplies a fixed cost. Concentration control is the side-effect."""
    ladder = [_bps_for(n) for n in range(1, 9)]
    assert ladder == sorted(ladder), f"friction is not monotonic in count: {ladder}"


def test_the_30bps_crossing_is_between_five_and_six_positions() -> None:
    """The documented claim (M77), re-derived from the fee model rather than remembered."""
    assert _bps_for(5) < 30.0 <= _bps_for(6), (
        f"the 30 bps crossing moved: 5 -> {_bps_for(5):.2f}, 6 -> {_bps_for(6):.2f}. "
        "The comment on `max_concurrent_positions` quotes this and must be updated."
    )


def test_the_default_cap_sits_below_thirty_bps() -> None:
    """What the default of 3 actually buys, stated as a number."""
    cap = get_settings().max_concurrent_positions
    assert cap == 3, "the default moved — re-derive the ladder in the config comment"
    assert _bps_for(cap) < 30.0


def test_the_cap_is_a_flat_fee_effect_not_a_risk_effect() -> None:
    """⭐⭐ The claim that makes item 24 a WORDING fix rather than a number fix.

    If the flat DP charge were removed, the friction ladder would be nearly flat in the
    position count — proving the rail is about paying a fixed fee N times, not about
    concentration. Everything else in the stack is proportional to turnover and so is
    invariant to how the same capital is split.
    """
    from app.trading.fees import ZERODHA_EQUITY

    assert ZERODHA_EQUITY.dp_charge_per_sell > 0, "the flat charge is the mechanism"

    # Strip the flat component analytically: it contributes exactly dp * n.
    dp = float(ZERODHA_EQUITY.dp_charge_per_sell)
    without_flat = [
        _bps_for(n) - (dp * n) / float(CAPITAL) * 1e4 for n in range(1, 9)
    ]
    spread = max(without_flat) - min(without_flat)
    assert spread < 1.0, (
        f"without the flat DP charge the ladder still spans {spread:.2f} bps — the "
        "'it is a flat-fee effect' explanation in the config comment is wrong"
    )
