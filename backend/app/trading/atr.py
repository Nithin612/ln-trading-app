"""ATR from stored candles — for the Layered Ratchet Stop's chandelier layer.

Computed in the trading layer (NOT the frozen analysis engine): we only READ
candles here, never recompute signals. This is the Wilder-seed ATR — the
simple mean of the True Range over the last `period` completed candles — which
is a fine current-volatility estimate for the shadow comparator. It is not the
engine's indicator ATR and carries no parity obligation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Ohlcv1h, Ohlcv1m, Ohlcv5m, Ohlcv15m, OhlcvDaily

# Dynamic table dispatch: the five OHLCV models are column-identical, so the
# selected model is typed Any (mypy can't resolve shared columns off a dict of
# heterogeneous mapped classes).
_TF_MODEL: dict[str, Any] = {
    "1m": Ohlcv1m,
    "5m": Ohlcv5m,
    "15m": Ohlcv15m,
    "1h": Ohlcv1h,
    "1d": OhlcvDaily,
}


def atr_timeframe_for(classification: str | None) -> str:
    """Volatility timeframe matched to the trade's horizon: intraday styles use
    5-minute bars, multi-day styles use daily bars."""
    if classification in ("scalp", "intraday"):
        return "5m"
    return "1d"


async def latest_atr(
    db: AsyncSession,
    stock_id: int,
    timeframe: str = "1d",
    period: int = 14,
    *,
    before: datetime | None = None,
) -> Decimal | None:
    """Wilder-seed ATR over the last `period` completed candles at or before
    `before` (default: the latest). Returns None if there aren't enough bars."""
    model = _TF_MODEL.get(timeframe)
    if model is None:
        return None

    stmt = select(model.high, model.low, model.close).where(
        model.stock_id == stock_id,
        model.is_complete.is_(True),
    )
    if before is not None:
        stmt = stmt.where(model.time <= before)
    stmt = stmt.order_by(model.time.desc()).limit(period + 1)

    rows = (await db.execute(stmt)).all()
    if len(rows) < period + 1:
        return None

    rows = list(reversed(rows))  # ascending, so prev_close precedes each bar
    prev_close = Decimal(str(rows[0].close))
    total = Decimal(0)
    for r in rows[1:]:
        high, low, close = Decimal(str(r.high)), Decimal(str(r.low)), Decimal(str(r.close))
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        total += tr
        prev_close = close
    return total / Decimal(period)
