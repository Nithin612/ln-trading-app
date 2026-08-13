"""Regime-eligibility overlay — the §8-validated regime gate (Phase 6).

The §8 walk-forward (`docs/analysis/gate-walkforward-*.md`, quant-verifier PASS)
established that committed entries whose decision-bar ADX regime is transitional
(20–25) are net-negative, and that skipping them improves win rate, Sharpe and
max drawdown out-of-sample. This module acts on that finding as a downstream
OVERLAY — it never touches the frozen confluence engine (cf. `risk_guards.py`:
"analysis/ is frozen, so the guard lives here"). It reads a committed signal's
own factor payload, recovers its regime via the canonical `regime` taxonomy, and
decides eligibility.

Modes (`settings.regime_gate_mode`), default **shadow**:
  off    — no gate.
  shadow — the verdict is computed for MEASUREMENT only (see
           `app/services/regime_gate_shadow.py`); the order path never acts on
           it. A new gate lives here until forward evidence on the live
           population agrees with the backtest.
  active — the order path rejects an ineligible signal. Flipping shadow→active
           is one setting and fully reversible; it is the behaviour-changing step
           that needs explicit sign-off.

**Precondition for the active flip:** regime is currently recovered by parsing
the frozen ADX factor's explanation ("ADX=X"). That is fine while the gate only
MEASURES (shadow), but before it gates real orders (active) the numeric ADX level
should be persisted as a first-class field at signal commit and read here — a
money-path gate must not hang off prose parsing (quant-verifier 2026-08-13).

**Fail-open:** a gate that suppresses trades must never suppress on uncertainty,
so a signal whose regime can't be recovered ("regime n/a") is eligible.
"""

from __future__ import annotations

from app.models.signal import Signal
from app.signals import regime as rg

# Which regimes the gate suppresses. The §8 finding is transitional-only; choppy
# is negative too but skipping it as well over-filtered in the gate experiment.
SKIP_REGIMES: frozenset[str] = frozenset({rg.TRANSITIONAL})


def signal_regime(signal: Signal) -> str:
    """The signal's ADX regime bucket, recovered from its stored factor payload
    (fail-open to 'regime n/a')."""
    return rg.regime_from_factor_scores(signal.factor_scores)


def is_eligible(signal: Signal, *, skip: frozenset[str] = SKIP_REGIMES) -> bool:
    """False only when the signal's regime is in the skip-set. Unknown regime →
    eligible (fail-open)."""
    return signal_regime(signal) not in skip


def order_block_reason(
    signal: Signal, mode: str, *, skip: frozenset[str] = SKIP_REGIMES
) -> str | None:
    """The 409 reason to reject a paper order on this signal, or None to allow it.

    Only ACTIVE mode ever blocks — in off/shadow this is a no-op, so wiring it
    into the order path changes no behaviour until the gate is flipped."""
    if mode != "active":
        return None
    if is_eligible(signal, skip=skip):
        return None
    return (
        f"Signal regime is {signal_regime(signal)} — gated by the regime overlay "
        "(net-negative expectancy; §8-validated)"
    )
