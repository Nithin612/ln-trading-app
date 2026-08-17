"""Order-book depth capture — Phase 6.8.1.

The tick consumer already subscribes ``KiteTicker.MODE_FULL``, so every tick
carries 5-level market depth that today is discarded. This module extracts the
TOP OF BOOK (best bid/ask + sizes) and caches it in Redis under
``depth:{stock_id}`` with a short TTL, mirroring the ``ltp:{stock_id}`` contract
in ``tick_consumer``.

PROVISIONAL, live-only data — the same discipline as the forming/tick layer:
  - It is NEVER written to a candle table and NEVER enters a backtest or P&L
    (the no-look-ahead invariant, trading-domain rule 3). It exists to make
    LIVE paper fills honest (spread-aware slippage, 6.8.2) and to feed liquidity
    gates — nothing that is replayed, backtested, or scored.
  - Best-effort: a malformed, one-sided, or crossed book yields ``None``, never
    an error, so depth capture can never cost the consumer an LTP or a candle.

Redis contract (import ``DEPTH_KEY`` from here — never retype the pattern):
  KEY  ``depth:{stock_id}`` → JSON ``{stock_id, instrument_token, bid, ask,
  bid_qty, ask_qty, ts}``; prices are Decimal-parseable strings; TTL 60 s.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

# Redis KEY holding the latest top-of-book per stock. paper_broker (6.8.2) reads
# this exact key via get_live_depth — import DEPTH_KEY from here, never retype.
DEPTH_KEY = "depth:{stock_id}"
DEPTH_KEY_TTL_SECONDS = 60  # top-of-book goes stale fast; fail open to flat bps


@dataclass(frozen=True)
class Depth:
    """Top of the order book. Prices are Decimal (money); sizes are int."""

    bid: Decimal
    ask: Decimal
    bid_qty: int
    ask_qty: int

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal(2)

    @property
    def spread_bps(self) -> float:
        """Relative spread in basis points — the liquidity metric. A ratio, so
        float is fine (money rules); 0.0 when the mid is unusable."""
        mid = self.mid
        if mid <= 0:
            return 0.0
        return float(self.spread / mid) * 10_000.0


def extract_top_of_book(tick: Mapping[str, Any]) -> Depth | None:
    """Best bid/ask from a Kite MODE_FULL tick. ``None`` when the tick carries
    no usable two-sided book: not full mode, pre-open one-sided, empty (0-price)
    levels, or a crossed-book (ask < bid) data glitch — none of which is a
    tradeable book, so all fail open."""
    depth = tick.get("depth")
    if not isinstance(depth, Mapping):
        return None
    buy = depth.get("buy")
    sell = depth.get("sell")
    # Both sides must be non-empty sequences before we index [0]. A truthy but
    # non-list value (a dict → KeyError: 0, an int → TypeError) would otherwise
    # raise, breaking the "never raises" contract this function promises.
    if not isinstance(buy, (list, tuple)) or not isinstance(sell, (list, tuple)):
        return None
    if not buy or not sell:
        return None
    top_buy = buy[0]
    top_sell = sell[0]
    if not isinstance(top_buy, Mapping) or not isinstance(top_sell, Mapping):
        return None
    try:
        bid = Decimal(str(top_buy["price"]))
        ask = Decimal(str(top_sell["price"]))
        bid_qty = int(top_buy.get("quantity") or 0)
        ask_qty = int(top_sell.get("quantity") or 0)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    # Kite fills empty depth levels with a 0 price; a crossed book (ask < bid)
    # is a transient feed glitch. A locked book (ask == bid, spread 0) is legal.
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    return Depth(bid=bid, ask=ask, bid_qty=bid_qty, ask_qty=ask_qty)


def serialize_depth(
    stock_id: int, instrument_token: int, depth: Depth, ts: str
) -> str:
    """JSON envelope for the Redis value. Prices as strings → Decimal-exact on
    read-back (never float for money)."""
    return json.dumps(
        {
            "stock_id": stock_id,
            "instrument_token": instrument_token,
            "bid": str(depth.bid),
            "ask": str(depth.ask),
            "bid_qty": depth.bid_qty,
            "ask_qty": depth.ask_qty,
            "ts": ts,
        }
    )


def parse_depth(raw: str | None) -> Depth | None:
    """Parse a stored depth value back to a ``Depth``. ``None`` on any
    corruption — a bad cache entry must never raise into a caller (fail open)."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return Depth(
            bid=Decimal(str(data["bid"])),
            ask=Decimal(str(data["ask"])),
            bid_qty=int(data["bid_qty"]),
            ask_qty=int(data["ask_qty"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, InvalidOperation):
        return None


async def write_depth(
    redis: Any,
    stock_id: int,
    instrument_token: int,
    depth: Depth,
    *,
    ts: str,
) -> None:
    """SET ``depth:{stock_id}`` with a TTL. Takes the caller's Redis client (the
    tick consumer's shared connection) — never open a connection per tick."""
    await redis.set(
        DEPTH_KEY.format(stock_id=stock_id),
        serialize_depth(stock_id, instrument_token, depth, ts),
        ex=DEPTH_KEY_TTL_SECONDS,
    )


async def get_live_depth(stock_id: int) -> Depth | None:
    """Latest LIVE top-of-book from Redis (no fallback). ``None`` means no fresh
    book — market closed, the stock isn't trading, or depth capture is off (the
    key has a 60 s TTL). Mirrors ``paper_broker.get_live_ltp``; consumed by the
    fill model in 6.8.2."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            raw: str | None = await r.get(DEPTH_KEY.format(stock_id=stock_id))
        finally:
            # aclose in finally — a raised GET must not leak the connection.
            with contextlib.suppress(Exception):
                await r.aclose()
        return parse_depth(raw)
    except Exception:
        return None
