"""Celery tasks for the Phase 0 F&O data recorders.

Recording starts long before the analytics phase because recorded calendar
time is the scarce resource (UPGRADE_PLAN.md):

  - fo_eod_ingestion:      F&O bhavcopy + India VIX, after NSE publishes EOD
  - record_option_chains:  1-minute chain snapshots during market hours;
                           silently idle without an active Kite token
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.core.config import settings
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")


def _within_market_hours(now_utc: datetime | None = None) -> bool:
    """True during NSE cash-market hours (9:15–15:30 IST, Mon–Fri).

    Pure wall-clock check; holiday awareness is a separate async
    market_calendar.is_trading_day() check inside the task bodies.
    """
    now_ist = (now_utc or datetime.now(UTC)).astimezone(_IST)
    if now_ist.weekday() > 4:  # Sat/Sun
        return False
    minutes = now_ist.hour * 60 + now_ist.minute
    return (9 * 60 + 15) <= minutes <= (15 * 60 + 30)


@celery_app.task(name="app.tasks.fo_tasks.fo_eod_ingestion", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def fo_eod_ingestion(self: object) -> dict[str, object]:  # noqa: ARG001
    """Heal F&O bhavcopy + India VIX up to today (self-healing since the
    2026-07-17 EOD outage — see services/eod_catchup.py). 18:45 IST weekdays."""
    return run_db_task(_run_fo_eod)


async def _run_fo_eod() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.eod_catchup import catchup_fo_eod

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        return await catchup_fo_eod(db, today_ist)


@celery_app.task(name="app.tasks.fo_tasks.record_option_chains", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def record_option_chains(self: object) -> dict[str, object]:  # noqa: ARG001
    """One chain-snapshot pass. Beat fires every minute in the market window."""
    return run_db_task(_run_chain_snapshot)


async def _run_chain_snapshot() -> dict[str, object]:
    from app.broker.kite_client import build_kite
    from app.db.session import AsyncSessionFactory
    from app.services.chain_recorder import (
        get_any_active_admin_token,
        record_chain_snapshots,
    )

    if not _within_market_hours():
        return {"status": "skipped", "message": "outside market hours"}

    async with AsyncSessionFactory() as db:
        from app.services.market_calendar import is_trading_day

        if not await is_trading_day(db, datetime.now(UTC).astimezone(_IST).date()):
            return {"status": "skipped", "message": "market holiday"}
        access_token = await get_any_active_admin_token(db)
        if access_token is None:
            # Normal in Phases 0–2 (no Kite subscription yet) — stay quiet.
            return {"status": "skipped", "message": "no active kite token"}

        kite = build_kite(access_token)
        underlyings = [
            u.strip().upper()
            for u in settings.fo_chain_underlyings.split(",")
            if u.strip()
        ]
        return await record_chain_snapshots(
            db, kite, underlyings, settings.fo_chain_strikes_each_side
        )
