"""Circuit-band capture — Phase 6.8.3.

NSE/BSE apply daily price bands (2/5/10/20%): a stock cannot trade below its
``lower_circuit_limit`` or above its ``upper_circuit_limit``. When a name is
pinned AT a band there is no counterparty on that side — a long into the lower
circuit cannot be stopped out at any price. The circuit-eligibility overlay
(``app/signals/circuit_guard.py``) uses these bands to skip entering a name
already sitting near its adverse band.

Bands are NOT on the ``MODE_FULL`` tick wire — they come from Kite ``quote()``
(`lower/upper_circuit_limit`). The ``refresh_circuit_bands`` task fetches them in
one batched call and caches them here; the order path only READS the cache.

PROVISIONAL, live-only data — same discipline as depth (6.8.1): NEVER written to
a candle, NEVER entered into a backtest or P&L. Best-effort throughout: a
malformed quote or a bad cache entry yields ``None``, never an error, so the gate
FAILS OPEN (a missing band never blocks an otherwise-valid signal).

Redis contract (import ``CIRCUIT_KEY`` from here — never retype the pattern):
  KEY  ``circuit:{stock_id}`` → JSON ``{stock_id, lower, upper, ts}``; prices are
  Decimal-parseable strings; TTL ``settings.circuit_band_ttl_s``.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

# Redis KEY holding the latest circuit band per stock. The order path reads this
# exact key via get_circuit_band — import CIRCUIT_KEY from here, never retype.
CIRCUIT_KEY = "circuit:{stock_id}"

# Kite quote() accepts at most 500 instruments per call.
QUOTE_BATCH = 500


@dataclass(frozen=True)
class CircuitBand:
    """The day's price band. Both limits are Decimal (money)."""

    lower: Decimal
    upper: Decimal


def parse_quote_band(quote_row: Any) -> CircuitBand | None:
    """Extract the band from one Kite ``quote()`` row. ``None`` when the row has
    no usable two-sided band: absent limits, zero (no band applies — many
    indices/derivatives), or a crossed band (upper ≤ lower) data glitch. None of
    those is a tradeable band, so all fail open."""
    if not isinstance(quote_row, dict):
        return None
    try:
        lower = Decimal(str(quote_row.get("lower_circuit_limit")))
        upper = Decimal(str(quote_row.get("upper_circuit_limit")))
    except (TypeError, ValueError, InvalidOperation):
        return None
    if lower <= 0 or upper <= 0 or upper <= lower:
        return None
    return CircuitBand(lower=lower, upper=upper)


def serialize_band(stock_id: int, band: CircuitBand, ts: str) -> str:
    """JSON envelope for the Redis value. Limits as strings → Decimal-exact on
    read-back (never float for money)."""
    return json.dumps(
        {
            "stock_id": stock_id,
            "lower": str(band.lower),
            "upper": str(band.upper),
            "ts": ts,
        }
    )


def parse_band(raw: str | None) -> CircuitBand | None:
    """Parse a stored band value back to a ``CircuitBand``. ``None`` on any
    corruption — a bad cache entry must never raise into a caller (fail open)."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        band = CircuitBand(
            lower=Decimal(str(data["lower"])),
            upper=Decimal(str(data["upper"])),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if band.lower <= 0 or band.upper <= 0 or band.upper <= band.lower:
        return None
    return band


async def write_band(redis: Any, stock_id: int, band: CircuitBand, *, ts: str) -> None:
    """SET ``circuit:{stock_id}`` with a TTL. Takes the caller's Redis client
    (the refresh task's shared connection) — never open a connection per stock."""
    await redis.set(
        CIRCUIT_KEY.format(stock_id=stock_id),
        serialize_band(stock_id, band, ts),
        ex=settings.circuit_band_ttl_s,
    )


async def refresh_bands(
    redis: Any,
    kite: Any,
    token_stock_map: dict[int, int],
    *,
    ts: str,
) -> int:
    """Fetch bands for every instrument in ``token_stock_map`` (instrument_token →
    stock_id) via batched ``kite.quote()`` and cache them. Returns the number of
    bands written. Best-effort per batch: a failed or malformed quote logs and is
    skipped so one bad batch never aborts the rest (fail open)."""
    tokens = list(token_stock_map)
    written = 0
    for i in range(0, len(tokens), QUOTE_BATCH):
        batch = tokens[i : i + QUOTE_BATCH]
        try:
            quotes = await kite.quote(batch)
        except Exception:
            log.exception("circuit-band quote() failed for a batch of %d", len(batch))
            continue
        for token in batch:
            band = parse_quote_band(quotes.get(str(token)))
            if band is None:
                continue
            await write_band(redis, token_stock_map[token], band, ts=ts)
            written += 1
    return written


async def get_circuit_band_checked(stock_id: int) -> tuple[CircuitBand | None, bool]:
    """``(band, ok)`` — the band, and whether the READ ITSELF succeeded.

    ``(None, True)`` means "looked, there is no fresh band" (the refresh task hasn't run,
    the market is closed, bands are disabled — the key has a TTL). ``(None, False)`` means
    the read FAILED (Redis down, parse error).

    The distinction exists because the two are opposite answers for eligibility: a missing
    band is a normal fail-open, while a failed read means an ACTIVE circuit gate could not
    be judged at all and must be reported as unassessed rather than silently clear
    (bug-hunter, 2026-09-05 — an infra fault was being recorded as a data-coverage gap and
    then counted as evidence by the shadow sidecar)."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            raw: str | None = await r.get(CIRCUIT_KEY.format(stock_id=stock_id))
        finally:
            # aclose in finally — a raised GET must not leak the connection.
            with contextlib.suppress(Exception):
                await r.aclose()
        return parse_band(raw), True
    except Exception:
        return None, False


async def get_circuit_band(stock_id: int) -> CircuitBand | None:
    """Latest cached band from Redis (no fallback), conflating "no band" with "read
    failed". Prefer `get_circuit_band_checked` on any path that must distinguish them."""
    band, _ok = await get_circuit_band_checked(stock_id)
    return band
