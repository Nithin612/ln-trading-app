"""Celery task — CAS (Closing Auction Session) daily capture (Stage 1).

Polls Kite /quote for the F&O (Category-I) universe during 3:15–3:35 IST and upserts one `cas_daily`
row per stock (pre-auction price, reference, indicative close, official/auction close, imbalance).
Research/observability only — the order path never reads it. Beat fires it every minute in a broad
window; the task self-guards to the CAS window (15:15–15:33 IST), no-op otherwise. Silently
idle without an active Kite admin token (mirrors circuit_tasks).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.core.config import settings
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")
# CAS is 15:15–15:35 IST; auction executes ~15:29. Capture 15:15–15:33 to catch the executed close.
_CAS_START = time(15, 15)
_CAS_END = time(15, 33)


def _within_cas_window() -> bool:
    now = datetime.now(UTC).astimezone(_IST).timetz().replace(tzinfo=None)
    return _CAS_START <= now <= _CAS_END


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.cas_tasks.capture_cas_window", bind=True, max_retries=0
)
def capture_cas_window(self: object) -> dict[str, object]:  # noqa: ARG001
    """One CAS-capture pass. Beat fires it each minute in the market window; it self-guards."""
    return run_db_task(_run_capture_cas)


async def _run_capture_cas() -> dict[str, object]:
    from sqlalchemy import select

    from app.broker.kite_rest import ThrottledKite
    from app.db.session import AsyncSessionFactory
    from app.models.stock import Stock
    from app.services.cas_capture import capture_cas
    from app.services.chain_recorder import get_any_active_admin_token
    from app.services.market_calendar import is_trading_day

    if not settings.cas_capture_enabled:
        return {"status": "skipped", "message": "cas_capture_enabled is False"}
    if not _within_cas_window():
        return {"status": "skipped", "message": "outside CAS window"}

    now_ist = datetime.now(UTC).astimezone(_IST)
    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, now_ist.date()):
            return {"status": "skipped", "message": "market holiday"}
        token = await get_any_active_admin_token(db)
        if token is None:
            return {"status": "skipped", "message": "no active kite token"}
        rows = (
            await db.execute(select(Stock.id, Stock.symbol).where(Stock.is_active, Stock.is_fno))
        ).all()
        symbol_stock_map = {f"NSE:{sym}": sid for sid, sym in rows}
        if not symbol_stock_map:
            return {"status": "skipped", "message": "empty F&O universe"}
        kite = ThrottledKite(token)
        written = await capture_cas(db, kite, symbol_stock_map, trade_date=now_ist.date())

    log.info("CAS capture: %d rows upserted over %d F&O stocks", written, len(symbol_stock_map))
    return {"status": "ok", "written": written, "universe": len(symbol_stock_map)}
