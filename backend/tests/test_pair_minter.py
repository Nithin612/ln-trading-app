"""Pair-signal shadow minter (Phase 6.5b slice 2) — mints only currently-extreme pairs."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
from app.models.pair import PairSignal
from app.services.pair_minter import mint_pair_signals
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

SEED = 20260815


def _ar1(rng: np.random.Generator, phi: float, n: int, sigma: float) -> np.ndarray:
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = phi * s[t - 1] + rng.normal(0.0, sigma)
    return s


def _rwalk(rng: np.random.Generator, n: int) -> np.ndarray:
    return np.cumsum(rng.normal(0.0, 1.0, n))


def _weekdays(start: date, n: int) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _pair(
    rng: np.random.Generator, n: int, *, last_z: float | None
) -> tuple[np.ndarray, np.ndarray]:
    """Cointegrated a≈b+stationary spread. If last_z given, force the CURRENT spread to
    last_z·σ from its trailing mean (an entry extreme)."""
    b = 100.0 + _rwalk(rng, n)
    spread = _ar1(rng, 0.9, n, 1.0)
    if last_z is not None:
        tm = float(np.mean(spread[-21:-1]))
        ts = float(np.std(spread[-21:-1], ddof=1))
        spread[-1] = tm + last_z * ts
    return b + spread, b


async def _insert_daily(
    db: AsyncSession, stock_id: int, closes: np.ndarray, days: list[date]
) -> None:
    from app.models.market_data import OhlcvDaily

    for d, close in zip(days, closes, strict=True):
        px = Decimal(str(round(float(close), 4)))
        db.add(
            OhlcvDaily(
                stock_id=stock_id,
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),
                open=px,
                high=px,
                low=px,
                close=px,
                volume=1000,
                is_complete=True,
            )
        )
    await db.flush()


async def _seed_pair(db: AsyncSession, *, last_z: float | None) -> None:
    rng = np.random.default_rng(SEED)
    days = _weekdays(date(2025, 1, 6), 150)
    a, b = _pair(rng, 150, last_z=last_z)
    s1 = await make_stock(db, symbol="PMA", sector="IT", is_nifty50=True)
    s2 = await make_stock(db, symbol="PMB", sector="IT", is_nifty50=True)
    await _insert_daily(db, s1.id, a, days)  # PMA < PMB → symbol_a = PMA (the extreme leg)
    await _insert_daily(db, s2.id, b, days)
    await db.commit()


_NOW = datetime(2025, 9, 1, tzinfo=UTC)


async def test_mint_creates_long_spread_shadow_signal(db: AsyncSession) -> None:
    await _seed_pair(db, last_z=-3.0)  # current spread 3σ LOW → z ≤ −entry → long_spread
    minted = await mint_pair_signals(db, now=_NOW)
    assert len(minted) >= 1
    df_sig = (await db.execute(select(PairSignal).where(PairSignal.method == "df"))).scalar_one()
    assert df_sig.is_shadow is True and df_sig.status == "open"
    assert df_sig.direction == "long_spread"
    assert df_sig.entry_z <= -2.0
    assert df_sig.z_stop < 0  # signed stop for a long
    assert df_sig.spread_sigma > 0
    assert df_sig.adf_pvalue is None  # df arm carries no ADF p-value


async def test_mint_dedups_open_signals(db: AsyncSession) -> None:
    await _seed_pair(db, last_z=-3.0)
    first = await mint_pair_signals(db, now=_NOW)
    assert len(first) >= 1
    second = await mint_pair_signals(db, now=_NOW + timedelta(days=1))
    assert second == []  # the open pair signals block a re-mint
    rows = (await db.execute(select(PairSignal))).scalars().all()
    assert len(rows) == len(first)


async def test_mint_skips_pairs_not_at_an_extreme(db: AsyncSession) -> None:
    await _seed_pair(db, last_z=None)  # cointegrated but the current spread is not extreme
    minted = await mint_pair_signals(db, now=_NOW, entry_z=2.0)
    # nothing at |z| ≥ 2 right now → nothing minted (or at most the arms that happen to spike)
    assert all(abs(s.entry_z) >= 2.0 for s in minted)


async def test_mint_skips_pair_already_past_its_stop(db: AsyncSession) -> None:
    # current spread ~5σ low → |z| ≥ |z_stop|=3.5 → the signal would be born PAST its own stop,
    # so a favourable reversion up through −3.5 would book as a stop-loss. Must NOT mint.
    await _seed_pair(db, last_z=-5.0)
    minted = await mint_pair_signals(db, now=_NOW)
    assert minted == []
    assert (await db.execute(select(PairSignal))).scalars().first() is None
