"""Sector / index relative-strength eligibility overlay — Market Context Engine, slice 1.

The tradeable confluence engine is pure bottom-up single-name technicals; it carries no
top-down "is this stock's sector / index leading?" context. That gap is the reason the
MCE exists (``docs/phases/phase-MCE-market-context-engine.md``). This overlay supplies the
missing relative-strength read as a downstream ELIGIBILITY gate / modifier — **never** a
new additive confluence factor. (An additive context factor would dilute the ≥70%
confluence gate; the walk-forward-negative intraday RS *profiles* are the cautionary
precedent — see the MCE plan's "GATES/MODIFIERS, not additive factors" principle.)

Same shape as ``circuit_guard`` / ``regime_guard`` / ``entry_quality``: **pure** (no I/O),
**moded** (off / shadow / active), **fail-open**. It reuses the platform's OWN
relative-strength definition (``app/profiles/setups.eval_relative_strength``): the stock's
return over ``lookback`` sessions minus its benchmark's return over the same window; a BUY
wants out-performance (``excess ≥ min_excess_pct``), a SELL wants under-performance
(``excess ≤ -min_excess_pct``). Reusing that definition — rather than inventing one — keeps
this overlay consistent with the (frozen-adjacent) profile logic.

The benchmark close series is **supplied by the caller**. This module is deliberately
agnostic to whether that series is a synthesized constituent basket or a real index feed —
choosing that source is a separate MCE decision, and the overlay's arithmetic is identical
either way.

**Caller contract (to be ENFORCED at the wiring slice, not here):** the two series must be
session-aligned — the same trailing NSE trading days, both ending on completed candle N
(never the forming / fill candle) — so the positional ``[-1]`` / ``[-(lookback + 1)]`` compare
the same windows and cannot look ahead (trading-domain.md: compute on N, valid from N+1). This
pure module aligns POSITIONALLY only and fails open on a gap; the wiring slice must slice both
series to identical completed-candle windows and test that contract.

Modes (a future ``settings.sector_rs_gate_mode``), default **off**:
  off    — no gate. Slice 1 ships unwired; the module is off until the order-path /
           shadow-sidecar slice lands, so it changes no behaviour today.
  shadow — the verdict is computed for MEASUREMENT only (a future ``sector-rs-shadow``
           sidecar, mirroring ``regime_gate_shadow``); the order path never acts on it.
  active — the order path rejects an ineligible signal. Flipping to active is the
           behaviour-changing step: it needs forward shadow evidence + a §8-on-≥2y
           regression + explicit sign-off (the R-track ceremony), never a silent flip.

**Fail-open** (a gate that suppresses trades must never suppress on uncertainty): a missing
benchmark, a series shorter than ``lookback + 1``, or a degenerate base price all yield an
un-blocked verdict.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

_Q = Decimal("0.0001")
_HUNDRED = Decimal(100)


def _pos_side(side: str) -> str:
    """Normalise an order/signal side to LONG / SHORT. BUY→LONG, SELL→SHORT;
    LONG/SHORT pass through. Mirrors ``circuit_guard._pos_side``."""
    s = side.upper()
    if s in ("BUY", "LONG"):
        return "LONG"
    return "SHORT"


@dataclass(frozen=True)
class RelativeStrengthVerdict:
    """The overlay's read on one signal — the audit trail stamped on the order's
    ``broker_payload["sector_rs"]`` so a shadow report can aggregate what the gate WOULD
    suppress, and so any decision is reconstructable later.

    ``blocked`` is the pure eligibility read (independent of mode); ``order_block_reason``
    applies the mode. All percents are ``Decimal`` — a float round-trip through JSON would
    lose the exactness the money rules require."""

    blocked: bool
    has_benchmark: bool  # False ⇒ no benchmark series; blocked is False (fail-open)
    side: str  # "LONG" | "SHORT"
    lookback: int
    benchmark_label: str | None = None  # e.g. "sector:Information Technology" | "NIFTY50"
    stock_ret_pct: Decimal | None = None
    bench_ret_pct: Decimal | None = None
    excess_pct: Decimal | None = None  # stock_ret − bench_ret
    min_excess_pct: Decimal = Decimal(0)
    reasons: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        """JSON-safe telemetry. Percents as strings (Decimal-exact)."""

        def s(v: Decimal | None) -> str | None:
            return str(v.quantize(_Q)) if v is not None else None

        return {
            "blocked": self.blocked,
            "has_benchmark": self.has_benchmark,
            "side": self.side,
            "lookback": self.lookback,
            "benchmark_label": self.benchmark_label,
            "stock_ret_pct": s(self.stock_ret_pct),
            "bench_ret_pct": s(self.bench_ret_pct),
            "excess_pct": s(self.excess_pct),
            "min_excess_pct": str(self.min_excess_pct),
            "reasons": list(self.reasons),
        }


def _return_pct(now: Decimal, then: Decimal) -> Decimal:
    """Simple percent return, Decimal throughout."""
    return (now - then) / then * _HUNDRED


def evaluate(
    *,
    stock_closes: Sequence[Decimal],
    benchmark_closes: Sequence[Decimal] | None,
    side: str,
    lookback: int = 20,
    min_excess_pct: Decimal = Decimal(0),
    benchmark_label: str | None = None,
) -> RelativeStrengthVerdict:
    """Judge a signal's relative strength vs its benchmark over ``lookback`` sessions.

    Reuses ``eval_relative_strength``'s definition exactly:
      excess = stock_return − benchmark_return   (over the last ``lookback`` sessions)
      BUY  passes when  excess ≥  min_excess_pct   (out-performing → eligible)
      SELL passes when  excess ≤ -min_excess_pct   (under-performing → eligible)
    ``blocked`` is the negation of "passes".

    Fail-open (un-blocked, with ``reasons`` recording why it could not assess): benchmark
    absent, either series shorter than ``lookback + 1`` bars, or a zero base price."""
    pos_side = _pos_side(side)
    base = RelativeStrengthVerdict(
        blocked=False,
        has_benchmark=benchmark_closes is not None,
        side=pos_side,
        lookback=lookback,
        benchmark_label=benchmark_label,
        min_excess_pct=min_excess_pct,
    )

    if benchmark_closes is None:
        return base
    need = lookback + 1
    if len(stock_closes) < need or len(benchmark_closes) < need:
        return RelativeStrengthVerdict(
            **{**base.__dict__, "reasons": ["series shorter than lookback + 1"]}
        )

    stock_now, stock_then = stock_closes[-1], stock_closes[-need]
    bench_now, bench_then = benchmark_closes[-1], benchmark_closes[-need]
    # Fail open on a gap: the annotated type is Sequence[Decimal], but a real feed can
    # carry a hole (a missing bar → None, or a non-Decimal). Decimal arithmetic on such a
    # value would RAISE — which would suppress on an exception, violating "never suppress on
    # uncertainty". Guard the four endpoints we actually read before any arithmetic.
    if any(not isinstance(x, Decimal) for x in (stock_now, stock_then, bench_now, bench_then)):
        return RelativeStrengthVerdict(
            **{**base.__dict__, "reasons": ["series contains a gap (missing/non-Decimal bar)"]}
        )
    if stock_then == 0 or bench_then == 0:
        return RelativeStrengthVerdict(**{**base.__dict__, "reasons": ["degenerate base price"]})

    stock_ret = _return_pct(stock_now, stock_then)
    bench_ret = _return_pct(bench_now, bench_then)
    excess = stock_ret - bench_ret

    if pos_side == "LONG":
        passed = excess >= min_excess_pct
        verb, want = "under-performs", "out-performance"
    else:
        passed = excess <= -min_excess_pct
        verb, want = "out-performs", "under-performance"

    reasons: list[str] = []
    if not passed:
        label = benchmark_label or "its benchmark"
        reasons.append(
            f"{pos_side} but stock {verb} {label} by {excess.quantize(_Q)}% over {lookback} "
            f"sessions (wants {want} vs min_excess {min_excess_pct}%)"
        )

    return RelativeStrengthVerdict(
        blocked=not passed,
        has_benchmark=True,
        side=pos_side,
        lookback=lookback,
        benchmark_label=benchmark_label,
        stock_ret_pct=stock_ret,
        bench_ret_pct=bench_ret,
        excess_pct=excess,
        min_excess_pct=min_excess_pct,
        reasons=reasons,
    )


def order_block_reason(verdict: RelativeStrengthVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order on this signal, or None to allow it.

    Only ACTIVE mode ever blocks — in off/shadow this is a no-op, so wiring it into the
    order path (a later slice) changes no behaviour until the gate is flipped."""
    if mode != "active" or not verdict.blocked:
        return None
    detail = "; ".join(verdict.reasons) if verdict.reasons else "relative strength below threshold"
    return f"Signal fails the sector/index relative-strength overlay: {detail}"
