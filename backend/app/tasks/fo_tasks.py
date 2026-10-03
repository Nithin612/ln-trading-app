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
    """Calendar-free wall-clock check (09:15–15:30 IST, Mon–Fri) — a thin alias of
    `market_hours.is_market_session`, kept for callers without a DB (W2: one
    implementation). Tasks with a DB use `market_calendar.in_market_session`, which
    also sees weekend special sessions and holidays."""
    from app.trading.market_hours import is_market_session

    return is_market_session(now_utc or datetime.now(UTC))


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

    async with AsyncSessionFactory() as db:
        from app.services.market_calendar import in_market_session

        if not await in_market_session(db, datetime.now(UTC)):
            return {"status": "skipped", "message": "outside market session"}
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
