"""Corporate-action adjustment of OPEN paper positions — Phase 6.8.5.

CA detection today is quarantine-only: it removes a flagged stock from the
SELECTION universe but does nothing to a position already held through an
ex-date. After a 5:1 split, a held position's `avg_entry_price`, `qty`,
`current_sl`, `current_tp` are all off by 5×, so its displayed P&L and its risk
(R) are silently wrong. This module fixes that for paper positions on the ex-date.

Invariants (the whole point):
  - The ratio comes from the VERIFIED `corporate_actions` row, never guessed from
    a price gap or parsed from headline text.
  - **R (risk) and reward:risk are preserved EXACTLY.** Entry (and peak) scale by
    the nominal ratio — matching the exchange's ex-date price adjustment — while SL
    and TP scale by their entry-relative DISTANCE × old_qty/new_qty, so
    `|entry − SL| × qty` (R) and `|TP − entry| × qty` (reward) are unchanged against
    the ACTUAL new qty. For a divisible ratio (every split, every 1:N bonus) this is
    the clean ÷factor and notional is preserved too. For a fractional-entitlement
    bonus (qty not divisible by `ratio_from`) the odd fraction is floored (cash-in-
    lieu in reality) and LOGGED: R stays exact, notional drops by that fraction.
    `peak_pnl` / `unrealized_pnl` are ₹ amounts invariant under the split — untouched
    (the monitor refreshes the mark from the ex-adjusted market price).
  - **Idempotent.** One `position_corporate_actions` ledger row per (position,
    action), UNIQUE — a re-run on the same ex-date is a no-op.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corporate_action import (
    CA_TYPES,
    CorporateAction,
    PositionCorporateAction,
)
from app.models.trading import Position

log = logging.getLogger(__name__)

_Q4 = Decimal("0.0001")  # Numeric(12,4) storage grid for price levels
_Q6 = Decimal("0.000001")  # ledger factor precision


async def record_corporate_action(
    db: AsyncSession,
    *,
    stock_id: int,
    action_type: str,
    ex_date: object,
    ratio_from: int,
    ratio_to: int,
    source: str = "manual",
    note: str | None = None,
) -> CorporateAction:
    """Record a verified split/bonus. Ratio is new:old shares — a 5:1 split is
    `ratio_from=1, ratio_to=5`; a 1:1 bonus is `1:2`. Both must be > 0. Raises
    ValueError on a bad type or non-positive ratio (the API maps it to 422)."""
    if action_type not in CA_TYPES:
        raise ValueError(f"action_type must be one of {CA_TYPES}, got {action_type!r}")
    if ratio_from <= 0 or ratio_to <= 0:
        raise ValueError("ratio_from and ratio_to must both be positive")
    ca = CorporateAction(
        stock_id=stock_id,
        action_type=action_type,
        ex_date=ex_date,
        ratio_from=ratio_from,
        ratio_to=ratio_to,
        source=source,
        note=note,
    )
    db.add(ca)
    await db.flush()
    return ca


def _scale_price(price: Decimal | None, ratio_from: int, ratio_to: int) -> Decimal | None:
    """A market price LEVEL (entry, peak) after the action: × ratio_from / ratio_to
    — the exchange's ex-date price adjustment. On the 4-dp grid; None passes through."""
    if price is None:
        return None
    return (Decimal(str(price)) * ratio_from / ratio_to).quantize(_Q4)


def _preserve_r_level(
    level: Decimal | None,
    old_entry: Decimal,
    new_entry: Decimal,
    old_qty: int,
    new_qty: int,
) -> Decimal | None:
    """An SL/TP level after the action, scaled so its entry-relative DISTANCE × the
    ACTUAL new qty is unchanged — so R (`|entry−SL|×qty`) and reward (`|TP−entry|×qty`)
    are preserved EXACTLY even when qty was floored to an integer. Side-agnostic (uses
    the signed distance from entry). For a divisible ratio this equals the clean
    ÷factor. None passes through."""
    if level is None:
        return None
    new_dist = (Decimal(str(level)) - old_entry) * old_qty / new_qty
    return (new_entry + new_dist).quantize(_Q4)


