"""Worker heartbeat — A40.

The cheapest half of the liveness story: each role records that it is alive, and the
ABSENCE of that record is the alarm. No counter, no scrape, no metrics stack — the same
ruling that kept 6.8.6 a staleness check rather than a Prometheus deployment.

This task runs on the Celery worker and therefore reports the `celery` role only. A worker
that is down cannot report that it is down; that asymmetry is the whole point, and it is why
the reader of these heartbeats (`make analysis`) lives in a different process.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.worker_heartbeat", bind=True, max_retries=0
)
def worker_heartbeat(self: object) -> dict[str, object]:  # noqa: ARG001
    """Record that the Celery worker is alive."""
    return run_db_task(_run_heartbeat)


async def _run_heartbeat() -> dict[str, object]:
    import contextlib

    import redis.asyncio as aioredis

    from app.core.config import settings
    from app.services.worker_health import beat

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await beat(r, "celery")
    finally:
        with contextlib.suppress(Exception):
            await r.aclose()
    return {"status": "ok", "role": "celery"}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.check_calendar_coverage", bind=True, max_retries=0
)
def check_calendar_coverage(self: object) -> dict[str, object]:  # noqa: ARG001
    """A36 — push PROACTIVELY when the NSE holiday calendar is running out of runway.

    The query-time warning inside `market_calendar` is seen by nobody. This reads the
    coverage horizon once a day and, if it is short or gone, PUSHES via the notifier — the
    same absence-vs-presence pairing as A40's CAS check. The daily report carries the same
    horizon as a human-read surface, so a quiet channel is never the only evidence.
    """
    return run_db_task(_run_check_calendar_coverage)


async def _run_check_calendar_coverage() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.calendar_health import read_calendar_status, to_notification
    from app.services.notifier import notify

    async with AsyncSessionFactory() as db:
        status = await read_calendar_status(db)
    n = to_notification(status)
    if n is not None:
        notify(n)
        return {
            "status": "alert",
            "level": n.level.value,
            "trading_days_remaining": status.trading_days_remaining,
            "covered_through": str(status.coverage_end),
        }
    return {
        "status": "ok",
        "trading_days_remaining": status.trading_days_remaining,
        "covered_through": str(status.coverage_end),
    }
