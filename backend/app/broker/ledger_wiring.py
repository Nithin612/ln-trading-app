"""Queue item 2 — the production caller for the append-only ledger.

## ⛔⛔ The defect

`app/services/ledger.py` was built, migrated, tested — and **imported by `tests/test_ledger.py`
only**. `ledger_entries` held 0 rows and no production code path could ever add one. It is the one
artifact designed to survive the next database loss, and it was wired to nothing.

## ⭐ Fail CLOSED, in the fill's own transaction — deliberately against the house pattern

Every order-path overlay in this codebase fails **open** inside a `begin_nested` savepoint, and
that is right for a *gate*: refusing to block a trade on a rule you are unsure about. It is exactly
wrong for an audit trail. An overlay that fails open declines to interfere; a ledger that fails
open **lets money move with no record of it**, which is the failure this table exists to prevent.

So the ledger row is written in the **same transaction as the fill**: either both land or neither
does, and there is no such thing as an untraced execution. The cost of that choice is a new way for
an order to fail. It is accepted here because

- this is paper trading, so a refused order costs nothing, and
- the 2026-09-07 loss is the reason the module exists; an audit trail that silently skips rows
  under load is not an audit trail.

⚠ **Revisit at Phase 7.** With real money, "refuse the order because the ledger insert failed" is a
different trade-off and deserves its own decision rather than inheriting this one.

⚠ **Two costs of fail-closed, stated rather than discovered later** (bug-hunter, 2026-09-18):

- **The position monitor commits once per scan**, so a single failing `record_close` discards
  *every* close in that beat. With 25 open positions and three stops hit in the same minute, a
  ledger failure on the second loses all three exits; `max_retries=0`, so they are only re-taken
  next minute if price is still through the stop. The alternative — a per-position savepoint —
  weakens fail-closed, and that is a Phase-7 decision, not a silent one.
- **`ledger.record` calls `current_commit()`**, which shells out to `git rev-parse HEAD` on the
  event loop. `lru_cache` makes it once per process (measured **2.29 ms**), but the bound is its
  5 s timeout, so a stalled filesystem would stall the API. Warming it in the FastAPI lifespan
  would remove that entirely.

## Chaining without a schema change

A trade's entry and exit must share a `chain_id`, and `Position.id` is a UUID *string*, not a
`uuid.UUID`. Rather than add a column, the chain id is **derived** —
`uuid5(namespace, "position:{id}")` — so the
close can recompute exactly what the fill used, with nothing stored and nothing to drift.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import LedgerEntry
from app.models.trading import Order, Position
from app.services import ledger

_IST = ZoneInfo("Asia/Kolkata")

#: Fixed namespace for derived chain ids. ⛔ Never regenerate it: the value is what lets a row
#: written today be joined to one written before this comment existed.
CHAIN_NAMESPACE = uuid.UUID("6f1b2f3c-9a44-5d8e-b7c1-2e5a9d0f4b31")

#: The sample tag for rows produced by live paper trading, as opposed to a study run.
#: `record()` refuses a blank one, which is the point (§16.1).
LIVE_PAPER_EXPERIMENT = "live-paper"


def _paise(v: Decimal) -> Decimal:
    """Round to what `Numeric(14,2)` will actually store."""
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def chain_for_position(position_id: str) -> uuid.UUID:
    """The `chain_id` shared by every row about one position. Derived, never stored.

    ⚠ `Position.id` is a UUID STRING in this schema, not an integer — the id goes into the
    uuid5 name verbatim, so the derivation is stable whatever the column type is.
    """
    return uuid.uuid5(CHAIN_NAMESPACE, f"position:{position_id}")


#: ⭐ The DATA DEFINITION, not the session. ⛔ This was `live-feed:{date}` and that was wrong
#: (bug-hunter, 2026-09-18): a version that changes every day duplicates the `as_of` axis and,
#: by the ledger's own §16.1 rule, makes no two live fills from different days combinable — it
#: destroys the column's discriminating power instead of providing it. Bump it when the FEED or
#: FILL MODEL changes; 6.8.2 (spread-aware fills) and A37 (participation) were exactly such bumps.
LIVE_DATA_VERSION = "live-feed:v1"


def market_date(when: datetime) -> date:
    """The MARKET date this row belongs to — **IST, not UTC**.

    ⛔ `as_of` is documented in `models/ledger.py` as the market date, and IST is UTC+5:30, so a
    UTC date stamps anything between **00:00 and 05:30 IST onto the previous session**
    (bug-hunter, 2026-09-18). That is reachable without special config: `manual_close_position`
    has no market-hours guard, and off-market entries are per-account. During the session itself
    (03:45-10:00 UTC) the two never differ, which is exactly why it would not have shown up in
    normal use — and why `export_day` and the `as_of` index would have silently filed those rows
    on the wrong session, breaking the TIME-axis rule this column exists to enforce.
    """
    return when.astimezone(_IST).date()


async def record_fill(
    db: AsyncSession,
    *,
    order: Order,
    position: Position,
    signal_id: str | None = None,
) -> LedgerEntry:
    """One `execution` row per fill. Called from `place_paper_order` before it returns.

    ⚠ Records the ORDER's filled price and quantity, not the position's average: this row is
    about what happened at this fill, and averaging-in would make a second entry overwrite the
    history of the first.
    """
    when = order.filled_at or datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "order_id": order.id,
        "position_id": position.id,
        "signal_id": signal_id,
        "side": order.side,
        "quantity": order.filled_qty,
        "fill_price": str(order.filled_price),
        "position_side": position.side,
        "position_quantity_after": position.quantity,
        "avg_entry_after": str(position.avg_entry_price),
        "stop_loss": str(position.current_sl) if position.current_sl is not None else None,
        "take_profit": str(position.current_tp) if position.current_tp is not None else None,
        # ⚠ The broker's own FILL audit only — slippage model and the post-fill `chase`.
        # ⛔ The gate stamps (`circuit_gate`, `entry_quality`, `chase_gate`) are NOT here:
        # `api/v1/trading.place_order` merges them onto `order.broker_payload` AFTER
        # `place_paper_order` returns, so this snapshot predates them (bug-hunter,
        # 2026-09-18). Recording them needs the stamping moved inside the broker, which
        # is a money-path change of its own — tracked, not done here.
        "broker_payload": order.broker_payload or {},
    }
    return await ledger.record(
        db,
        node_type="execution",
        chain_id=chain_for_position(position.id),
        as_of=market_date(when),
        experiment_id=LIVE_PAPER_EXPERIMENT,
        data_version=LIVE_DATA_VERSION,
        stock_id=position.stock_id,
        user_id=position.user_id,
        label=f"{order.side} {order.filled_qty} @ {order.filled_price}",
        payload=payload,
    )


async def record_close(
    db: AsyncSession, *, order: Order, position: Position, reason: str
) -> LedgerEntry:
    """One `position_lifecycle` row per close, carrying the realised outcome.

    ⚠ `realized_pnl` here is net of charges (the broker sets it that way), and the payload says
    so rather than leaving a reader to guess which side of the fee line a number sits on.
    """
    when = order.filled_at or datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "order_id": order.id,
        "position_id": position.id,
        "signal_id": position.signal_id,
        "reason": reason,
        "exit_price": str(position.exit_price),
        "quantity": order.filled_qty,
        "avg_entry_price": str(position.avg_entry_price),
        # ⚠ Quantized to paise. `positions.realized_pnl` is Numeric(14,2), so the
        # unrounded in-memory Decimal is NOT the number the book will hold — on an
        # averaged-in position they differ, and a ledger that cannot reconcile with
        # the book it audits is worth little (bug-hunter, 2026-09-18). ROUND_HALF_UP
        # to match Postgres numeric, not Decimal's default banker's rounding.
        "realized_pnl_net_of_charges": str(_paise(position.realized_pnl)),
        "charges": str(_paise(position.charges)) if position.charges is not None else None,
        "opened_at": position.opened_at.isoformat() if position.opened_at else None,
        "closed_at": position.closed_at.isoformat() if position.closed_at else None,
        "broker_payload": order.broker_payload or {},
    }
    return await ledger.record(
        db,
        node_type="position_lifecycle",
        chain_id=chain_for_position(position.id),
        as_of=market_date(when),
        experiment_id=LIVE_PAPER_EXPERIMENT,
        data_version=LIVE_DATA_VERSION,
        stock_id=position.stock_id,
        user_id=position.user_id,
        label=f"close {position.side} {order.filled_qty} @ {position.exit_price} ({reason})",
        payload=payload,
    )