async def apply_ca_to_position(
    db: AsyncSession, position: Position, ca: CorporateAction
) -> PositionCorporateAction | None:
    """Adjust one OPEN position for one action, preserving R exactly. Returns the
    ledger row, or None if this (position, action) was already applied (idempotent)
    or the position is already closed (defensive — only open positions adjust)."""
    if position.closed_at is not None:
        return None
    already = (
        await db.execute(
            select(PositionCorporateAction).where(
                PositionCorporateAction.position_id == position.id,
                PositionCorporateAction.corporate_action_id == ca.id,
            )
        )
    ).scalars().first()
    if already is not None:
        return None

    old_qty = position.quantity
    old_entry = Decimal(str(position.avg_entry_price))
    # qty × factor as integer arithmetic — a fractional entitlement floors (real-world
    # cash-in-lieu). R is preserved regardless because SL/TP scale by distance × the
    # ACTUAL new_qty below; only notional drops by the floored fraction.
    new_qty = old_qty * ca.ratio_to // ca.ratio_from
    if new_qty <= 0:
        # A ratio that would zero the position (or worse). Refuse — never mangle it.
        log.error(
            "CA %s on position %s: qty %d × %d:%d floors to %d — refusing to adjust",
            ca.id, position.id, old_qty, ca.ratio_from, ca.ratio_to, new_qty,
        )
        return None
    if (old_qty * ca.ratio_to) % ca.ratio_from != 0:
        log.warning(
            "CA %s on position %s: qty %d not divisible by ratio_from %d — fractional "
            "entitlement floored to %d shares (R preserved exactly; notional drops by "
            "the fraction, i.e. cash-in-lieu is not credited in paper)",
            ca.id, position.id, old_qty, ca.ratio_from, new_qty,
        )
    # Entry (and peak) follow the nominal ex-date price scale; SL/TP preserve R.
    new_entry = (old_entry * ca.ratio_from / ca.ratio_to).quantize(_Q4)

    position.quantity = new_qty
    position.avg_entry_price = new_entry
    position.current_sl = _preserve_r_level(
        position.current_sl, old_entry, new_entry, old_qty, new_qty
    )
    position.current_tp = _preserve_r_level(
        position.current_tp, old_entry, new_entry, old_qty, new_qty
    )
    position.peak_price = _scale_price(position.peak_price, ca.ratio_from, ca.ratio_to)
    # peak_pnl / unrealized_pnl are ₹ P&L, invariant under the split — untouched.

    ledger = PositionCorporateAction(
        position_id=position.id,
        corporate_action_id=ca.id,
        factor=(Decimal(ca.ratio_to) / Decimal(ca.ratio_from)).quantize(_Q6),
        old_quantity=old_qty,
        new_quantity=new_qty,
        old_avg_entry_price=old_entry,
        new_avg_entry_price=new_entry,
    )
    db.add(ledger)
    await db.flush()
    return ledger


async def apply_ex_date_corporate_actions(
    db: AsyncSession, as_of: date
) -> list[PositionCorporateAction]:
    """Apply every corporate action with ex-date ON OR BEFORE `as_of` to the OPEN
    paper positions in the affected stock. **`<=`, not `==`**, so a missed pre-market
    run (worker restart/soak) or a CA entered late is caught up on the next run — a
    position left un-adjusted through a split would otherwise false-stop-out when the
    monitor sees the old SL against the ex-adjusted tape, booking a fake loss into the
    30-day clock. The idempotency ledger makes re-scanning past ex-dates a no-op for
    already-adjusted positions.

    Commits PER POSITION (like gap_fill) so one collision can't abort the batch: a
    lost concurrent race (IntegrityError on the unique ledger key — two runs both
    passed the idempotency SELECT) is rolled back and skipped, not fatal. Returns the
    ledger rows written this run."""
    cas = (
        await db.execute(select(CorporateAction).where(CorporateAction.ex_date <= as_of))
    ).scalars().all()
    applied: list[PositionCorporateAction] = []
    for ca in cas:
        positions = (
            await db.execute(
                select(Position).where(
                    Position.stock_id == ca.stock_id,
                    Position.mode == "paper",
                    Position.closed_at.is_(None),
                )
            )
        ).scalars().all()
        for pos in positions:
            try:
                led = await apply_ca_to_position(db, pos, ca)
                if led is not None:
                    await db.commit()
                    applied.append(led)
            except IntegrityError:
                await db.rollback()
                log.info(
                    "CA %s position %s already applied by a concurrent run — skipped",
                    ca.id, pos.id,
                )
    return applied
