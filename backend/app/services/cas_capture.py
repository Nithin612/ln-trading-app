"""CAS (Closing Auction Session) capture — Stage 1.

Polls Kite REST /quote for the F&O (Category-I) universe during 3:15–3:35 IST and upserts one
`cas_daily` row per (stock, trade_date): the pre-auction (3:15) price, the exchange reference price,
the evolving indicative close, the latest official/auction close, and the total imbalance quantity.
Read-only research feed — it NEVER gates, sizes, or trades.

Kite /quote carries these (non-documented) auction fields — verified live 2026-08-25:
`indicative_close_price`, `total_imbalance_qty`, `reference_limit_price`. The WebSocket MODE_FULL
struct has no imbalance field, so REST /quote is the only path (the same batched `kite.quote()` the
6.8.3 circuit-band cache uses). Idempotent: the market-hours task polls the window every ~1 min and
each poll UPSERTs — `pre_auction_price` is frozen on the first (pre-auction) capture; the rest
converge to the final auction values (last_price → the clearing price after execution ~15:29).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import CasDaily

log = logging.getLogger(__name__)
QUOTE_BATCH = 500  # Kite /quote accepts up to 500 instruments per call


@dataclass(frozen=True)
class ParsedCas:
    last_price: Decimal
    reference_price: Decimal | None
    indicative_close: Decimal | None
    total_imbalance_qty: int | None


def _dec(v: object) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def parse_cas(quote: dict[str, Any] | None) -> ParsedCas | None:
    """Pull the CAS fields from one /quote row. None when there is no usable last price (a quote we
    can't anchor). Missing auction fields (before the auction populates ~15:21) parse to None/0 —
    that's expected and preserved."""
    if not isinstance(quote, dict):
        return None
    last = _dec(quote.get("last_price"))
    if last is None:
        return None
    imb_raw = quote.get("total_imbalance_qty")
    try:
        imbalance = int(imb_raw) if imb_raw is not None else None
    except (TypeError, ValueError):
        imbalance = None
    return ParsedCas(
        last_price=last,
        reference_price=_dec(quote.get("reference_limit_price")),
        indicative_close=_dec(quote.get("indicative_close_price")),
        total_imbalance_qty=imbalance,
    )


async def capture_cas(
    db: AsyncSession,
    kite: Any,
    symbol_stock_map: dict[str, int],
    *,
    trade_date: date,
) -> int:
    """Poll /quote for every symbol (EXCHANGE:SYMBOL → stock_id) and upsert into `cas_daily`.
    Returns rows written. Best-effort per batch (a failed batch logs and is skipped — fail open).
    `pre_auction_price` is set only on the first insert and preserved thereafter; the other fields
    update to the latest poll so the row converges to the final auction print."""
    symbols = list(symbol_stock_map)
    written = 0
    for i in range(0, len(symbols), QUOTE_BATCH):
        batch = symbols[i : i + QUOTE_BATCH]
        try:
            quotes = await kite.quote(batch)
        except Exception:
            log.exception("CAS capture quote() failed for a batch of %d", len(batch))
            continue
        rows: list[dict[str, object]] = []
        for sym in batch:
            p = parse_cas(quotes.get(sym))
            if p is None:
                continue
            rows.append(
                {
                    "stock_id": symbol_stock_map[sym],
                    "trade_date": trade_date,
                    "pre_auction_price": p.last_price,  # frozen on insert (see set_ below)
                    "reference_price": p.reference_price,
                    "indicative_close": p.indicative_close,
                    "official_close": p.last_price,  # latest last → clearing price after ~15:29
                    "total_imbalance_qty": p.total_imbalance_qty,
                    "polls": 1,
                }
            )
        if not rows:
            continue
        stmt = pg_insert(CasDaily).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trade_date"],
            set_={
                # pre_auction_price intentionally omitted → keeps the first (pre-auction) capture.
                "reference_price": stmt.excluded.reference_price,
                "indicative_close": stmt.excluded.indicative_close,
                "official_close": stmt.excluded.official_close,
                # A MATCHED auction reports 0 residual imbalance; that post-execution 0 (the last
                # in-window poll, ~15:29) must NOT clobber the meaningful pre-execution imbalance —
                # the whole predictor the Stage-2 study needs. Keep the last NON-ZERO value
                # (imbalance is never exactly 0 mid-auction; 0 appears only post-match).
                "total_imbalance_qty": case(
                    (
                        func.coalesce(stmt.excluded.total_imbalance_qty, 0) != 0,
                        stmt.excluded.total_imbalance_qty,
                    ),
                    else_=CasDaily.total_imbalance_qty,
                ),
                "polls": CasDaily.polls + 1,
                "captured_at": func.now(),
            },
        )
        await db.execute(stmt)
        written += len(rows)
    await db.commit()
    return written
