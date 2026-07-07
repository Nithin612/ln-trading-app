"""Celery tasks for corporate filings ingestion — Phase 6."""
from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.filing_tasks.poll_filings", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def poll_filings(self: object) -> dict[str, int]:  # noqa: ARG001
    """Poll NSE and BSE corporate announcements. Runs every 60 seconds."""
    return run_db_task(_run_poll)


async def _run_poll() -> dict[str, int]:
    from app.db.session import AsyncSessionFactory
    from app.ingestion.filings_consumer import ingest_filings

    async with AsyncSessionFactory() as db:
        count = await ingest_filings(db)
        return {"inserted": count}
