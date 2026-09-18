"""Queue item 2 — the ledger actually receives rows from the money path.

⭐ These are the tests whose absence let `ledger_entries` sit at 0 rows. `tests/test_ledger.py`
covers what `record()` DOES; nothing covered that anything CALLS it. Every assertion here goes
through `place_paper_order` / `close_position` rather than the ledger API, because reaching the
ledger directly is exactly the coverage that was already green while production wrote nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.broker.ledger_wiring import (
    LIVE_DATA_VERSION,
    LIVE_PAPER_EXPERIMENT,
    chain_for_position,
    market_date,
)
from app.broker.paper_broker import close_position, place_paper_order
from app.models.ledger import LedgerEntry
from app.models.signal import Signal
from app.services.ledger import LedgerError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user, make_stock


async def _trader(db: AsyncSession):
    """A user who may fill outside market hours.

    ⚠ `allow_offmarket_entry` is a column on USER, not a setting — the broker's off-market
    rejection is unconditional and per-account. Without it every test here 422s on that
    instead of on whatever it means to assert.
    """
    user = await create_test_user(db)
    user.allow_offmarket_entry = True
    await db.flush()
    return user


async def _signal(db: AsyncSession, stock_id: int) -> Signal:
    """Two scoring factors, so the ACTIVE entry-diversity gate does not reject the order for
    an unrelated reason."""
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="100.0000",
        stop_loss="95.0000",
        take_profit="115.0000",
        suggested_qty=10,
        confidence_pct=80,
        factor_scores={
            "DOW_TREND": {"weight": 20, "score": 0.8, "explanation": "uptrend"},
            "MACD_CROSS": {"weight": 15, "score": 0.6, "explanation": "bull cross"},
        },
        headline="BUY LEDGER WIRING TEST",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _entries(db: AsyncSession) -> list[LedgerEntry]:
    return list((await db.execute(select(LedgerEntry))).scalars().all())


@pytest.mark.asyncio
async def test_a_paper_fill_writes_an_execution_row(db: AsyncSession) -> None:
    """⛔ The regression for the defect itself: before this, `ledger_entries` could not gain a
    row from any production path."""
    user = await _trader(db)
    stock = await make_stock(db, symbol="LEDGERCO")
    sig = await _signal(db, stock.id)

    order, position = await place_paper_order(db, user, sig, side="BUY")

    rows = await _entries(db)
    assert len(rows) == 1, "a fill wrote no ledger row — this is the item-2 defect"
    row = rows[0]
    assert row.node_type == "execution"
    assert row.stock_id == stock.id
    assert row.user_id == user.id
    assert row.payload["order_id"] == order.id
    assert row.payload["position_id"] == position.id
    assert row.payload["fill_price"] == str(order.filled_price)


@pytest.mark.asyncio
async def test_provenance_is_populated_not_unknown(db: AsyncSession) -> None:
    """⭐ The sample-tag rule is the reason the columns are NOT NULL. A row that names its
    sample as 'unknown' is combinable with nothing, which makes writing it near-pointless."""
    user = await _trader(db)
    stock = await make_stock(db, symbol="PROVCO")
    sig = await _signal(db, stock.id)

    await place_paper_order(db, user, sig, side="BUY")

    row = (await _entries(db))[0]
    assert row.experiment_id == LIVE_PAPER_EXPERIMENT
    assert row.data_version == LIVE_DATA_VERSION
    assert row.code_commit, "no code_commit — the row cannot be tied to what produced it"


@pytest.mark.asyncio
async def test_close_writes_a_lifecycle_row_on_the_same_chain(db: AsyncSession) -> None:
    """⭐ Entry and exit must reconstruct as ONE trade. The chain id is derived from the
    position id rather than stored, so this is also the test that the derivation is stable
    across the two call sites."""
    user = await _trader(db)
    stock = await make_stock(db, symbol="CHAINCO")
    sig = await _signal(db, stock.id)
    _order, position = await place_paper_order(db, user, sig, side="BUY")

    await close_position(db, position, exit_price=Decimal("110"), reason="manual")

    rows = await _entries(db)
    assert len(rows) == 2
    kinds = {r.node_type for r in rows}
    assert kinds == {"execution", "position_lifecycle"}
    assert len({r.chain_id for r in rows}) == 1, "entry and exit landed on different chains"
    assert rows[0].chain_id == chain_for_position(position.id)


@pytest.mark.asyncio
async def test_the_close_row_carries_the_realised_outcome(db: AsyncSession) -> None:
    """A lifecycle row that does not say what the trade made is an audit trail of nothing."""
    user = await _trader(db)
    stock = await make_stock(db, symbol="PNLCO")
    sig = await _signal(db, stock.id)
    _order, position = await place_paper_order(db, user, sig, side="BUY")

    await close_position(db, position, exit_price=Decimal("110"), reason="tp_hit")

    # ⚠ Refresh first. Comparing the payload with the SAME in-memory object cannot catch the
    # rounding defect at all: `positions.realized_pnl` is Numeric(14,2) and the in-memory
    # Decimal is not, so only the round-tripped value proves the ledger reconciles with the book
    # (bug-hunter, 2026-09-18).
    await db.refresh(position)
    close_row = next(r for r in await _entries(db) if r.node_type == "position_lifecycle")
    assert close_row.payload["reason"] == "tp_hit"
    assert close_row.payload["realized_pnl_net_of_charges"] == str(position.realized_pnl)
    assert close_row.payload["exit_price"] == str(position.exit_price)
    assert "charges" in close_row.payload, "no charge line — P&L cannot be reconciled"


@pytest.mark.asyncio
async def test_averaging_in_writes_a_second_execution_row(db: AsyncSession) -> None:
    """⚠ A second entry into the same position must not overwrite the first's history: each
    FILL is its own row, even though the position is one object."""
    user = await _trader(db)
    stock = await make_stock(db, symbol="AVGCO")
    sig = await _signal(db, stock.id)

    # ⚠ Explicit small sizes: a default-sized first entry consumes the whole per-trade risk
    # budget, and the broker then (correctly) refuses the second as risk-stacking. The
    # averaging-in path is what is under test here, not the risk guard.
    await place_paper_order(db, user, sig, side="BUY", quantity=1)
    await place_paper_order(db, user, sig, side="BUY", quantity=1)

    execs = [r for r in await _entries(db) if r.node_type == "execution"]
    assert len(execs) == 2, "averaging in produced one row — the first fill's record was lost"
    assert len({r.chain_id for r in execs}) == 1, "both fills belong to the same position"


def test_the_chain_derivation_is_stable_and_distinct() -> None:
    """Derived, not stored — so it must be a pure function of the position id."""
    a = chain_for_position("pos-1")
    assert a == chain_for_position("pos-1")
    assert a != chain_for_position("pos-2")
    assert isinstance(a, uuid.UUID)


def test_as_of_is_the_market_date_not_the_utc_date() -> None:
    """⛔ `as_of` is the MARKET date and IST is UTC+5:30, so a UTC date files anything between
    00:00 and 05:30 IST onto the PREVIOUS session. Reachable via `manual_close_position`, which
    has no market-hours guard (bug-hunter, 2026-09-18)."""
    late_evening_utc = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)  # = 2026-09-19 00:30 IST

    assert market_date(late_evening_utc) == date(2026, 9, 19)
    assert late_evening_utc.date() == date(2026, 9, 18), "the UTC date is the wrong answer"

    midsession = datetime(2026, 9, 18, 6, 0, tzinfo=UTC)  # 11:30 IST — inside the session
    assert market_date(midsession) == midsession.date(), "they must agree during the session"


def test_a_ledger_failure_cannot_be_swallowed_as_a_broker_rejection() -> None:
    """⛔⛔ The fail-closed contract in one assertion.

    `api/v1/trading.place_order` and `paper_adapter.submit` both catch
    `(PaperOrderError, ValueError)`, append a REJECTED event and then COMMIT. While `LedgerError`
    subclassed `ValueError`, a failed ledger write would have committed the fill, returned 422,
    and left an open position with no ledger row — the exact inverse of the guarantee.
    """
    assert not issubclass(LedgerError, ValueError), (
        "LedgerError is a ValueError again — the order path's broker-rejection handlers will "
        "swallow it and COMMIT the fill, defeating fail-closed"
    )
