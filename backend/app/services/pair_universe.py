"""Pair-trading universe screen (Phase 6.5a.2) — run the cointegration/mean-reversion
screen (`pair_screen`) over the real market universe and rank the candidate pairs.

Read-only, mints NOTHING (shadow-first; the frozen single-name engine is untouched).
The DB layer loads daily closes + sectors; the pure helpers (`align_closes`,
`rank_pairs`) do the alignment + ranking and are unit-testable without a DB.

Product decisions (autonomous 2026-08-14 — documented for later tuning, see
phase-06-6.5-pairtrading-plan.md):
  - **Universe = active Nifty50 with a sector tag.** Liquid names with good sector
    coverage; the short-leg (futures) exists for these when 6.5d tradeability arrives.
  - **Same-sector pairs only.** A prior against data-snooped false cointegration —
    screening all C(n,2) invites spurious hits (multiple testing). Economically-linked
    pairs are where cointegration has a real cause.
  - **Lookback ≈ 400 trading days.** Enough for a stable hedge ratio + DF stat, recent
    enough to matter. Tunable.
  - **Ranked by DF t-stat** (strongest stationarity first); gate = `pair_screen.is_candidate`.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import OhlcvDaily
from app.models.stock import Stock
from app.services import pair_screen as ps

_IST = ZoneInfo("Asia/Kolkata")

DEFAULT_LOOKBACK_TRADING_DAYS = 400


@dataclass(frozen=True)
class PairCandidate:
    """A same-sector pair whose spread screened as a tradeable mean-reversion candidate."""

    symbol_a: str
    symbol_b: str
    sector: str
    stat: ps.PairStat


def align_closes(
    a: dict[date, float],
    b: dict[date, float],
    *,
    min_common: int = ps.MIN_OBS,
) -> tuple[ps.FloatArray, ps.FloatArray] | None:
    """Inner-join two date→close maps on their common trading days (chronological), as
    aligned float arrays. None when fewer than `min_common` shared days — different
    listing dates / holiday gaps / T2T dark days must not misalign the two legs."""
    common = sorted(set(a) & set(b))
    if len(common) < min_common:
        return None
    aa = np.array([a[d] for d in common], dtype=np.float64)
    bb = np.array([b[d] for d in common], dtype=np.float64)
    return aa, bb


def rank_pairs(
    closes_by_symbol: dict[str, dict[date, float]],
    sector_of: dict[str, str | None],
    *,
    min_common: int = ps.MIN_OBS,
) -> list[PairCandidate]:
    """Screen every SAME-SECTOR pair and return the candidates, strongest stationarity
    (most-negative DF t-stat) first. Pure — no DB. A pair is kept only when its aligned
    spread passes `pair_screen.is_candidate` (significant DF stat + tradeable half-life)."""
    by_sector: dict[str, list[str]] = {}
    for sym, sec in sector_of.items():
        if sec and sym in closes_by_symbol:
            by_sector.setdefault(sec, []).append(sym)
    out: list[PairCandidate] = []
    for sec, syms in by_sector.items():
        for sym_a, sym_b in itertools.combinations(sorted(syms), 2):
            aligned = align_closes(
                closes_by_symbol[sym_a], closes_by_symbol[sym_b], min_common=min_common
            )
            if aligned is None:
                continue
            stat = ps.screen_pair(aligned[0], aligned[1])
            if stat is not None and ps.is_candidate(stat):
                out.append(PairCandidate(symbol_a=sym_a, symbol_b=sym_b, sector=sec, stat=stat))
    out.sort(key=lambda c: c.stat.df_tstat)
    return out


async def load_daily_closes(
    db: AsyncSession, stock_ids: list[int], since: datetime
) -> dict[int, dict[date, float]]:
    """IST-date → close (float) per stock, COMPLETE bars only, on/after `since`. Money
    is Decimal in the DB; converted to float here because the screen is indicator-class
    statistics (rules-allowed), not P&L."""
    if not stock_ids:
        return {}
    rows = (
        await db.execute(
            select(OhlcvDaily.stock_id, OhlcvDaily.time, OhlcvDaily.close)
            .where(
                OhlcvDaily.stock_id.in_(stock_ids),
                OhlcvDaily.is_complete.is_(True),
                OhlcvDaily.time >= since,
            )
            .order_by(OhlcvDaily.time)
        )
    ).all()
    out: dict[int, dict[date, float]] = {}
    for sid, ts, close in rows:
        out.setdefault(sid, {})[ts.astimezone(_IST).date()] = float(close)
    return out


async def screen_universe(
    db: AsyncSession,
    *,
    lookback_trading_days: int = DEFAULT_LOOKBACK_TRADING_DAYS,
    min_common: int = ps.MIN_OBS,
    now: datetime | None = None,
) -> list[PairCandidate]:
    """Screen same-sector pairs across the active, sector-tagged Nifty50 over the last
    `lookback_trading_days`. Read-only; returns ranked `PairCandidate`s. `now` is
    injectable for deterministic tests (no hidden clock)."""
    now = now or datetime.now(tz=UTC)
    stocks = (
        await db.execute(
            select(Stock.id, Stock.symbol, Stock.sector).where(
                Stock.is_active.is_(True),
                Stock.is_nifty50.is_(True),
                Stock.sector.is_not(None),
            )
        )
    ).all()
    if not stocks:
        return []
    id_to_sym = {sid: sym for sid, sym, _sec in stocks}
    sector_of: dict[str, str | None] = {sym: sec for _sid, sym, sec in stocks}
    # ~1.6 calendar days per trading day (weekends+holidays) — a generous window so the
    # requested trading-day depth is available.
    since = now - timedelta(days=int(lookback_trading_days * 1.6))
    closes_by_id = await load_daily_closes(db, list(id_to_sym), since)
    closes_by_symbol = {id_to_sym[sid]: series for sid, series in closes_by_id.items()}
    return rank_pairs(closes_by_symbol, sector_of, min_common=min_common)


def render_markdown(candidates: list[PairCandidate], *, day: date) -> str:
    """A dated report of the screened candidate pairs (read-only research artifact)."""
    out = [
        f"# Pair-trading candidates (same-sector, Nifty50) — {day}",
        "",
        "_Read-only screen (`pair_screen` + `pair_universe`). Same-sector pairs whose spread "
        "is a statistically-significant, tradeable-horizon mean-reversion candidate. Mints NO "
        "signal — 6.5a research only. Gate: DF t-stat ≤ −2.86 (5% CV) AND half-life ∈ "
        f"[{ps.MIN_HALF_LIFE:.0f}, {ps.MAX_HALF_LIFE:.0f}] bars. Ranked by DF t-stat._",
        "",
        "| # | pair | sector | β | half-life | DF t-stat | VR(2) | z now | n |",
        "|--:|---|---|--:|--:|--:|--:|--:|--:|",
    ]
    if not candidates:
        out.append("| — | (no candidates) | — | — | — | — | — | — | — |")
    for i, c in enumerate(candidates, 1):
        s = c.stat
        out.append(
            f"| {i} | {c.symbol_a}–{c.symbol_b} | {c.sector} | {s.beta:.3f} | "
            f"{s.half_life:.1f} | {s.df_tstat:.2f} | {s.variance_ratio:.3f} | "
            f"{s.zscore:+.2f} | {s.n} |"
        )
    out.append("")
    return "\n".join(out) + "\n"
