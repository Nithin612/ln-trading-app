"""Trail stop-loss state machine — Phase 8.

States (trail_state on Position):
  none        Original SL from signal; no adjustment yet.
  breakeven   Price moved 1R in direction → SL moved to entry (no loss).
  trailing_1  Price moved 1.5R → SL to entry + 0.5R (locked in small profit).
  trailing_2  Price moved 2R+ → SL trails at entry + 1R (half profit locked).

R = abs(entry - original_sl).

The state machine is monotonic: states only advance forward, never back.
"""

from decimal import Decimal
from typing import NamedTuple

_STATES = ["none", "breakeven", "trailing_1", "trailing_2"]


class TrailResult(NamedTuple):
    new_sl: Decimal
    new_state: str
    advanced: bool   # True if state moved forward


def advance_trail(  # noqa: C901
    *,
    side: str,
    entry: Decimal,
    original_sl: Decimal,
    current_sl: Decimal,
    current_price: Decimal,
    current_state: str,
) -> TrailResult:
    """Compute new SL and trail state given the current market price.

    Returns the same (current_sl, current_state, False) if no advancement.
    """
    if current_state not in _STATES:
        current_state = "none"

    risk = abs(entry - original_sl)
    if risk == 0:
        return TrailResult(current_sl, current_state, False)

    is_long = side.upper() == "LONG"
    price_move = (current_price - entry) if is_long else (entry - current_price)

    # Determine best achievable state from current price
    if price_move >= risk * Decimal("2"):
        target_state = "trailing_2"
    elif price_move >= risk * Decimal("1.5"):
        target_state = "trailing_1"
    elif price_move >= risk * Decimal("1"):
        target_state = "breakeven"
    else:
        target_state = "none"

    current_idx = _STATES.index(current_state)
    target_idx = _STATES.index(target_state)

    if target_idx <= current_idx:
        # No advancement — return unchanged
        return TrailResult(current_sl, current_state, False)

    # Advance to target state and compute the new SL
    new_state = target_state
    if new_state == "breakeven":
        new_sl = entry
    elif new_state == "trailing_1":
        if is_long:
            new_sl = entry + risk * Decimal("0.5")
        else:
            new_sl = entry - risk * Decimal("0.5")
    else:  # trailing_2
        if is_long:
            # Trail at current_price - 1R so it tracks the price
            new_sl = current_price - risk
        else:
            new_sl = current_price + risk

    # Never move SL against the position (safety guard)
    if is_long and new_sl < current_sl:
        new_sl = current_sl
    elif not is_long and new_sl > current_sl:
        new_sl = current_sl

    return TrailResult(new_sl, new_state, True)


def is_sl_hit(
    *,
    side: str,
    current_price: Decimal,
    current_sl: Decimal,
) -> bool:
    if side.upper() == "LONG":
        return current_price <= current_sl
    return current_price >= current_sl


def is_tp_hit(
    *,
    side: str,
    current_price: Decimal,
    current_tp: Decimal,
) -> bool:
    if side.upper() == "LONG":
        return current_price >= current_tp
    return current_price <= current_tp


def compute_pnl(
    *,
    side: str,
    entry: Decimal,
    exit_price: Decimal,
    quantity: int,
) -> Decimal:
    """Compute realized P&L in INR (no brokerage — paper trading)."""
    if side.upper() == "LONG":
        return (exit_price - entry) * Decimal(str(quantity))
    return (entry - exit_price) * Decimal(str(quantity))
