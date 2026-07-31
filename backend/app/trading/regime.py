"""Daily regime (trend vs chop) via Kaufman's Efficiency Ratio.

Single source of truth shared by the signal overlay (``GET /signals/active``)
and the position-health watcher (``GET /trading/positions``) so both read
"is this name trending?" identically. ER in [0, 1]: >~0.4 is a clean trend,
<~0.3 is chop. Threshold from the 2026-07-30/31 trade review, where the choppy
bucket produced nearly all the losses.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import OhlcvDaily

CHOPPY_ER = 0.30  # daily Kaufman ER below this = choppy
ER_PERIOD = 10
_LOOKBACK_DAYS = 45  # ~30 trading days → enough bars for ER(10)


def kaufman_er(closes: list[float], n: int = ER_PERIOD) -> float | None:
    """Efficiency ratio over the last ``n`` moves: ``|net| / sum(|steps|)``.

    ``None`` when there are too few bars. 0-1, where >~0.4 is a clean trend and
    <~0.3 is chop. A flat path (no movement) returns 0.0, not a divide error.
    """
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1):]
    net = abs(seg[-1] - seg[0])
    path = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
    return (net / path) if path else 0.0


async def er_by_stock(
    db: AsyncSession, stock_ids: list[int], now: datetime
) -> dict[int, float | None]:
    """Current daily-regime ER for each stock, from recent completed daily bars.

    One batch query for the whole set. Stocks with too few bars map to ``None``
    (regime unknown → callers must treat as "not choppy", never as chop).
    """
    if not stock_ids:
        return {}
    cutoff = now - timedelta(days=_LOOKBACK_DAYS)
    rows = (
        await db.execute(
            select(OhlcvDaily.stock_id, OhlcvDaily.close)
            .where(
                OhlcvDaily.stock_id.in_(stock_ids),
                OhlcvDaily.is_complete.is_(True),
                OhlcvDaily.time >= cutoff,
            )
            .order_by(OhlcvDaily.stock_id, OhlcvDaily.time)
        )
    ).all()
    by_stock: dict[int, list[float]] = {}
    for r in rows:
        by_stock.setdefault(r.stock_id, []).append(float(r.close))
    return {sid: kaufman_er(closes) for sid, closes in by_stock.items()}
