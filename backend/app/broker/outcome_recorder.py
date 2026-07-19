"""Signal-outcome recorder thread (Phase 3, slice 3.6).

Consumes the tick-trigger alerts Redis STREAM through a consumer group
(`outcome-recorder`) and persists first touches of each active signal's
entry zone / SL / TP via app/services/signal_outcomes.py. Durable
at-least-once: entries are XACKed only AFTER the DB commit, redelivery
is harmless (every write is idempotent), and a crash leaves unacked
entries in the PEL, which the startup recovery pass re-reads (id "0")
before tailing new entries (">").

Runs as a daemon thread in the live worker (the refresher pattern: own
event loop, own pool_size=1 engine, own sync redis client — nothing
pooled ever crosses loops; ZERO work on the consumer thread). Alerts
without a signal_id (market-level PDH/PDL/S&R/vburst) and non-touch
signal alerts (sl_near/tp_near proximity) are ACKed immediately —
outcome truth needs touches, and an unacked skip would pin the PEL
forever.

Pure observability: never feeds scoring, sizing, gating, or backtests.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time as time_mod
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.services.signal_outcomes import (
    TOUCH_SOURCES,
    apply_touch,
    ensure_outcome_row,
)

log = logging.getLogger(__name__)

GROUP = "outcome-recorder"
CONSUMER = "worker-1"  # single-consumer group by design (one live worker)

_BATCH = 200
_BLOCK_MS = 2000


def ensure_group(redis: Any) -> None:
    """Create the consumer group at '$' (new alerts only — outcomes
    begin at deployment; pre-existing stream history belongs to signals
    the expiry sweeper will finalize). BUSYGROUP = already exists."""
    import redis as redis_lib

    try:
        redis.xgroup_create(settings.live_alert_stream, GROUP, id="$", mkstream=True)
    except redis_lib.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def drain_once(db: Any, redis: Any, *, start_id: str = ">") -> int:
    """One XREADGROUP batch → idempotent writes → COMMIT → XACK.

    start_id ">" tails new entries; "0" re-reads THIS consumer's pending
    list (crash recovery). Returns entries processed (0 = nothing there).
    """
    resp = redis.xreadgroup(
        GROUP,
        CONSUMER,
        {settings.live_alert_stream: start_id},
        count=_BATCH,
        block=_BLOCK_MS if start_id == ">" else None,
    )
    if not resp:
        return 0
    _stream, entries = resp[0]
    if not entries:
        return 0

    ack_ids: list[str] = []
    wrote = False
    for entry_id, fields in entries:
        ack_ids.append(entry_id)
        source = fields.get("source", "")
        signal_id = fields.get("signal_id")
        if source not in TOUCH_SOURCES or not signal_id:
            continue  # acked below — not outcome material
        try:
            ts = datetime.fromtimestamp(int(fields["ts"]), tz=UTC)
            price = str(fields["price"])
        except (KeyError, TypeError, ValueError):
            log.warning("outcome: malformed alert entry %s skipped: %s",
                        entry_id, fields)
            continue
        # Per-entry SAVEPOINT: one poison entry (e.g. an unbindable price
        # reaching the driver) must roll back ONLY ITSELF — never abort
        # its batch-mates' writes, and it gets ACKed as a documented drop
        # instead of pinning the PEL and killing the thread on every
        # restart (bug-hunter MEDIUM 2026-07-19, executed repro).
        try:
            async with db.begin_nested():
                if not await ensure_outcome_row(db, signal_id):
                    log.warning("outcome: alert for unknown signal %s skipped",
                                signal_id)
                    continue
                await apply_touch(db, signal_id=signal_id, source=source,
                                  ts=ts, price=price)
            wrote = True
        except Exception:
            log.exception("outcome: entry %s poisoned; acking as dropped: %s",
                          entry_id, fields)

    if wrote:
        await db.commit()
    # ACK strictly AFTER the commit: a crash between commit and ack means
    # redelivery of already-applied entries — harmless by idempotency.
    if ack_ids:
        redis.xack(settings.live_alert_stream, GROUP, *ack_ids)
    return len(entries)


def run_outcome_recorder(stop: threading.Event) -> None:
    """Outcome recorder thread body (the refresher pattern)."""
    import redis as redis_sync
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    loop = asyncio.new_event_loop()
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    redis = redis_sync.from_url(settings.redis_url, decode_responses=True)

    async def _drain(start_id: str) -> int:
        async with AsyncSession(engine) as db:
            return await drain_once(db, redis, start_id=start_id)

    try:
        ensure_group(redis)
        # Crash recovery: re-process THIS consumer's unacked entries
        # first. Same armor as the tail loop — a transient DB/redis error
        # here must retry, not kill the thread on every worker start
        # (bug-hunter MEDIUM 2026-07-19).
        while not stop.is_set():
            try:
                if loop.run_until_complete(_drain("0")) == 0:
                    break
            except Exception:
                log.exception("outcome: recovery drain failed; retrying")
                time_mod.sleep(1.0)
        while not stop.is_set():
            try:
                loop.run_until_complete(_drain(">"))
            except Exception:
                log.exception("outcome: drain failed; retrying")
                # a dead redis/DB must not busy-spin the thread
                time_mod.sleep(1.0)
    except Exception:
        log.exception("outcome: recorder thread died")
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()
        try:
            redis.close()
        except Exception:
            log.debug("outcome: redis close raised; ignoring")
