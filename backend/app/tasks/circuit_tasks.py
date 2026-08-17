"""Celery task for the Phase 6.8.3 circuit-band cache.

Fetches lower/upper circuit limits for the active NSE EQ universe via a single
batched Kite ``quote()`` and caches them in Redis (``circuit:{stock_id}``) for
the circuit-eligibility overlay (``app/signals/circuit_guard.py``). The order
path only READS this cache — never fetches — so no external call touches the
money path. Market-hours only; silently idle without an active Kite token.
"""
from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.core.config import settings
from app.tasks._runner import run_db_task
from app.tasks.fo_tasks import _within_market_hours  # shared wall-clock guard

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.circuit_tasks.refresh_circuit_bands", bind=True, max_retries=0
)
def refresh_circuit_bands(self: object) -> dict[str, object]:  # noqa: ARG001
    """One band-refresh pass. Beat fires it periodically in the market window."""
    return run_db_task(_run_refresh_circuit_bands)


async def _run_refresh_circuit_bands() -> dict[str, object]:
    import redis.asyncio as aioredis

    from app.broker.circuit_bands import refresh_bands
    from app.broker.kite_rest import ThrottledKite
    from app.broker.tick_consumer import _build_token_stock_map
    from app.db.session import AsyncSessionFactory
    from app.services.chain_recorder import get_any_active_admin_token
    from app.services.market_calendar import is_trading_day

    if not settings.circuit_bands_enabled:
        return {"status": "skipped", "message": "circuit_bands_enabled is False"}
    if not _within_market_hours():
        return {"status": "skipped", "message": "outside market hours"}

    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, datetime.now(UTC).astimezone(_IST).date()):
            return {"status": "skipped", "message": "market holiday"}
        access_token = await get_any_active_admin_token(db)
        if access_token is None:
            # Normal without a Kite subscription active — stay quiet.
            return {"status": "skipped", "message": "no active kite token"}
        token_stock_map = await _build_token_stock_map(db, access_token)

    if not token_stock_map:
        return {"status": "skipped", "message": "empty universe"}

    kite = ThrottledKite(access_token)
    ts = datetime.now(UTC).isoformat()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        written = await refresh_bands(r, kite, token_stock_map, ts=ts)
    finally:
        with contextlib.suppress(Exception):
            await r.aclose()

    log.info(
        "circuit-band refresh: %d bands cached over %d instruments",
        written, len(token_stock_map),
    )
    return {"status": "ok", "cached": written, "universe": len(token_stock_map)}
