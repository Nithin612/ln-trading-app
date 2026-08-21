"""Liquidity eligibility overlay — MCE slice 5a (the junk filter's core).

The SRTL loss (a BUY on a ₹39 micro-cap × 2666 qty) blew up not because the stock was
*small* but because it was **un-exitable — illiquid**: no buyers to hit the stop. This
overlay blocks an entry into a name whose typical daily traded value is below a floor,
i.e. a position you could not get out of at any sane price. It is the direct, data-we-
already-have protection against that archetype (the market-cap / fundamentals dimension is
the separate XBRL slice 5b).

Liquidity is **side-independent**: an illiquid name traps a long (no buyers for the stop)
AND a short (no sellers to cover), so the gate blocks either side. `side` is carried on the
verdict for the audit trail only.

Same shape as `sector_rs` / `market_regime` / `circuit_guard`: **pure** (no I/O), **moded**
(off / shadow / active), **fail-open**. Frozen confluence engine untouched. The metric is the
**median** daily traded value (₹ = close × volume) over `lookback` completed sessions — median,
not mean, so one block-deal spike can't make a thin name look liquid. Caller supplies the
series aligned to the signal's decision time (no look-ahead), same contract as the siblings.

**Fail-open:** fewer than `lookback` sessions (history too thin to judge) ⇒ eligible.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal

_Q = Decimal("0.01")


def _pos_side(side: str) -> str:
    return "LONG" if side.upper() in ("BUY", "LONG") else "SHORT"


def _median(values: list[Decimal]) -> Decimal:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / Decimal(2)


@dataclass(frozen=True)
class LiquidityVerdict:
    """The overlay's read on one signal — stamped on the order's
    ``broker_payload["liquidity"]`` so the shadow report can aggregate what it WOULD
    suppress. ₹ values are ``Decimal`` (a float round-trip would lose exactness)."""

    blocked: bool
    has_data: bool  # False ⇒ fewer than lookback sessions; blocked is False (fail-open)
    side: str  # LONG | SHORT — audit only; the block is side-independent
    lookback: int
    sessions: int = 0  # sessions actually seen
    median_traded_value: Decimal | None = None  # ₹, median of close×volume
    min_traded_value: Decimal = Decimal(0)  # the floor judged against
    reasons: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        def s(v: Decimal | None) -> str | None:
            return str(v.quantize(_Q)) if v is not None else None

        return {
            "blocked": self.blocked,
            "has_data": self.has_data,
            "side": self.side,
            "lookback": self.lookback,
            "sessions": self.sessions,
            "median_traded_value": s(self.median_traded_value),
            "min_traded_value": str(self.min_traded_value),
            "reasons": list(self.reasons),
        }


def evaluate(
    *,
    traded_values: Sequence[Decimal],
    side: str,
    lookback: int = 20,
    min_traded_value: Decimal = Decimal(10_000_000),  # ₹1 crore/day default floor
) -> LiquidityVerdict:
    """Judge a signal's liquidity. Blocks (either side) when the median daily traded value
    over `lookback` sessions is below `min_traded_value`. Fail-open (un-blocked, ``has_data``
    False) when fewer than `lookback` sessions are supplied."""
    pos_side = _pos_side(side)
    n = len(traded_values)
    base = LiquidityVerdict(
        blocked=False,
        has_data=False,
        side=pos_side,
        lookback=lookback,
        sessions=n,
        min_traded_value=min_traded_value,
    )
    if n < lookback or lookback <= 0:
        return replace(base, reasons=["fewer than lookback sessions"])

    median = _median(list(traded_values[-lookback:]))
    reasons: list[str] = []
    blocked = median < min_traded_value
    if blocked:
        reasons.append(
            f"median daily traded value ₹{median.quantize(_Q)} over {lookback} sessions is below "
            f"the ₹{min_traded_value} floor — too illiquid to exit safely (either side)"
        )
    return LiquidityVerdict(
        blocked=blocked,
        has_data=True,
        side=pos_side,
        lookback=lookback,
        sessions=n,
        median_traded_value=median,
        min_traded_value=min_traded_value,
        reasons=reasons,
    )


def order_block_reason(verdict: LiquidityVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order, or None to allow it. Only ACTIVE blocks; in
    off/shadow this is a no-op."""
    if mode != "active" or not verdict.blocked:
        return None
    detail = "; ".join(verdict.reasons) if verdict.reasons else "below the liquidity floor"
    return f"Signal fails the liquidity overlay: {detail}"
