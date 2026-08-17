"""Circuit-band eligibility overlay — Phase 6.8.3.

A long whose stock is pinned near its LOWER circuit has no buyers: the stop
cannot fill at any price, software or exchange (a structurally un-exitable
trade). A short near the UPPER band is the mirror. This overlay skips entering a
name whose entry sits within ``circuit_proximity_pct`` of its ADVERSE band —
long → lower, short → upper. Bands ≥ 20% wide are legitimately tradeable, so we
gate on PROXIMITY, not band existence.

This is a downstream ELIGIBILITY overlay — it never touches the frozen confluence
engine (the same shape as ``regime_guard.py`` and ``risk_guards.py``). Bands come
from the live cache (``app/broker/circuit_bands.py``); this module is pure — it
takes an entry + side + band and decides.

Modes (``settings.circuit_gate_mode``), default **shadow** — identical lifecycle
to the regime gate:
  off    — no gate.
  shadow — the verdict is computed and stamped on the order for MEASUREMENT only
           (``circuit-gate-shadow-<date>.md``); the order path never acts on it.
  active — the order path rejects an ineligible signal. Flipping shadow→active is
           one setting and fully reversible; it needs forward evidence + sign-off.

**Fail-open:** a gate that suppresses trades must never suppress on uncertainty,
so a signal with no cached band (``band is None``) is eligible.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.broker.circuit_bands import CircuitBand

_Q = Decimal("0.0001")


@dataclass(frozen=True)
class CircuitVerdict:
    """The circuit gate's read on one entry — the audit trail stamped on the
    order's ``broker_payload["circuit_gate"]`` so the shadow report can aggregate
    what the gate WOULD suppress, and so any decision is reconstructable later."""

    blocked: bool  # True only when the entry is within proximity of the adverse band
    has_band: bool  # False ⇒ no cached band; blocked is False (fail-open)
    side: str  # "LONG" | "SHORT"
    adverse: str | None  # "lower" (long) | "upper" (short) — the band that can trap
    entry: Decimal
    lower: Decimal | None
    upper: Decimal | None
    distance_pct: Decimal | None  # % from entry to the adverse band (None w/o band)
    proximity_pct: Decimal  # the threshold this verdict was judged against

    def as_payload(self) -> dict[str, object]:
        """JSON-safe telemetry. Money/percent as strings — a float round-trip
        through JSON would lose the Decimal exactness the money rules require."""
        return {
            "blocked": self.blocked,
            "has_band": self.has_band,
            "side": self.side,
            "adverse": self.adverse,
            "entry": str(self.entry),
            "lower": str(self.lower) if self.lower is not None else None,
            "upper": str(self.upper) if self.upper is not None else None,
            "distance_pct": (
                str(self.distance_pct.quantize(_Q)) if self.distance_pct is not None else None
            ),
            "proximity_pct": str(self.proximity_pct),
        }


def _pos_side(side: str) -> str:
    """Normalise an order/position side to LONG/SHORT. BUY→LONG, SELL→SHORT;
    LONG/SHORT pass through."""
    s = side.upper()
    if s in ("BUY", "LONG"):
        return "LONG"
    return "SHORT"


def evaluate(
    entry: Decimal,
    side: str,
    band: CircuitBand | None,
    proximity_pct: Decimal,
) -> CircuitVerdict:
    """Judge one entry against its band. Long → distance to the LOWER band; short
    → distance to the UPPER band; blocked when that distance ≤ proximity_pct.

    Fail-open: ``band is None`` (or a non-positive entry, which can't yield a
    meaningful percent) returns an un-blocked verdict."""
    pos_side = _pos_side(side)
    if band is None or entry <= 0:
        return CircuitVerdict(
            blocked=False,
            has_band=band is not None,
            side=pos_side,
            adverse="lower" if pos_side == "LONG" else "upper",
            entry=entry,
            lower=band.lower if band is not None else None,
            upper=band.upper if band is not None else None,
            distance_pct=None,
            proximity_pct=proximity_pct,
        )
    if pos_side == "LONG":
        adverse, adverse_price = "lower", band.lower
        distance_pct = (entry - adverse_price) / entry * Decimal(100)
    else:
        adverse, adverse_price = "upper", band.upper
        distance_pct = (adverse_price - entry) / entry * Decimal(100)
    return CircuitVerdict(
        blocked=distance_pct <= proximity_pct,
        has_band=True,
        side=pos_side,
        adverse=adverse,
        entry=entry,
        lower=band.lower,
        upper=band.upper,
        distance_pct=distance_pct,
        proximity_pct=proximity_pct,
    )


def order_block_reason(verdict: CircuitVerdict, mode: str) -> str | None:
    """The 409 reason to reject a paper order on this signal, or None to allow it.

    Only ACTIVE mode ever blocks — in off/shadow this is a no-op, so wiring it
    into the order path changes no behaviour until the gate is flipped."""
    if mode != "active" or not verdict.blocked:
        return None
    dist = verdict.distance_pct
    dist_s = f"{dist.quantize(_Q)}%" if dist is not None else "—"
    return (
        f"Entry {verdict.entry} is {dist_s} from the {verdict.adverse} circuit band "
        f"(≤ {verdict.proximity_pct}%) — gated by the circuit overlay: a "
        f"{verdict.side} pinned near its {verdict.adverse} band cannot be exited"
    )
