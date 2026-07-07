"""Regression: Celery tasks reusing the pooled engine across event loops.

Bug (Phase-2 gate, bug-hunter HIGH): every task body did
`asyncio.run(...)` — a fresh loop — while app.db.session's POOLED engine
returned asyncpg connections bound to the previous task's (closed) loop.
The worker child's second DB task died with "got Future attached to a
different loop": the 5-min sweeper kept children warm, so the sweeper,
EOD chain, and nightly suggestions were all structurally broken in a real
worker. Invisible to the suite because conftest builds its own NullPool
engine.

run_db_task disposes the pool INSIDE each task's loop; these tests drive
the app's REAL pooled engine through back-to-back fresh loops — the
canary sequence that failed before the fix.
"""

from __future__ import annotations

from app.db.session import AsyncSessionFactory
from app.tasks._runner import run_db_task
from sqlalchemy import text


async def _probe() -> int:
    async with AsyncSessionFactory() as db:
        return int((await db.execute(text("SELECT 1"))).scalar_one())


def test_celery_loop_reuse_second_task_survives() -> None:
    """Two sequential fresh-loop runs against the pooled app engine —
    the second call raised RuntimeError(different loop) on the old
    asyncio.run pattern."""
    assert run_db_task(_probe) == 1
    assert run_db_task(_probe) == 1  # ← died here before the fix
    assert run_db_task(_probe) == 1


def test_pool_is_empty_between_task_loops() -> None:
    """The disposal contract itself: after run_db_task returns, the pool
    holds no connections bound to the dead loop."""
    from app.db.session import engine

    run_db_task(_probe)
    assert engine.pool.checkedin() == 0
    assert engine.pool.checkedout() == 0
