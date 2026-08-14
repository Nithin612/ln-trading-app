"""Pair-universe screen (Phase 6.5a.2) — same-sector pair discovery over real bars.

Pure helpers (align_closes, rank_pairs) tested without a DB; screen_universe tested
end-to-end against a planted cointegrated pair. Randomness seeded (reproducible)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
from app.models.market_data import OhlcvDaily
from app.services import pair_universe as pu
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

SEED = 20260814


def _ar1(rng: np.random.Generator, phi: float, n: int, sigma: float) -> np.ndarray:
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = phi * s[t - 1] + rng.normal(0.0, sigma)
    return s


def _coint(rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Two series sharing a dominant stochastic trend + independent stationary noise →
    cointegrated (a−b is stationary)."""
    common = np.cumsum(rng.normal(0.0, 1.0, n))
    a = 100.0 + common + _ar1(rng, 0.9, n, 0.5)
    b = 50.0 + common + _ar1(rng, 0.9, n, 0.5)
    return a, b


def _weekdays(start: date, n: int) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


# --------------------------------------------------------------------------- #
# align_closes                                                                #
# --------------------------------------------------------------------------- #


def test_align_closes_inner_joins_common_days() -> None:
    days = _weekdays(date(2025, 1, 6), 100)
    a = {d: float(i) for i, d in enumerate(days)}
    b = {d: float(i * 2) for i, d in enumerate(days[10:])}  # b starts 10 days later
    aligned = pu.align_closes(a, b, min_common=60)
    assert aligned is not None
    assert aligned[0].shape == aligned[1].shape == (90,)


def test_align_closes_none_when_too_few_common() -> None:
    days = _weekdays(date(2025, 1, 6), 5)
    a = {d: 1.0 for d in days}
    assert pu.align_closes(a, a, min_common=60) is None


# --------------------------------------------------------------------------- #
# rank_pairs (pure)                                                           #
# --------------------------------------------------------------------------- #


def test_rank_pairs_finds_cointegrated_same_sector_pair() -> None:
    rng = np.random.default_rng(SEED)
    n = 200
    days = _weekdays(date(2025, 1, 6), n)
    a, b = _coint(rng, n)
    c = np.cumsum(rng.normal(0.0, 1.0, n)) + 50.0  # independent random walk
    closes = {
        "AAA": dict(zip(days, a, strict=True)),
        "BBB": dict(zip(days, b, strict=True)),
        "CCC": dict(zip(days, c, strict=True)),
    }
    sectors: dict[str, str | None] = {"AAA": "IT", "BBB": "IT", "CCC": "IT"}
    cands = pu.rank_pairs(closes, sectors)
    pairs = {(x.symbol_a, x.symbol_b) for x in cands}
    assert ("AAA", "BBB") in pairs
    # the independent RW does not cointegrate with either leg
    assert ("AAA", "CCC") not in pairs and ("BBB", "CCC") not in pairs


def test_rank_pairs_excludes_cross_sector() -> None:
    rng = np.random.default_rng(SEED)
    n = 200
    days = _weekdays(date(2025, 1, 6), n)
    a, b = _coint(rng, n)
    closes = {"AAA": dict(zip(days, a, strict=True)), "BBB": dict(zip(days, b, strict=True))}
    # a cointegrated pair, but the legs are in DIFFERENT sectors → never screened
    assert pu.rank_pairs(closes, {"AAA": "IT", "BBB": "BANK"}) == []


def test_rank_pairs_skips_untagged_sector() -> None:
    rng = np.random.default_rng(SEED)
    n = 200
    days = _weekdays(date(2025, 1, 6), n)
    a, b = _coint(rng, n)
    closes = {"AAA": dict(zip(days, a, strict=True)), "BBB": dict(zip(days, b, strict=True))}
    assert pu.rank_pairs(closes, {"AAA": None, "BBB": None}) == []


# --------------------------------------------------------------------------- #
# screen_universe (DB)                                                        #
# --------------------------------------------------------------------------- #


async def _insert_daily(
    db: AsyncSession, stock_id: int, closes: np.ndarray, days: list[date]
) -> None:
    for d, close in zip(days, closes, strict=True):
        px = Decimal(str(round(float(close), 4)))
        db.add(
            OhlcvDaily(
                stock_id=stock_id,
                time=datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC),  # 15:30 IST
                open=px,
                high=px,
                low=px,
                close=px,
                volume=1000,
                is_complete=True,
            )
        )
    await db.flush()


async def test_screen_universe_finds_planted_pair(db: AsyncSession) -> None:
    rng = np.random.default_rng(SEED)
    n = 150
    days = _weekdays(date(2025, 1, 6), n)
    a, b = _coint(rng, n)
    s1 = await make_stock(db, symbol="PAIRA", sector="IT", is_nifty50=True)
    s2 = await make_stock(db, symbol="PAIRB", sector="IT", is_nifty50=True)
    # excluded: same sector but NOT nifty50, and a nifty50 with no sector tag
    await make_stock(db, symbol="PAIRX", sector="IT", is_nifty50=False)
    await make_stock(db, symbol="PAIRY", sector=None, is_nifty50=True)
    await _insert_daily(db, s1.id, a, days)
    await _insert_daily(db, s2.id, b, days)
    await db.commit()

    now = datetime(2025, 9, 1, tzinfo=UTC)  # after the bars; injected (no hidden clock)
    cands = await pu.screen_universe(db, now=now, lookback_trading_days=400)
    pairs = {(c.symbol_a, c.symbol_b) for c in cands}
    assert ("PAIRA", "PAIRB") in pairs
    found = next(c for c in cands if (c.symbol_a, c.symbol_b) == ("PAIRA", "PAIRB"))
    assert found.sector == "IT"
    assert found.stat.df_tstat < pu.ps.DF_CRIT_5PCT


async def test_screen_universe_empty_when_no_universe(db: AsyncSession) -> None:
    assert await pu.screen_universe(db, now=datetime(2025, 9, 1, tzinfo=UTC)) == []


# --------------------------------------------------------------------------- #
# render                                                                      #
# --------------------------------------------------------------------------- #


def test_render_markdown_empty_and_populated() -> None:
    assert "(no candidates)" in pu.render_markdown([], day=date(2026, 8, 14))
    stat = pu.ps.PairStat(
        alpha=0.0,
        beta=1.05,
        half_life=8.2,
        df_tstat=-4.1,
        variance_ratio=0.93,
        zscore=-2.3,
        n=180,
        spread_mean=0.0,
        spread_std=1.0,
    )
    md = pu.render_markdown(
        [pu.PairCandidate(symbol_a="AAA", symbol_b="BBB", sector="IT", stat=stat)],
        day=date(2026, 8, 14),
    )
    assert "AAA–BBB" in md and "-4.10" in md and "IT" in md
