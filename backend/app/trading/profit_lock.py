"""Layered Ratchet Stop — the Dynamic Profit Lock mechanism (design 2026-07-29).

Pure, deterministic stop-computation. No I/O, no clocks — prices/ATR enter as
parameters. A shadow comparator replays it over history (evidence), and it is
ALSO wired into the live PAPER exit path per-user: `position_monitor` selects
this ratchet when `User.profit_lock_enabled` is set, otherwise the fixed
`trail_sl` ladder governs. Still shadow-first — it only moves paper stops and
gates nothing real until the Phase-7 live cutover; the per-class params below
are calibration starting points, not final.

The effective stop is the TIGHTEST of several candidate floors, ratcheted one
way only (up for a long, down for a short):

  - initial risk SL           the disaster floor, never removed
  - ATR chandelier            peak ∓ k·ATR  — gives a trend room to breathe
  - profit-lock cap           don't give back more than g% of peak profit

The ATR chandelier and profit-lock cap arm only after the trade has moved
`arm_r` R in favour (before that the position keeps its full initial risk — no
premature tightening). The two layers hand off automatically: on a smooth
trend the ATR chandelier binds (room); on a fast spike where ATR is
deceptively small, the giveback cap binds (protection). There is no profit
ceiling — nothing here exits on reaching a target.

R (risk per share) = |entry − initial SL|. Money is Decimal throughout.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_ONE = Decimal(1)


@dataclass(frozen=True)
class RatchetParams:
    """Per-classification tuning. Giveback tapers linearly from `giveback_early`
    (at `arm_r`) to `giveback_late` (at `late_r` and beyond) — wide early so a
    pullback doesn't exit a young trend, tighter once the trade is deep in
    profit. These are STARTING points for backtest, not final values."""

    arm_r: Decimal        # arm the lock once favourable move ≥ arm_r · R
    atr_k: Decimal        # ATR chandelier multiple (bigger = more room)
    giveback_early: Decimal   # fraction of peak profit allowed back at arm
    giveback_late: Decimal    # fraction allowed back at/after late_r
    late_r: Decimal = Decimal("3")


# Keyed by signal.classification. Intraday tight (fast mean-reversion after a
# spike), swing/positional wider (multi-day pullbacks are normal).
CLASS_PARAMS: dict[str, RatchetParams] = {
    "scalp": RatchetParams(Decimal("0.8"), Decimal("1.0"), Decimal("0.25"), Decimal("0.15")),
    "intraday": RatchetParams(Decimal("1.0"), Decimal("1.5"), Decimal("0.35"), Decimal("0.20")),
    "swing": RatchetParams(Decimal("1.0"), Decimal("2.5"), Decimal("0.55"), Decimal("0.40")),
    "positional": RatchetParams(Decimal("1.0"), Decimal("3.5"), Decimal("0.60"), Decimal("0.45")),
    "investment": RatchetParams(Decimal("1.0"), Decimal("4.0"), Decimal("0.60"), Decimal("0.45")),
}
DEFAULT_PARAMS = CLASS_PARAMS["swing"]


def params_for(classification: str | None) -> RatchetParams:
    """Resolve tuning for a classification, falling back to the swing preset."""
    if classification is None:
        return DEFAULT_PARAMS
    return CLASS_PARAMS.get(classification, DEFAULT_PARAMS)


def giveback_fraction(params: RatchetParams, r_mult: Decimal) -> Decimal:
    """Allowed giveback fraction of peak profit at a given R-multiple of the
    favourable move. Constant `giveback_early` up to `arm_r`, linearly tapering
    to `giveback_late` by `late_r`, then constant."""
    if r_mult <= params.arm_r:
        return params.giveback_early
    if r_mult >= params.late_r:
        return params.giveback_late
    span = params.late_r - params.arm_r
    if span <= 0:
        return params.giveback_late
    frac = (r_mult - params.arm_r) / span
    return params.giveback_early + (params.giveback_late - params.giveback_early) * frac


def layered_ratchet_stop(
    *,
    side: str,
    entry: Decimal,
    original_sl: Decimal,
    peak_price: Decimal,
    atr: Decimal | None,
    params: RatchetParams,
    current_stop: Decimal,
) -> Decimal:
    """Compute the new effective stop given the best price reached so far.

    `peak_price` is the most favourable price seen (highest for a long, lowest
    for a short). `current_stop` is the stop currently in force; the return
    value never ratchets against the position. `atr` may be None (chandelier
    layer simply doesn't contribute)."""
    is_long = side.upper() == "LONG"
    risk = (entry - original_sl) if is_long else (original_sl - entry)

    if is_long:
        candidates = [original_sl]
        move = peak_price - entry
        if risk > 0 and move >= params.arm_r * risk:
            if atr is not None and atr > 0:
                candidates.append(peak_price - atr * params.atr_k)
            g = giveback_fraction(params, move / risk)
            candidates.append(entry + move * (_ONE - g))
        return max(current_stop, max(candidates))

    candidates = [original_sl]
    move = entry - peak_price
    if risk > 0 and move >= params.arm_r * risk:
        if atr is not None and atr > 0:
            candidates.append(peak_price + atr * params.atr_k)
        g = giveback_fraction(params, move / risk)
        candidates.append(entry - move * (_ONE - g))
    return min(current_stop, min(candidates))


# --------------------------------------------------------------------------- #
# Absolute-rupee profit ladder — the trader's "seal ₹X" model (live paper path) #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AbsoluteLadderParams:
    """Rupee-denominated profit ladder. Coherent across trades once every trade
    is sized to the same per-trade risk budget (paper_broker.size_for_fill), so
    a ₹ profit maps to a consistent R. Amounts are position-level rupees."""

    breakeven_inr: Decimal      # peak profit ≥ this → lock breakeven (no loss)
    trail_start_inr: Decimal    # peak profit ≥ this → start sealing profit
    giveback_inr: Decimal       # seal (peak_profit − giveback): a fixed-₹ trailing giveback
    atr_k: Decimal              # giveback is at least atr_k·ATR in price (elasticity/room)


def absolute_ladder_stop(
    *,
    side: str,
    entry: Decimal,
    original_sl: Decimal,
    peak_price: Decimal,
    quantity: int,
    atr: Decimal | None,
    params: AbsoluteLadderParams,
    current_stop: Decimal,
) -> Decimal:
    """New effective stop under the rupee profit ladder, ratcheted one way only.

    Tightest of these floors wins (max for a long, min for a short); never moves
    against the position:
      - original risk SL   the disaster floor, never removed
      - breakeven (entry)  armed once peak profit ≥ breakeven_inr (kills the
                           "went +₹2k then back to a loss" case)
      - sealed floor       armed once peak profit ≥ trail_start_inr: the price
                           giving (peak_profit − giveback), i.e. peak ∓ giveback_price
                           with giveback_price = max(giveback_inr/qty, atr_k·ATR) —
                           a quiet name seals tight to the ₹ giveback, a volatile
                           one keeps more room so a normal pullback doesn't exit it.

    `peak_price` is the best price reached; `atr` may be None (no ATR room)."""
    is_long = side.upper() == "LONG"
    qty = Decimal(quantity)
    if qty <= 0:
        return current_stop
    peak_profit = (peak_price - entry) * qty if is_long else (entry - peak_price) * qty

    candidates = [original_sl]
    if peak_profit >= params.breakeven_inr:
        candidates.append(entry)
    if peak_profit >= params.trail_start_inr:
        giveback_price = params.giveback_inr / qty
        if atr is not None and atr > 0:
            giveback_price = max(giveback_price, params.atr_k * atr)
        seal = (peak_price - giveback_price) if is_long else (peak_price + giveback_price)
        candidates.append(seal)

    if is_long:
        return max(current_stop, max(candidates))
    return min(current_stop, min(candidates))


def ladder_params_from_settings() -> AbsoluteLadderParams:
    """Resolve the ladder tuning from config (deferred import keeps the stop
    functions above pure and dependency-free)."""
    from app.core.config import settings

    return AbsoluteLadderParams(
        breakeven_inr=Decimal(str(settings.profit_lock_breakeven_inr)),
        trail_start_inr=Decimal(str(settings.profit_lock_trail_start_inr)),
        giveback_inr=Decimal(str(settings.profit_lock_giveback_inr)),
        atr_k=Decimal(str(settings.profit_lock_atr_k)),
    )
