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


@celery_app.task(name="app.tasks.profile_tasks.intraday_suggestions", bind=True, max_retries=1)  # type: ignore[untyped-decorator]
def intraday_suggestions(self: object, schedule: str) -> dict[str, object]:  # noqa: ARG001
    """Run the profiles on an intraday schedule. Beat: see celery_app.

    Replaces the `on_close_suggestions` stub. That stub was written to be driven
    by live candle-close events, which is a strictly harder problem (one task
    per stock per bar, fanning out across the universe) for no benefit here: the
    profiles score a COMPLETED bar, and bar boundaries are known in advance, so
    a beat one minute after each close is the same computation with a fraction
    of the machinery and no dependence on the tick pipeline being healthy.
    """
    return run_db_task(lambda: _run_intraday(schedule))


async def _run_intraday(schedule: str) -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.profiles.pipeline import run_scheduled_profiles
    from app.services.market_calendar import is_trading_day
    from app.tasks.signal_tasks import _default_risk_params
    from app.trading.market_hours import is_market_session

    now_utc = datetime.now(UTC)
    # Authoritative session guard. The crontab window is deliberately coarse
    # (it cannot express :15-minute precision across an hour range), so the
    # exact 09:15–15:30 IST boundary is enforced here — the same split the
    # position monitor uses after its 08:30 pre-open beat closed positions on a
    # stale previous-session close.
    if not is_market_session(now_utc):
        return {"status": "skipped", "message": "outside market session"}

    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, now_utc.astimezone(_IST).date()):
            return {"status": "skipped", "message": "not a trading day"}
        capital, risk_pct = _default_risk_params()
        counts = await run_scheduled_profiles(db, schedule, capital, risk_pct)
    log.info("intraday suggestions (%s): %s", schedule, counts)
    return {"status": "ok", "schedule": schedule, "profiles": counts}
