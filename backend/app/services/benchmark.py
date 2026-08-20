"""Benchmark provider for the sector/index relative-strength overlay (MCE slice 2).

Bridges the index price store (`index_ohlcv_1d`) and the pure RS overlay
(`app/signals/sector_rs.py`). It:

  1. picks a stock's benchmark index — the most specific of the membership flags
     (Bank-Nifty member → NIFTY BANK, else Fin-Nifty member → NIFTY FINANCIAL
     SERVICES, else the broad market NIFTY 50); and
  2. returns the stock's and that benchmark's daily closes **aligned on common trading
     days**, most-recent `lookback + 1` sessions, chronological.

Alignment is enforced HERE (the slice-1 quant-verifier note): the two series are an
INNER JOIN on trade date over completed EOD bars, so `sector_rs.evaluate`'s positional
`[-1]`/`[-(lookback+1)]` compare the same sessions and cannot look ahead. Per-sector
index mapping (Nifty IT / Auto / …) is a documented follow-up — the data can accrue via
the `indices` registry now; slice 2 uses the membership flags only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Index, Stock

log = logging.getLogger(__name__)

# Broad-market fallback; the membership flags override it when set.
_MARKET = "NIFTY50"

# Aligned trailing closes for one stock vs one index, completed daily bars only,
# most-recent first (reversed to chronological in the provider). `{as_of}` is either
# empty or the literal `AND o.time <= :as_of` (a fixed clause, value bound) so the
# context is anchored to the signal's decision time — matching the entry-quality ATR
# anchoring, no look-ahead. Fixed table names (python rules: no caller-supplied
# identifiers).
_ALIGNED_SQL = """
    SELECT o.close AS stock_close, i.close AS bench_close
    FROM ohlcv_1d o
    JOIN index_ohlcv_1d i
      ON (o.time AT TIME ZONE 'UTC')::date = i.trade_date
    WHERE o.stock_id = :stock_id
      AND o.is_complete = true
      AND i.index_id = :index_id
      {as_of}
    ORDER BY (o.time AT TIME ZONE 'UTC')::date DESC
    LIMIT :n
"""


@dataclass(frozen=True)
class RsContext:
    """A stock's and its benchmark's date-aligned closes, chronological. The two lists
    are always equal length (inner join). `benchmark_symbol` is set even when there are
    no aligned bars, so the shadow report can say which index the stock was judged
    against."""

    benchmark_symbol: str
    stock_closes: list[Decimal]
    benchmark_closes: list[Decimal]


def benchmark_symbol_for(stock: Stock) -> str:
    """Most specific index for a stock, from its membership flags. Bank ⊃ Fin ⊃ market:
    a bank is usually in both Bank-Nifty and Fin-Nifty, and its sector benchmark is
    Bank-Nifty."""
    if stock.is_banknifty:
        return "BANKNIFTY"
    if stock.is_finnifty:
        return "FINNIFTY"
    return _MARKET


async def load_rs_context(
    db: AsyncSession, stock_id: int, *, lookback: int = 20, as_of: datetime | None = None
) -> RsContext | None:
    """Aligned closes for `stock_id` vs its benchmark over the last `lookback + 1`
    common sessions. When `as_of` is given (the signal's decision time), only bars up to
    that instant are considered — so the overlay judges the context available AT COMMIT,
    matching the entry-quality ATR anchoring; no look-ahead. Returns None only when the
    stock itself is unknown; a known stock with no aligned bars yet returns empty series
    (the overlay then fails open on 'series shorter than lookback + 1'). Never raises for
    missing data."""
    stock = await db.get(Stock, stock_id)
    if stock is None:
        return None
    symbol = benchmark_symbol_for(stock)

    index_id = (
        await db.execute(select(Index.id).where(Index.symbol == symbol))
    ).scalar_one_or_none()
    if index_id is None:
        # Registry gap (should not happen for the three membership indices) — fail open.
        log.warning("benchmark index %s not in the indices registry", symbol)
        return RsContext(benchmark_symbol=symbol, stock_closes=[], benchmark_closes=[])

    params: dict[str, object] = {"stock_id": stock_id, "index_id": index_id, "n": lookback + 1}
    as_of_clause = ""
    if as_of is not None:
        as_of_clause = "AND o.time <= :as_of"
        params["as_of"] = as_of
    rows = (await db.execute(text(_ALIGNED_SQL.format(as_of=as_of_clause)), params)).all()
    rows = list(reversed(rows))  # DESC → chronological
    return RsContext(
        benchmark_symbol=symbol,
        stock_closes=[Decimal(str(r.stock_close)) for r in rows],
        benchmark_closes=[Decimal(str(r.bench_close)) for r in rows],
    )
