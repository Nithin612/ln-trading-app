"""Expiry sweeper (Phase 2 slice 2) — makes SIGNAL_ENGINE.md §5 true.

Regression context: the spec always claimed a 5-minute sweeper; before this
slice NOTHING ever wrote status="expired"/expired_at — expiry existed only
as a lazy query-time filter, so lapsed signals stayed "active" rows forever.
"""

from datetime import UTC, datetime, timedelta

from app.models.signal import Signal
from app.tasks.expiry_tasks import sweep_expired
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


async def _mk_signal(
    db: AsyncSession,
    stock_id: int,
    status: str,
    validity_until: datetime,
) -> Signal:
    signal = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="490.0000",
        stop_loss="482.0000",
        take_profit="506.0000",
        suggested_qty=250,
        confidence_pct=80,
        factor_scores={},
        headline="sweeper fixture",
        status=status,
        validity_until=validity_until,
        created_at=datetime.now(tz=UTC),
    )
    db.add(signal)
    await db.flush()
    return signal


class TestExpirySweep:
    async def test_sweeps_exactly_the_lapsed_active_rows(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="SWEEP1")
        now = datetime(2026, 7, 6, 10, 0, tzinfo=UTC)

        lapsed = await _mk_signal(db, stock.id, "active", now - timedelta(minutes=1))
        boundary = await _mk_signal(db, stock.id, "active", now)  # <= now → expires
        alive = await _mk_signal(db, stock.id, "active", now + timedelta(days=2))
        already = await _mk_signal(db, stock.id, "expired", now - timedelta(days=1))
        already_expired_at = already.expired_at
        await db.commit()

        count = await sweep_expired(db, now)
        assert count == 2

        for sig, expect_status in (
            (lapsed, "expired"),
            (boundary, "expired"),
            (alive, "active"),
            (already, "expired"),
        ):
            await db.refresh(sig)
            assert sig.status == expect_status

        assert lapsed.expired_at == now
        assert boundary.expired_at == now
        assert alive.expired_at is None
        # untouched: the sweep must not rewrite rows that were already expired
        assert already.expired_at == already_expired_at

    async def test_idempotent_second_sweep(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="SWEEP2")
        now = datetime(2026, 7, 6, 10, 0, tzinfo=UTC)
        await _mk_signal(db, stock.id, "active", now - timedelta(hours=3))
        await db.commit()

        assert await sweep_expired(db, now) == 1
        assert await sweep_expired(db, now) == 0

    async def test_noop_on_empty(self, db: AsyncSession) -> None:
        assert await sweep_expired(db, datetime.now(tz=UTC)) == 0
