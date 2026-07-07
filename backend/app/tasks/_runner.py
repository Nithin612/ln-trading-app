"""Celery ↔ asyncio bridge for DB-touching tasks.

Every Celery task body runs `asyncio.run(...)` — a FRESH event loop per
invocation. The shared engine in app.db.session is POOLED: asyncpg
connections returned to the pool stay bound to the loop they were created
on, so the worker child's SECOND task finds loop-dead connections and dies
with "got Future attached to a different loop". The 5-minute expiry
sweeper keeps every prefork child warm, which made every recurring DB task
after the first structurally broken (bug-hunter, Phase-2 gate).

Fix: dispose the pool INSIDE the task's loop, before asyncio.run closes
it. The next task lazily reconnects on its own loop. Cost: one connect per
task — nothing at beat cadence.

Every DB-touching Celery task body must go through run_db_task; direct
asyncio.run(...) with AsyncSessionFactory is the bug this module exists
to prevent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


def run_db_task[T](factory: Callable[[], Awaitable[T]]) -> T:
    """Run an async task body in a fresh loop, pool-safe."""

    async def _wrapped() -> T:
        from app.db.session import engine

        try:
            return await factory()
        finally:
            # Must happen while THIS loop is alive — asyncpg connections
            # cannot be closed from a different (later) loop.
            await engine.dispose()

    return asyncio.run(_wrapped())
