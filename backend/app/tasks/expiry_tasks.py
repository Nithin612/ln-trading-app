"""Signal expiry sweeper — makes SIGNAL_ENGINE.md §5 true (Phase 2 slice 2).

The spec has always said "runs every 5 minutes via Celery"; until now
expiry existed only as a lazy query-time filter and `expired_at` was never
written. Outcome P&L reconciliation stays Phase 6 — this task only owns
the status lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.celery_app import celery_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.expiry_tasks.sweep_expired_signals", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def sweep_expired_signals(self: object) -> dict[str, int]:  # noqa: ARG001
    """Flip lapsed active signals to expired. Beat: every 5 min, weekdays."""
    return asyncio.run(_run_sweep())


async def sweep_expired(db: AsyncSession, now: datetime) -> int:
    """Core sweep — session and clock injected so tests freeze time."""
    from sqlalchemy import update

    from app.models.signal import Signal

    result = await db.execute(
        update(Signal)
        .where(Signal.status == "active", Signal.validity_until <= now)
        .values(status="expired", expired_at=now)
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def _run_sweep() -> dict[str, int]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        expired = await sweep_expired(db, datetime.now(tz=UTC))
    if expired:
        log.info("expiry sweep: %d signals expired", expired)
    return {"signals_expired": expired}
