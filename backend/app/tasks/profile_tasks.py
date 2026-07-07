"""Celery tasks for the per-profile suggestion pipelines (Phase 2 slice 7).

nightly_suggestions runs every ACTIVE eod-schedule profile after the EOD
data chain (FII/DII 18:30 → equities EOD 18:40 → legacy generation 19:15 →
THIS at 19:25 IST). The on-close trigger is a stub until Phase-3 realtime
delivers live candle-close events.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")


@celery_app.task(name="app.tasks.profile_tasks.nightly_suggestions", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def nightly_suggestions(self: object) -> dict[str, object]:  # noqa: ARG001
    """Run all active EOD profiles. Beat: 19:25 IST weekdays."""
    return run_db_task(_run_nightly)


async def _run_nightly() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.profiles.pipeline import run_scheduled_profiles
    from app.services.market_calendar import is_trading_day
    from app.tasks.signal_tasks import _default_risk_params

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, today_ist):
            log.info("nightly suggestions skipped: %s is not a trading day", today_ist)
            return {"status": "skipped", "message": "not a trading day"}
        capital, risk_pct = _default_risk_params()
        counts = await run_scheduled_profiles(db, "eod", capital, risk_pct)
    return {"status": "ok", "profiles": counts}


@celery_app.task(name="app.tasks.profile_tasks.on_close_suggestions", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def on_close_suggestions(self: object, stock_id: int, timeframe: str) -> dict[str, object]:  # noqa: ARG001
    """Phase-3 stub: live candle-close trigger for intraday profiles."""
    log.debug("on_close_suggestions stub: stock=%s tf=%s (Phase 3)", stock_id, timeframe)
    return {"status": "stub", "message": "intraday profile triggers arrive with Phase 3"}
