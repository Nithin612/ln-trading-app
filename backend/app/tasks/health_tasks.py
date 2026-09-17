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
from typing import TYPE_CHECKING

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from sqlalchemy.ext.asyncio import AsyncSession

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


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.check_feed_coverage", bind=True, max_retries=0
)
def check_feed_coverage(self: object) -> dict[str, object]:  # noqa: ARG001
    """U4′ — push PROACTIVELY when an EOD feed is current but THIN.

    Same absence-vs-presence pairing as A36 above, and the same reason: the coverage
    check's only other caller is `build_daily_report`, i.e. `make analysis`, which a
    human runs by hand. A breadth collapse on a day nobody ran the report was therefore
    never seen — the detector examines the newest session only, and that session then
    joins the baseline it is judged against. The daily report still carries the same
    numbers as a human-read surface, so a quiet channel is never the only evidence.
    """
    return run_db_task(_run_check_feed_coverage)


async def _run_check_feed_coverage() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        return await _coverage_alert_payload(db)


async def _coverage_alert_payload(db: AsyncSession) -> dict[str, object]:
    """The task's body, taking its session as an argument so the `notify` seam can be
    tested through BOTH sides (`.claude/rules/testing.md`: mocking the seam hides it).

    ⚠ The split is not cosmetic. `AsyncSessionFactory` is a module-level POOLED engine,
    while the suite runs function-scoped event loops with NullPool — so a second test in
    the same run gets a pooled connection bound to a closed loop and dies with "Event
    loop is closed". That is the configured pattern the testing rules say not to fight,
    so the session comes in as a parameter and only the three-line `async with` wrapper
    above stays uncovered.
    """
    from app.services.feed_health import check_feed_coverage as read_coverage
    from app.services.feed_health import (
        check_segment_coverage,
        check_session_completeness,
        completeness_to_notification,
        coverage_to_notification,
        segments_to_notification,
    )
    from app.services.notifier import notify

    rows = await read_coverage(db)
    # U4″ — the same beat, because it is the same question at a finer grain with the same
    # remedy. Two notifications rather than one merged: a whole-archive collapse and a
    # missing blue chip need different first moves, and a reader who gets one message for
    # both learns to skim it.
    segments = await check_segment_coverage(db)
    # The third question, on the same beat: same family, same remedy owner. A
    # separate notification because 'current but nearly empty' sends you somewhere
    # different from 'today's file was thin'.
    sessions = await check_session_completeness(db)
    measured = {
        r.table: {"names": r.names, "baseline": r.baseline, "shortfall_pct": r.shortfall_pct}
        for r in rows
    }
    seg_measured = {
        r.name: {"expected": r.expected, "priced": r.priced, "absent": list(r.absent)}
        for r in segments
    }
    alerts = [
        n
        for n in (
            coverage_to_notification(rows),
            segments_to_notification(segments),
            completeness_to_notification(sessions),
        )
        if n is not None
    ]
    for n in alerts:
        notify(n)
    if not alerts:
        return {"status": "ok", "feeds": measured, "segments": seg_measured,
                "sessions": {r.table: r.completeness_pct for r in sessions}}
    # ⚠ `level` stays in the payload. Adding the segment check turned one notification into
    # a list and the first cut dropped this field — the existing beat test caught it, which
    # is the argument for asserting the payload SHAPE and not just the status string.
    return {
        "status": "alert",
        "level": max(n.level.value for n in alerts),
        "feeds": measured,
        "segments": seg_measured,
        "sessions": {r.table: r.completeness_pct for r in sessions},
    }


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.check_universe_health", bind=True, max_retries=0
)
def check_universe_health(self: object) -> dict[str, object]:  # noqa: ARG001
    """§77 — push when the universe rule has stopped running.

    ⭐ The failure this catches has no symptom of its own. `materialise_universe` is the
    only writer of `stocks.is_active`, and that flag gates ingestion breadth, the scan
    universe and the live subscription — so a beat that silently stopped leaves the whole
    system running confidently on a decision nobody re-took. That is the 2026-09-07 shape
    exactly: **the absence of a write is not an error anyone raises.**

    ⚠ Runs at 04:10 UTC = 09:40 IST — AFTER `materialise-universe` (03:05 UTC), so a
    healthy morning is quiet and only a genuinely missed run alarms.
    """
    return run_db_task(_run_check_universe_health)


