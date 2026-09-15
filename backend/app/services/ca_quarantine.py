"""The CA quarantine's clearing path — §77 / Q-R3.

`ca_detector` sets `stocks.ca_flagged_at` when a session's open gaps far enough from the
previous close to suggest an unadjusted corporate action, and
`universe_service.resolve_universe` then excludes that name from every suggestion
universe. Until now there was **no way back**: one writer, no clearer anywhere, while
`stock.py`'s own docstring promised "unflag via admin after verifying".

⭐ **It is not a theoretical leak.** Measured 2026-09-14: 7 flagged, 5 of them active, and
**4 of the 7 flagged that same day**. The tradeable universe was shrinking by roughly four
names a week, permanently, and the only visible symptom would have been suggestions
quietly covering fewer stocks.

⛔ **An expiry would be the wrong instrument.** The contamination is in the unadjusted
price history and does not heal with time; a timer would re-admit contaminated bars on a
schedule. Only a human saying "I checked this, and here is why it is safe" clears it.

⚠ **Clearing does NOT adjust anything.** It asserts the history is usable — either the gap
was a real price move, or the series has since been adjusted, or the bad bars have aged
out of every indicator window. If the name genuinely needs adjusting, the instrument is
`POST /corporate-actions` (a verified ratio + ex-date), not this.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corporate_action import CaFlagEvent
from app.models.stock import Stock

log = logging.getLogger(__name__)


class NotFlaggedError(Exception):
    """The stock is not currently quarantined, so there is nothing to clear.

    ⚠ Deliberately distinct from "no such stock": clearing an unflagged name is a
    no-op that would otherwise return 200 and teach the caller nothing."""


@dataclass(frozen=True)
class FlaggedStock:
    stock_id: int
    symbol: str
    flagged_at: datetime
    reason: str | None
    is_active: bool


async def list_flagged(db: AsyncSession) -> list[FlaggedStock]:
    """Everything currently in quarantine, oldest first — the review queue.

    ⚠ Includes INACTIVE names. The flag and the universe rule are independent, and a
    reviewer deciding what to release should see the whole quarantine rather than the
    subset that happens to be tradeable today."""
    rows = (
        await db.execute(
            select(
                Stock.id, Stock.symbol, Stock.ca_flagged_at, Stock.ca_flag_reason,
                Stock.is_active,
            )
            .where(Stock.ca_flagged_at.is_not(None))
            .order_by(Stock.ca_flagged_at)
        )
    ).all()
    return [
        FlaggedStock(
            stock_id=r.id, symbol=r.symbol, flagged_at=r.ca_flagged_at,
            reason=r.ca_flag_reason, is_active=r.is_active,
        )
        for r in rows
    ]


async def record_flag(
    db: AsyncSession, *, stock_id: int, reason: str, at: datetime
) -> None:
    """Append the machine's side of the log. Called by `ca_detector` in the same
    transaction as the flag, so the log cannot disagree with `stocks`.

    ⚠ `at` is REQUIRED, and it must be the same value written to `stocks.ca_flagged_at`.
    Leaving it to the column's `server_default now()` used a different clock:
    Postgres `now()` is `transaction_timestamp()`, and `eod_catchup` scans up to 21
    sessions in ONE session — so an event could be timestamped minutes before the flag it
    records, and disagree with `stocks` for the same event. In a log whose whole semantic
    is ORDERING, and which `history()` sorts by `at`, that is enough to put an admin's
    clear before the re-flag it actually preceded (bug-hunter, 2026-09-15).

    ⚠ No commit here — the detector commits once for the whole batch, and splitting that
    would let a crash leave flags without their events."""
    db.add(CaFlagEvent(stock_id=stock_id, event="flagged", reason=reason, at=at))


async def clear_flag(
    db: AsyncSession, *, stock_id: int, actor_user_id: int, reason: str
) -> FlaggedStock:
    """Release a stock from quarantine, recording who and why. Returns what was cleared.

    Raises `NotFlaggedError` when the stock does not exist or is not currently quarantined —
    the two are the same answer to the caller ("there is nothing here to release") and
    distinguishing them would leak which ids exist.

    ⚠ The stock becomes eligible for re-flagging immediately: the detector skips rows
    where `ca_flagged_at IS NULL`, so a genuine unadjusted action on a later session will
    quarantine it again. That is correct, and it is exactly why the log is append-only —
    the next flag must not erase this review.
    """
    stock = (
        await db.execute(
            select(Stock).where(Stock.id == stock_id, Stock.ca_flagged_at.is_not(None))
        )
    ).scalar_one_or_none()
    if stock is None:
        raise NotFlaggedError(f"stock {stock_id} is not in CA quarantine")

    # The query filters `is_not(None)`, but the column is Optional in the model and
    # mypy cannot carry a SQL predicate into Python types.
    assert stock.ca_flagged_at is not None
    cleared = FlaggedStock(
        stock_id=stock.id, symbol=stock.symbol, flagged_at=stock.ca_flagged_at,
        reason=stock.ca_flag_reason, is_active=stock.is_active,
    )
    db.add(
        CaFlagEvent(
            stock_id=stock.id, event="cleared", at=datetime.now(tz=UTC),
            reason=reason, actor_user_id=actor_user_id,
        )
    )
    stock.ca_flagged_at = None
    stock.ca_flag_reason = None
    await db.commit()
    log.warning(
        "CA quarantine CLEARED: %s (stock_id=%s) by user %s — %s (was: %s)",
        cleared.symbol, cleared.stock_id, actor_user_id, reason, cleared.reason,
    )
    return cleared


async def history(db: AsyncSession, *, stock_id: int) -> list[CaFlagEvent]:
    """Every flag and clear for one stock, oldest first."""
    return list(
        (
            await db.execute(
                select(CaFlagEvent)
                .where(CaFlagEvent.stock_id == stock_id)
                .order_by(CaFlagEvent.at, CaFlagEvent.id)
            )
        ).scalars()
    )
