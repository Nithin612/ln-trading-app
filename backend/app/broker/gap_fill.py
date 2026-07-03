"""Gap-fill logic for Kite WebSocket reconnections.

When the tick consumer reconnects after a disconnect it needs to backfill
the candles that were missed during the outage.  This module:
  1. Detects how far back we need to fill (last DB row → now)
  2. Fetches from Kite REST historical_data
  3. Upserts the candles into the appropriate ohlcv_* tables
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.candle_aggregator import TIMEFRAME_TABLE
from app.broker.kite_client import fetch_historical
from app.models.market_data import Ohlcv1h, Ohlcv1m, Ohlcv5m, Ohlcv15m

log = logging.getLogger(__name__)

# Kite interval strings for each timeframe
_TF_TO_KITE_INTERVAL: dict[str, str] = {
    "1m": "minute",
    "5m": "5minute",
    "15m": "15minute",
    "1h": "60minute",
}

_TF_TO_MODEL: dict[str, Any] = {
    "1m": Ohlcv1m,
    "5m": Ohlcv5m,
    "15m": Ohlcv15m,
    "1h": Ohlcv1h,
}


async def detect_and_fill_gaps(  # noqa: C901
    db: AsyncSession,
    access_token: str,
    instrument_token: int,
    stock_id: int,
    timeframes: list[str] | None = None,
) -> dict[str, int]:
    """Detect gaps for each timeframe and fill them from Kite REST.

    Returns dict of {timeframe: rows_inserted}.
    """
    if timeframes is None:
        timeframes = ["1m", "5m", "15m", "1h"]

    results: dict[str, int] = {}
    now = datetime.now(UTC)

    for tf in timeframes:
        table = TIMEFRAME_TABLE[tf]
        kite_interval = _TF_TO_KITE_INTERVAL[tf]

        # Find the latest complete candle for this stock+timeframe
        row = await db.execute(
            text(
                f"SELECT MAX(time) FROM {table}"  # noqa: S608
                " WHERE stock_id = :sid AND is_complete = true"
            ).bindparams(sid=stock_id)
        )
        last_time: datetime | None = row.scalar()

        if last_time is None:
            # No data at all — skip gap fill; let the tick consumer populate from here
            log.debug("No existing data for stock_id=%d tf=%s, skipping gap fill", stock_id, tf)
            results[tf] = 0
            continue

        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=UTC)

        gap_start = last_time + timedelta(minutes=1)
        if gap_start >= now:
            results[tf] = 0
            continue

        log.info(
            "Gap fill: stock_id=%d tf=%s from %s to %s",
            stock_id, tf, gap_start, now,
        )

        try:
            candles = await fetch_historical(
                access_token=access_token,
                instrument_token=instrument_token,
                interval=kite_interval,
                from_dt=gap_start,
                to_dt=now,
            )
        except Exception:
            log.exception("Kite historical_data failed for stock_id=%d tf=%s", stock_id, tf)
            results[tf] = 0
            continue

        if not candles:
            results[tf] = 0
            continue

        records = []
        for c in candles:
            dt = c["date"]
            if hasattr(dt, "astimezone"):
                dt = dt.astimezone(UTC)
            else:
                dt = datetime.fromisoformat(str(dt)).replace(tzinfo=UTC)
            records.append(
                {
                    "time": dt,
                    "stock_id": stock_id,
                    "open": Decimal(str(c["open"])),
                    "high": Decimal(str(c["high"])),
                    "low": Decimal(str(c["low"])),
                    "close": Decimal(str(c["close"])),
                    "volume": int(c["volume"]),
                    "is_complete": True,
                }
            )

        if records:
            model = _TF_TO_MODEL[tf]
            stmt = pg_insert(model).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["time", "stock_id"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "is_complete": stmt.excluded.is_complete,
                },
            )
            await db.execute(stmt)

        results[tf] = len(records)
        log.info("Gap fill done: stock_id=%d tf=%s rows=%d", stock_id, tf, len(records))

    return results
