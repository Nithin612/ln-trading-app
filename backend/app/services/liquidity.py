"""Liquidity context provider for the liquidity overlay (MCE slice 5a).

Supplies a stock's recent daily traded values (₹ = close × volume) from `ohlcv_1d`, most-
recent last, anchored to the signal's decision time (no look-ahead — same `time <= :as_of`
contract as the RS provider). The pure overlay (`app/signals/liquidity_guard.py`) takes the
median and compares it to the floor.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Completed daily bars only, most-recent first (reversed to chronological below). `{as_of}`
# is either empty or the fixed literal `AND time <= :as_of` (value bound). Fixed table name
# (python rules: no caller-supplied identifiers).
_TRADED_VALUE_SQL = """
    SELECT close, volume
    FROM ohlcv_1d
    WHERE stock_id = :stock_id
      AND is_complete = true
      {as_of}
    ORDER BY (time AT TIME ZONE 'UTC')::date DESC
    LIMIT :n
"""


async def load_traded_values(
    db: AsyncSession, stock_id: int, *, lookback: int = 20, as_of: datetime | None = None
) -> list[Decimal]:
    """The stock's last `lookback` daily traded values (₹ = close × volume), chronological,
    up to `as_of` (the signal's `created_at`). Empty when the stock is unknown or has no
    completed bars — the overlay then fails open on 'fewer than lookback sessions'."""
    params: dict[str, object] = {"stock_id": stock_id, "n": lookback}
    as_of_clause = ""
    if as_of is not None:
        as_of_clause = "AND time <= :as_of"
        params["as_of"] = as_of
    rows = (await db.execute(text(_TRADED_VALUE_SQL.format(as_of=as_of_clause)), params)).all()
    # DESC → chronological; close is Numeric→Decimal, volume is an int.
    return [Decimal(str(r.close)) * Decimal(r.volume) for r in reversed(rows)]
