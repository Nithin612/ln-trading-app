"""Liquidity context provider for the liquidity overlay (MCE slice 5a).

Supplies a stock's recent daily traded values (₹ = close × volume) from `ohlcv_1d`, most-
recent last, anchored to the signal's decision time (no look-ahead — same `time <= :as_of`
contract as the RS provider). The pure overlay (`app/signals/liquidity_guard.py`) takes the
median and compares it to the floor.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.signals.liquidity_guard import median_traded_value as _guard_median

log = logging.getLogger(__name__)

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


# Last `n` completed daily bars for MANY stocks in one round trip. The median is taken in
# PYTHON with Decimal, deliberately: Postgres `percentile_cont` returns double precision,
# and money through a float is exactly what `.claude/rules/trading-domain.md` forbids.
_BATCH_TRADED_VALUE_SQL = """
    WITH ranked AS (
        SELECT stock_id, close, volume,
               ROW_NUMBER() OVER (
                   PARTITION BY stock_id
                   ORDER BY (time AT TIME ZONE 'UTC')::date DESC
               ) AS rn
        FROM ohlcv_1d
        WHERE stock_id = ANY(:stock_ids)
          AND is_complete = true
          {as_of}
    )
    SELECT stock_id, close, volume FROM ranked WHERE rn <= :n
"""


# Re-exported from the PURE layer so there is exactly ONE definition. The claim that the
# gate and the fill model "cannot disagree" was previously just a comment — `liquidity_guard`
# kept its own private `_median` and never imported this one (quant-verifier).
median_traded_value = _guard_median


async def load_median_traded_values(
    db: AsyncSession,
    stock_ids: Sequence[int],
    *,
    lookback: int = 20,
    as_of: datetime | None = None,
) -> dict[int, Decimal]:
    """Median daily traded value (₹) per stock, over the last `lookback` completed sessions
    up to `as_of`. ONE round trip for the whole set.

    This is the denominator of the A37 volume-participation model: an order worth ₹1 lakh in
    a stock that trades ₹5 lakh a day is 20% of a session's volume and is not fillable at the
    quoted price. It is the same quantity the liquidity GATE thresholds on — deliberately, so
    the gate and the fill model cannot disagree about how liquid a name is.

    A stock with FEWER than `lookback` completed sessions is **absent** from the result, not
    zero: too little history is "unknown", and the caller fails open by charging no
    participation impact. Zero would mean infinite participation and reject everything.
    """
    ids = list({int(s) for s in stock_ids})
    if not ids or lookback <= 0:
        return {}
    params: dict[str, object] = {"stock_ids": ids, "n": lookback}
    as_of_clause = ""
    if as_of is not None:
        as_of_clause = "AND time <= :as_of"
        params["as_of"] = as_of
    rows = (
        await db.execute(text(_BATCH_TRADED_VALUE_SQL.format(as_of=as_of_clause)), params)
    ).all()
    by_stock: dict[int, list[Decimal]] = {}
    for r in rows:
        by_stock.setdefault(int(r.stock_id), []).append(Decimal(str(r.close)) * Decimal(r.volume))
    return {
        sid: median_traded_value(vals)
        for sid, vals in by_stock.items()
        if len(vals) >= lookback
    }


async def load_median_traded_values_safe(
    db: AsyncSession,
    stock_ids: Sequence[int],
    *,
    lookback: int = 20,
    as_of: datetime | None = None,
) -> dict[int, Decimal]:
    """`load_median_traded_values`, but a DB fault returns `{}` instead of raising.

    The ADV read prices fills and marks on the order path, and a liquidity lookup must
    never be the reason an order 500s — the sibling liquidity GATE has failed open in a
    savepoint since MCE 5a and this had no equivalent (quant-verifier). Empty means
    "unknown", and every consumer already treats a missing stock as *charge no
    participation*, so the degraded behaviour is exactly the pre-A37 fill model.

    The read runs in a SAVEPOINT so a failure rolls back only the nested block and leaves
    the session usable for the `place_paper_order` that follows.

    ⚠ Lives here, once, rather than as a `try/except` at each of the seven call sites: a
    fail-open repeated seven times is seven chances to forget it.
    """
    try:
        async with db.begin_nested():
            return await load_median_traded_values(
                db, stock_ids, lookback=lookback, as_of=as_of
            )
    except SQLAlchemyError:
        log.exception(
            "median-traded-value load failed; charging no participation impact for %s",
            list(stock_ids)[:10],
        )
        return {}

