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

**Post-close extension (DA-7, 2026-09-30).** `capture_postclose` polls the same universe over
15:44–16:05 IST and upserts `cas_postclose_daily`. SEBI's CAS circular (clause 4.2.4) runs a
post-close session 15:50–16:00 at the closing price, and Zerodha accepts CNC market orders in it.
So a buy at the official close is possible *after* the auction print is known, if a seller is
there. This records whether one was: the volume just after the auction (frozen on the first poll,
like `pre_auction_price`), the peak pending buy and sell quantity during the session, and the
volume after it. It uses only DOCUMENTED /quote fields (`volume`, `buy_quantity`, `sell_quantity`,
`last_price`), and never touches `cas_daily`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import CasDaily, CasPostCloseDaily

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
    `pre_auction_price` and `first_polled_at` (when it was observed) are set only on the first
    insert and preserved thereafter; the other fields update to the latest poll so the row
    converges to the final auction print. `captured_at` is the LAST poll's time."""
    symbols = list(symbol_stock_map)
    written = 0
    for i in range(0, len(symbols), QUOTE_BATCH):
        batch = symbols[i : i + QUOTE_BATCH]
        try:
            quotes = await kite.quote(batch)
        except Exception:
            log.exception("CAS capture quote() failed for a batch of %d", len(batch))
            continue
        observed = _now()  # the quote's arrival — frozen into first_polled_at on insert
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
                    "first_polled_at": observed,  # frozen on insert, with pre_auction_price
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
                # pre_auction_price and first_polled_at intentionally omitted → both keep the
                # first (pre-auction) capture.
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


@dataclass(frozen=True)
class ParsedPostClose:
    last_price: Decimal
    volume: int | None
    buy_quantity: int | None
    sell_quantity: int | None


_BIGINT_MAX = 9_223_372_036_854_775_807


def _nonneg_int(v: object) -> int | None:
    """A cumulative volume or a pending quantity: a non-negative integer that fits the BIGINT
    column, else None. A negative, malformed, non-finite or out-of-range value is unusable rather
    than clamped — a clamp would invent a number. (bug-hunter: `inf` used to raise OverflowError
    out of the parser and lose the whole minute; `1e30` passed the parse and failed the INSERT.)"""
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    n = int(d)
    return n if 0 <= n <= _BIGINT_MAX else None


def _now() -> datetime:
    """The observation clock — a module seam so tests can pin the instant a quote is seen."""
    return datetime.now(UTC)


def parse_postclose(quote: dict[str, Any] | None) -> ParsedPostClose | None:
    """Pull the post-close fields from one /quote row. None when there is no usable last price (a
    quote we can't anchor), exactly as `parse_cas`. The volume and quantity fields are DOCUMENTED
    /quote fields, unlike the CAS auction fields."""
    if not isinstance(quote, dict):
        return None
    last = _dec(quote.get("last_price"))
    if last is None:
        return None
    return ParsedPostClose(
        last_price=last,
        volume=_nonneg_int(quote.get("volume")),
        buy_quantity=_nonneg_int(quote.get("buy_quantity")),
        sell_quantity=_nonneg_int(quote.get("sell_quantity")),
    )


async def capture_postclose(
    db: AsyncSession,
    kite: Any,
    symbol_stock_map: dict[str, int],
    *,
    trade_date: date,
    in_session_at: Callable[[datetime], bool],
) -> int:
    """Poll /quote for every symbol and upsert into `cas_postclose_daily`. Returns rows written.

    ⭐ Every timestamp and the in-session decision are taken when the quote ARRIVES, not when the
    task started (bug-hunter LOW-5): `ThrottledKite` can spend seconds in backoff, so a 15:59 poll
    could otherwise record post-16:00 quantities as in-session, and a 15:49 poll could stamp a
    pre-session `first_polled_at` on a baseline that already includes post-close trades.

    Best-effort per batch, fail open, exactly as `capture_cas`. The merge rules are the whole
    design:
      - `volume_after_auction` and `first_polled_at` are FROZEN on the first insert (the same
        pattern as `cas_daily.pre_auction_price`). A late first poll is detectable from
        `first_polled_at`; it is never silently repaired.
      - `volume_latest` keeps the last NON-NULL volume, so a quote that omits it cannot erase
        what earlier polls saw; `volume_latest_at` keeps WHEN that volume was seen (unlike
        `captured_at`, which every poll advances).
      - `max_buy_qty` / `max_sell_qty` take the peak over polls INSIDE the post-close session
        (`in_session`); polls outside it contribute NULL, which GREATEST ignores.
    """
    symbols = list(symbol_stock_map)
    written = 0
    for i in range(0, len(symbols), QUOTE_BATCH):
        batch = symbols[i : i + QUOTE_BATCH]
        try:
            quotes = await kite.quote(batch)
        except Exception:
            log.exception("post-close capture quote() failed for a batch of %d", len(batch))
            continue
        observed = _now()
        in_session = in_session_at(observed)
        rows: list[dict[str, object]] = []
        for sym in batch:
            p = parse_postclose(quotes.get(sym))
            if p is None:
                continue
            rows.append(
                {
                    "stock_id": symbol_stock_map[sym],
                    "trade_date": trade_date,
                    "volume_after_auction": p.volume,  # frozen on insert (see set_ below)
                    "first_polled_at": observed,  # frozen on insert
                    "volume_latest": p.volume,
                    # dated only when this poll actually saw a volume (kept with it below)
                    "volume_latest_at": observed if p.volume is not None else None,
                    "last_price_latest": p.last_price,
                    "max_buy_qty": p.buy_quantity if in_session else None,
                    "max_sell_qty": p.sell_quantity if in_session else None,
                    "polls": 1,
                    "captured_at": observed,
                }
            )
        if not rows:
            continue
        stmt = pg_insert(CasPostCloseDaily).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trade_date"],
            set_={
                # volume_after_auction and first_polled_at intentionally omitted → frozen.
                "volume_latest": func.coalesce(
                    stmt.excluded.volume_latest, CasPostCloseDaily.volume_latest
                ),
                "volume_latest_at": func.coalesce(
                    stmt.excluded.volume_latest_at, CasPostCloseDaily.volume_latest_at
                ),
                "last_price_latest": stmt.excluded.last_price_latest,
                "max_buy_qty": func.greatest(
                    CasPostCloseDaily.max_buy_qty, stmt.excluded.max_buy_qty
                ),
                "max_sell_qty": func.greatest(
                    CasPostCloseDaily.max_sell_qty, stmt.excluded.max_sell_qty
                ),
                "polls": CasPostCloseDaily.polls + 1,
                "captured_at": stmt.excluded.captured_at,  # the observation instant, not now()
            },
        )
        await db.execute(stmt)
        written += len(rows)
    await db.commit()
    return written
