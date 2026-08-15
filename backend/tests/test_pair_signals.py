"""PairSignal model (Phase 6.5b slice 1) — the additive, shadow-only pair table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.pair import PairSignal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


async def test_pair_signal_persists_with_shadow_defaults(db: AsyncSession) -> None:
    a = await make_stock(db, symbol="LEGA")
    b = await make_stock(db, symbol="LEGB")
    sig = PairSignal(
        stock_a_id=a.id,
        stock_b_id=b.id,
        sector="Information Technology",
        method="df",
        beta=1.05,
        alpha=2.0,
        half_life=8.2,
        df_tstat=-3.5,
        adf_pvalue=None,
        direction="long_spread",
        entry_z=-2.1,
        z_exit=0.0,
        z_stop=-3.5,
        spread_entry=Decimal("1.2345"),
        spread_sigma=Decimal("0.5000"),
        validity_until=datetime.now(tz=UTC) + timedelta(days=30),
    )
    db.add(sig)
    await db.commit()

    got = (await db.execute(select(PairSignal))).scalar_one()
    assert got.method == "df" and got.direction == "long_spread"
    assert got.is_shadow is True  # shadow default — never tradeable
    assert got.status == "open"  # lifecycle default
    assert got.beta == 1.05 and got.entry_z == -2.1
    assert got.spread_entry == Decimal("1.2345")
    assert got.resolved_at is None and got.outcome_r is None  # unresolved until the tracker
    assert got.stock_a_id == a.id and got.stock_b_id == b.id


async def test_pair_signal_adf_arm_carries_pvalue(db: AsyncSession) -> None:
    a = await make_stock(db, symbol="LEGC")
    b = await make_stock(db, symbol="LEGD")
    sig = PairSignal(
        stock_a_id=a.id,
        stock_b_id=b.id,
        sector="Healthcare",
        method="adf",
        beta=0.9,
        alpha=1.0,
        half_life=12.0,
        df_tstat=-4.0,
        adf_pvalue=0.012,
        direction="short_spread",
        entry_z=2.3,
        z_exit=0.0,
        z_stop=3.5,
        spread_entry=Decimal("0.5000"),
        spread_sigma=Decimal("0.2500"),
        validity_until=datetime.now(tz=UTC) + timedelta(days=30),
    )
    db.add(sig)
    await db.commit()
    got = (await db.execute(select(PairSignal))).scalar_one()
    assert got.method == "adf" and got.adf_pvalue == 0.012 and got.direction == "short_spread"
