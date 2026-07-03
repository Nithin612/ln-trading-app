"""Zerodha KiteConnect client wrapper.

Responsibilities:
- Build the Kite login URL (step 1 of OAuth)
- Exchange request_token for access_token (step 2)
- Persist/revoke BrokerToken rows in the DB
- Expose a ready-to-use KiteConnect instance for REST calls (historical data, orders)
- Download and upsert the instruments CSV into kite_instruments
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from kiteconnect import KiteConnect
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.broker import BrokerToken, KiteInstrument

log = logging.getLogger(__name__)

# Kite tokens expire at 6 AM IST the next day.
# Store that offset (UTC equivalent of 6 AM IST = 0:30 UTC).
_TOKEN_EXPIRY_HOUR_UTC = 0
_TOKEN_EXPIRY_MINUTE_UTC = 30


def _next_expiry() -> datetime:
    """Return UTC datetime for 6 AM IST tomorrow."""
    now_utc = datetime.now(UTC)
    expiry = now_utc.replace(
        hour=_TOKEN_EXPIRY_HOUR_UTC,
        minute=_TOKEN_EXPIRY_MINUTE_UTC,
        second=0,
        microsecond=0,
    )
    if expiry <= now_utc:
        expiry += timedelta(days=1)
    return expiry


def get_login_url() -> str:
    """Return the Zerodha login redirect URL for step 1 of OAuth."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    return str(kc.login_url())


async def exchange_token(
    db: AsyncSession,
    user_id: int,
    request_token: str,
) -> BrokerToken:
    """Exchange request_token for access_token, persist, and return the BrokerToken row."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    data: dict[str, Any] = kc.generate_session(
        request_token, api_secret=settings.kite_api_secret
    )
    access_token: str = data["access_token"]

    # Invalidate any existing active tokens for this user
    await db.execute(
        update(BrokerToken)
        .where(BrokerToken.user_id == user_id, BrokerToken.is_active.is_(True))
        .values(is_active=False)
    )

    token = BrokerToken(
        user_id=user_id,
        broker="kite",
        access_token=access_token,
        request_token=request_token,
        expires_at=_next_expiry(),
        is_active=True,
    )
    db.add(token)
    await db.flush()
    await db.refresh(token)
    log.info("Kite access_token stored for user_id=%d expires=%s", user_id, token.expires_at)
    return token


async def get_active_token(db: AsyncSession, user_id: int) -> BrokerToken | None:
    """Return the current active, non-expired BrokerToken for this user, or None."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(BrokerToken)
        .where(
            BrokerToken.user_id == user_id,
            BrokerToken.is_active.is_(True),
            BrokerToken.expires_at > now,
        )
        .order_by(BrokerToken.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def build_kite(access_token: str) -> KiteConnect:
    """Return a KiteConnect instance ready for REST API calls."""
    kc = KiteConnect(api_key=settings.kite_api_key)
    kc.set_access_token(access_token)
    return kc


def map_instrument_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter + normalize raw Kite instrument rows for kite_instruments.

    Kept: NSE/BSE cash instruments AND the NFO derivatives segment (futures +
    options, with strike) — the option-chain recorder selects instruments
    from these rows locally instead of hitting Kite per request.
    """
    records: list[dict[str, Any]] = []
    for r in rows:
        exchange = str(r.get("exchange", ""))
        instrument_type = str(r.get("instrument_type", ""))
        if exchange not in ("NSE", "BSE", "NFO"):
            continue
        try:
            records.append(
                {
                    "instrument_token": int(r["instrument_token"]),
                    "exchange_token": int(r["exchange_token"]),
                    "tradingsymbol": str(r["tradingsymbol"]),
                    "exchange": exchange,
                    "instrument_type": instrument_type,
                    "name": str(r.get("name", "")),
                    "last_price": float(r.get("last_price", 0) or 0),
                    "tick_size": float(r.get("tick_size", 0.05) or 0.05),
                    "lot_size": int(r.get("lot_size", 1) or 1),
                    "segment": str(r.get("segment", "")),
                    "expiry": str(r.get("expiry", "") or ""),
                    "strike": Decimal(str(r.get("strike", 0) or 0)),
                    "synced_at": datetime.now(UTC),
                }
            )
        except (KeyError, ValueError):
            continue  # skip malformed rows
    return records


async def sync_instruments(db: AsyncSession, access_token: str) -> int:
    """Download instruments CSV from Kite and upsert into kite_instruments.

    Returns the number of rows upserted.
    """
    kc = build_kite(access_token)

    # kiteconnect returns raw CSV bytes from instruments()
    raw: bytes | str = kc.instruments()
    if isinstance(raw, (list, dict)):
        # Newer SDK versions return parsed list
        rows = raw
    else:
        reader = csv.DictReader(io.StringIO(raw if isinstance(raw, str) else raw.decode()))
        rows = list(reader)

    if not rows:
        log.warning("Kite instruments response was empty")
        return 0

    records = map_instrument_rows(rows)
    if not records:
        return 0

    # Chunked upsert: with NFO included this is ~80k rows — a single VALUES
    # clause would exceed asyncpg's bind-parameter limit.
    chunk = 2000
    for i in range(0, len(records), chunk):
        stmt = pg_insert(KiteInstrument).values(records[i : i + chunk])
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_token"],
            set_={
                "last_price": stmt.excluded.last_price,
                "synced_at": stmt.excluded.synced_at,
                "tradingsymbol": stmt.excluded.tradingsymbol,
                "name": stmt.excluded.name,
                "expiry": stmt.excluded.expiry,
                "strike": stmt.excluded.strike,
            },
        )
        await db.execute(stmt)
    log.info("Kite instruments synced: %d rows", len(records))
    return len(records)


async def fetch_historical(
    access_token: str,
    instrument_token: int,
    interval: str,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict[str, Any]]:
    """Fetch OHLCV candles from Kite REST for gap-fill.

    interval: "minute" | "5minute" | "15minute" | "60minute" | "day"
    Returns list of dicts with keys: date, open, high, low, close, volume.
    """
    kc = build_kite(access_token)
    # Run in a thread because kiteconnect is sync
    import asyncio
    data = await asyncio.to_thread(
        lambda: kc.historical_data(
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval=interval,
            continuous=False,
        ),
    )
    return cast("list[dict[str, Any]]", data)
