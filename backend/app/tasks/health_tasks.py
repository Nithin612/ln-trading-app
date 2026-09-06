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
