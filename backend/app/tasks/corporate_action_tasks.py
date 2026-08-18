"""Celery task for Phase 6.8.5 — CA-adjust OPEN paper positions on the ex-date.

Runs pre-market (before the 09:15 IST open, ahead of the position monitor) so a
held position's price levels + qty are corrected for a split/bonus BEFORE the
stock trades ex. Idempotent: a re-run on the same ex-date is a no-op.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.corporate_action_tasks.apply_corporate_actions", bind=True, max_retries=0
)
def apply_corporate_actions(self: object) -> dict[str, object]:  # noqa: ARG001
    """Adjust open paper positions for any corporate action with today's ex-date."""
    return run_db_task(_run_apply_corporate_actions)


async def _run_apply_corporate_actions() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.ca_adjust import apply_ex_date_corporate_actions

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        # Matches ex-date ≤ today (catch-up) and commits per position internally.
        applied = await apply_ex_date_corporate_actions(db, today_ist)
    if applied:
        log.info("CA-adjust: %d open position(s) adjusted for ex-date %s", len(applied), today_ist)
    return {"status": "ok", "ex_date": today_ist.isoformat(), "adjusted": len(applied)}