async def _run_check_universe_health() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        return await _universe_health_payload(db)


async def _universe_health_payload(db: AsyncSession) -> dict[str, object]:
    """The task body, session-injected for the same reason as
    `_coverage_alert_payload` — a pooled module-level engine cannot be opened twice
    across function-scoped event loops."""
    from app.services.notifier import notify
    from app.services.universe_health import read_universe_health, to_notification

    health = await read_universe_health(db)
    measured = {
        "snapshot_as_of": str(health.snapshot_as_of) if health.snapshot_as_of else None,
        "days_behind": health.snapshot_days_behind,
        "active_stocks": health.active_stocks,
        "inputs_on_record": health.inputs_match_snapshot,
    }
    n = to_notification(health)
    if n is not None:
        notify(n)
        return {"status": "alert", "level": n.level.value, **measured}
    return {"status": "ok", **measured}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.check_report_health", bind=True, max_retries=0
)
def check_report_health(self: object) -> dict[str, object]:  # noqa: ARG001
    """Q-R6 / V8 — push when recent trading sessions have no daily report.

    ⭐ Measured: **26 reports against 30 trading sessions** since 2026-08-01 — four
    missing, unnoticed. The report is where every other alarm in this system is READ, so
    a session without one ran unwatched, and **its silence is indistinguishable from a
    quiet day.**

    ⚠ It must live OUT here, in the beat. A report that did not run cannot tell you it did
    not run — the same asymmetry A40 states for the worker heartbeat.
    """
    return run_db_task(_run_check_report_health)


async def _run_check_report_health() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        return await _report_health_payload(db)


async def _report_health_payload(db: AsyncSession) -> dict[str, object]:
    """Session-injected for the same reason as the other two payloads — a pooled
    module-level engine cannot be opened twice across function-scoped event loops."""
    from app.services.notifier import notify
    from app.services.report_health import read_report_health, to_notification

    health = await read_report_health(db)
    measured = {
        "expected": len(health.expected),
        "present": len(health.present),
        "missing": [d.isoformat() for d in health.missing],
    }
    n = to_notification(health)
    if n is not None:
        notify(n)
        return {"status": "alert", "level": n.level.value, **measured}
    return {"status": "ok", **measured}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.health_tasks.check_starved_tables", bind=True, max_retries=0
)
def check_starved_tables(self: object) -> dict[str, object]:  # noqa: ARG001
    """V6/A5 — push when a table a consumer depends on is EMPTY.

    ⭐ One of the project's two recurring defect shapes: the code is correct, wired and
    green, and simply has no data to act on. `kite_instruments` before U1,
    `strategy_profiles` today — four production call sites read it and it has held zero
    rows since the 2026-09-07 rebuild, because `alembic upgrade` will not replay a data
    seed on a revision it has already marked applied.

    ⚠ **Its own task, not folded into `check_universe_health`.** The first cut rode that
    beat on the argument that both ask "is the machinery alive"; it broke that beat's own
    tests, and they were right to break — a task whose contract says "pushes nothing when
    the universe is current" must not push for an unrelated reason. Separate remedies want
    separate alarms.
    """
    return run_db_task(_run_check_starved_tables)


async def _run_check_starved_tables() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        return await _starvation_payload(db)


async def _starvation_payload(db: AsyncSession) -> dict[str, object]:
    """Session-injected, like the other payloads — a pooled module-level engine cannot be
    opened twice across function-scoped event loops."""
    from app.services.notifier import notify
    from app.services.starvation import check_starvation, to_notification

    rows = await check_starvation(db)
    starved = [r.entry.table for r in rows if r.is_starved]
    n = to_notification(rows)
    if n is not None:
        notify(n)
        return {"status": "alert", "level": n.level.value, "starved": starved}
    return {"status": "ok", "starved": []}
