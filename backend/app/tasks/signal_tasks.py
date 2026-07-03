"""Celery tasks for signal generation — Phase 6 + Phase 7."""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from app.celery_app import celery_app
from app.core.config import settings

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.signal_tasks.nightly_signal_generation", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def nightly_signal_generation(self: object) -> dict[str, int]:  # noqa: ARG001
    """Generate signals for all active stocks. Runs at 18:00 IST on weekdays."""
    return asyncio.get_event_loop().run_until_complete(_run_generation())


async def _run_generation() -> dict[str, int]:
    from app.db.session import AsyncSessionFactory
    from app.services.signal_service import run_nightly_signal_generation

    async with AsyncSessionFactory() as db:
        capital = Decimal("500000")
        risk_pct = Decimal(str(settings.default_risk_per_trade_pct / 100))
        signals = await run_nightly_signal_generation(db, capital, risk_pct)
        log.info("Nightly signal generation: %d signals produced", len(signals))
        return {"signals_generated": len(signals)}


@celery_app.task(name="app.tasks.signal_tasks.live_signal_generation", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def live_signal_generation(self: object, stock_id: int, timeframe: str) -> dict[str, int]:  # noqa: ARG001
    """Re-run the confluence engine for one stock after a live candle closes."""
    return asyncio.get_event_loop().run_until_complete(
        _run_live_generation(stock_id, timeframe)
    )


async def _run_live_generation(stock_id: int, timeframe: str) -> dict[str, int]:
    from app.db.session import AsyncSessionFactory
    from app.services.signal_service import run_live_signal_generation

    async with AsyncSessionFactory() as db:
        capital = Decimal("500000")
        risk_pct = Decimal(str(settings.default_risk_per_trade_pct / 100))
        count = await run_live_signal_generation(db, stock_id, timeframe, capital, risk_pct)
        return {"signals_generated": count}
