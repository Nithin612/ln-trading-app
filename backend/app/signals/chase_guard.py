"""Anti-chase eligibility overlay — the server-side backstop to the AlertBell guardrail.

A signal is meant to be entered at its ``entry_price``, with SL/TP defining the reward:risk
you were shown. Once the LIVE price runs past entry by more than ``max_chase_r`` × the trade's
risk (``|entry − SL|`` = 1R), that reward:risk is materially gone — you are buying *after* the
move (a BUY filling above entry moves you toward the target AND away from the stop, so risk
grows while reward shrinks; the mirror for a SELL). This overlay reads how far the current
market price sits past entry and blocks the order when it is chasing.

Evidence (chase_r-vs-outcome measurement, 2026-08-21, 39 resolved paper trades): the 37 with
chase_r ≤ 0.33 were **+₹275 avg / 62% win**; the only 2 that filled past 0.33R (incl. SRTL)
were **both losers, avg −₹3,074**. One-directional and mechanically motivated, but n=2 past the
line is thin — hence **shadow-first**; a flip to active needs the forward evidence the sidecar
accrues.

Same shape as ``liquidity_guard`` / ``market_regime`` / ``circuit_guard``: **pure** (no I/O —
the caller supplies the live price), **moded** (off / shadow / active), **fail-open**. Frozen
confluence engine untouched — this is a downstream eligibility gate, not a confluence factor.

**Fail-open:** no live price (``market_price is None``, e.g. off-market) or a zero-risk signal
(``entry == SL``) ⇒ not assessable ⇒ eligible. A *negative* chase (filled better than entry) is
never blocked — only running PAST entry chases.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

_Q = Decimal("0.001")


def _pos_side(side: str) -> str:
    return "LONG" if side.upper() in ("BUY", "LONG") else "SHORT"


@dataclass(frozen=True)
class ChaseVerdict:
    """The overlay's read on one signal at order time — stamped on the order's
    ``broker_payload["chase_gate"]`` so the shadow report can aggregate what it WOULD suppress.
    Distinct from the broker's post-fill ``broker_payload["chase"]`` telemetry (that measures the
    actual fill; this measures the live price BEFORE the fill, the pre-trade eligibility read)."""

    blocked: bool
    assessable: bool  # False ⇒ no live price or zero risk; blocked is False (fail-open)
    side: str  # LONG | SHORT
    max_chase_r: Decimal
    chase_r: Decimal | None = None  # signed R past entry in the trade's direction (>0 = chasing)
    entry: Decimal | None = None
    market_price: Decimal | None = None
    reason: str | None = None

    def as_payload(self) -> dict[str, object]:
        def s(v: Decimal | None, q: Decimal) -> str | None:
            return str(v.quantize(q)) if v is not None else None

        return {
            "blocked": self.blocked,
            "assessable": self.assessable,
            "side": self.side,
            "max_chase_r": str(self.max_chase_r),
            # 4dp so the shadow sidecar's would-block recompute is faithful to the gate's own
            # (full-precision) block decision at the ceiling (quant-verifier INFO #1).
            "chase_r": s(self.chase_r, Decimal("0.0001")),
            "entry": s(self.entry, Decimal("0.0001")),
            "market_price": s(self.market_price, Decimal("0.0001")),
            "reason": self.reason,
        }


def evaluate(
    *,
    entry: Decimal,
    stop_loss: Decimal,
    market_price: Decimal | None,
    side: str,
    max_chase_r: Decimal = Decimal("0.33"),
) -> ChaseVerdict:
    """Judge whether the live price is chasing a signal's entry. Blocks when the price has run
    more than ``max_chase_r`` × risk PAST entry in the trade's direction. Fail-open (un-blocked,
    ``assessable`` False) when there is no live price or the signal has zero risk."""
    pos_side = _pos_side(side)
    base = ChaseVerdict(
        blocked=False,
        assessable=False,
        side=pos_side,
        max_chase_r=max_chase_r,
        entry=entry,
        market_price=market_price,
    )
    if market_price is None:
        return replace(base, reason="no live price — chase not assessable")

    risk = abs(entry - stop_loss)
    if risk <= 0:
        return replace(base, reason="zero-risk signal (entry == SL) — chase not assessable")

    beyond = (market_price - entry) if pos_side == "LONG" else (entry - market_price)
    chase_r = beyond / risk
    blocked = chase_r > max_chase_r
    reason = None
    if blocked:
        reason = (
            f"live price ₹{market_price} is {chase_r.quantize(_Q)}R past the ₹{entry} entry "
            f"(ceiling {max_chase_r}R) — chasing: the reward:risk you were shown is materially gone"
        )
    return ChaseVerdict(
        blocked=blocked,
        assessable=True,
        side=pos_side,
        max_chase_r=max_chase_r,
        chase_r=chase_r,
        entry=entry,
        market_price=market_price,
        reason=reason,
    )


def order_block_reason(verdict: ChaseVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order, or None to allow it. Only ACTIVE blocks; in
    off/shadow this is a no-op."""
    if mode != "active" or not verdict.blocked:
        return None
    return f"Signal fails the anti-chase overlay: {verdict.reason}"
