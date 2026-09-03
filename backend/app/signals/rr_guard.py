"""Reward:risk floor overlay — the one gate that enforces an IDENTITY, not a hypothesis.

A signal whose planned TARGET sits closer than its STOP cannot be positive-expectancy
unless the win rate exceeds 50%, which no trend-following system sustains. That is
arithmetic, not a claim about the market, so this overlay ships ACTIVE with no
forward-evidence bar — there is no hypothesis to falsify. (Contrast every other overlay
here, each of which asserts something empirical about the tape and therefore waits on its
pre-registered count. Raising this floor ABOVE 1.0 *would* be empirical — 1.67 is the
break-even payoff at our observed 37.5% win rate, i.e. a number fitted to 99 trades — and
must go through the deflated-Sharpe / multiple-testing bar first.)

**Why the defect exists.** `analysis/risk.py::compute_levels` (FROZEN) pairs a STRUCTURAL
stop — the swing pivot for swing, EMA20 for positional — with an ABSOLUTE-% target (swing
= entry ±6%, positional ±15%). The ratio is therefore an accident of where the pivot
happened to sit: a 7% stop against a 6% target gives R:R 0.86, and **94 of 295 swing
signals** landed under 1.0 in the 2026-09-02 audit. Intraday and scalp are ratio-based
(1:2 and 1:1.5) and do not have this problem. This overlay is the tourniquet; making
swing/positional ratio-based is a §6 spec change plus an §8 regression, deliberately out
of scope here.

**It is complementary to `sl_atr`, not redundant** — the two are structurally disjoint. A
too-tight stop mechanically produces a LARGE ratio (a fixed 6% target ÷ a 0.4% stop = 15:1),
while R:R < 1 only arises when the stop is WIDE. Measured on the live inventory
(2026-09-02): 11 signals under R:R 1.0, 21 with stops under 2% of price, and **zero in
both**.

Same shape as `chase_guard` / `regime_guard` / `liquidity_guard`: **pure** (no I/O),
**moded** (off / shadow / active), **fail-open**. Frozen confluence engine untouched — a
downstream eligibility gate, never a confluence factor.

**Fail-open:** a zero-risk signal (entry == SL) is not assessable, so it is eligible here
— `risk_guards.safe_levels` and the broker's own sizing reject that case on their own
terms, and a gate that suppresses must never suppress on uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_Q = Decimal("0.01")


@dataclass(frozen=True)
class RrVerdict:
    """The overlay's read on one signal. Stamped on the order's
    ``broker_payload["rr_gate"]`` so a decision stays reconstructable."""

    blocked: bool
    assessable: bool  # False ⇒ zero-risk signal; blocked is False (fail-open)
    rr_min: Decimal
    rr: Decimal | None = None
    reason: str | None = None

    def as_payload(self) -> dict[str, object]:
        return {
            "blocked": self.blocked,
            "assessable": self.assessable,
            "rr_min": str(self.rr_min),
            "rr": str(self.rr.quantize(_Q)) if self.rr is not None else None,
            "reason": self.reason,
        }


def evaluate(
    *,
    entry: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    rr_min: Decimal = Decimal("1.0"),
) -> RrVerdict:
    """Judge a signal's PLANNED reward:risk = |TP − entry| / |entry − SL|.

    Planned, not realised: this is a property of the signal as committed, so it is
    decidable from the signal row alone with no live data — which is why the display path
    can judge it too (`app/signals/eligibility.py`)."""
    risk = abs(entry - stop_loss)
    if risk <= 0:
        return RrVerdict(
            blocked=False,
            assessable=False,
            rr_min=rr_min,
            reason="zero-risk signal (entry == SL) — reward:risk not assessable",
        )
    rr = abs(take_profit - entry) / risk
    blocked = rr < rr_min
    reason = None
    if blocked:
        reason = (
            f"planned reward:risk is {rr.quantize(_Q)} (floor {rr_min}) — the target "
            f"(₹{take_profit}) is closer than the stop (₹{stop_loss}), so the trade needs a "
            "win rate above 50% just to break even"
        )
    return RrVerdict(
        blocked=blocked, assessable=True, rr_min=rr_min, rr=rr, reason=reason
    )


def order_block_reason(verdict: RrVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order, or None to allow it. Only ACTIVE blocks; in
    off/shadow this is a no-op."""
    if mode != "active" or not verdict.blocked:
        return None
    return f"Signal fails the reward:risk floor: {verdict.reason}"
