"""Shared level-sanity guards for the LIVE generation paths (Phase-2 gate).

`compute_levels` can legally return a stop loss EQUAL to the entry price:
a pivot swing-low that the last close exactly retests passes the class-cap
check (0% distance ≤ cap) — and then `compute_quantity` raises
ValueError("Stop loss must differ from entry price"), which killed the
WHOLE nightly run for every remaining stock and profile (bug-hunter,
Phase-2 gate; crash pair executed on real values).

The backtest engines already reject this bar (engine.py's wrong-side/
degenerate SL `continue`s, mirrored in Rust). This module gives the live
pipeline and legacy signal_service the same reject-don't-crash semantics —
analysis/ is frozen, so the guard lives here, not in risk.py.
"""

from __future__ import annotations

from decimal import Decimal

from app.analysis.risk import compute_levels


def safe_levels(
    direction: str,
    classification: str,
    entry: Decimal,
    swing_low: Decimal | None,
    swing_high: Decimal | None,
    ema20_daily: Decimal | None = None,
) -> tuple[Decimal, Decimal] | None:
    """compute_levels + reject degenerate/wrong-side stops. None = reject."""
    levels = compute_levels(
        direction=direction,
        classification=classification,
        entry=entry,
        swing_low=swing_low,
        swing_high=swing_high,
        ema20_daily=ema20_daily,
    )
    if levels is None:
        return None
    stop_loss, take_profit = levels
    if direction == "BUY" and stop_loss >= entry:
        return None
    if direction == "SELL" and stop_loss <= entry:
        return None
    return stop_loss, take_profit
