"""Layered Ratchet Stop — the Dynamic Profit Lock mechanism (design 2026-07-29).

Pure, deterministic stop-computation. No I/O, no clocks — prices/ATR enter as
parameters. This is the piece a shadow comparator replays over history and, if
it proves out, would eventually drive live stops. It is NOT wired into the live
exit path — the current `trail_sl` ladder still governs real positions.

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
