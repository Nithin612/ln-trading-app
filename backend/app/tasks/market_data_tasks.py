"""Market-data ingestion tasks (Phase 2 slice 3; self-healing since Phase 3).

FII/DII daily flows were previously ingestable only via the manual admin
endpoint — the ±5-weight §2.7 factor scored zero forever. This task puts
ingestion on the beat (18:30 IST, after NSE publishes EOD flows).

2026-07-17 incident: the worker/beat never ran in the v2 era and every EOD
task ingested only `today`, so 07-03 → 07-17 became a silent hole. Task
bodies now delegate to services/eod_catchup.py, which heals every missing
session in a bounded lookback window — a run after any quiet spell
converges the tables instead of ingesting one day and leaving the gap.

Bulk/block-deal auto-ingestion stays manual until Phase 4 (no NSE fetcher
exists yet — only parse/upsert); the flow rollup treats missing rows as
zero, so partial data degrades gracefully.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.tasks._runner import run_db_task

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")


@celery_app.task(name="app.tasks.market_data_tasks.ingest_fii_dii", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def ingest_fii_dii(self: object) -> dict[str, object]:  # noqa: ARG001
    """Fetch + upsert FII/DII flows (self-healing). Beat: 18:30 IST weekdays."""
    return run_db_task(_run_ingest)


async def _run_ingest() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.eod_catchup import catchup_fii_dii

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        return await catchup_fii_dii(db, today_ist)


@celery_app.task(name="app.tasks.market_data_tasks.ingest_equities_eod", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def ingest_equities_eod(self: object) -> dict[str, object]:  # noqa: ARG001
    """Heal ohlcv_1d up to today (bhavcopy + CA sweep). Beat: 18:40 IST.

    Closes a pipeline gap found in Phase 2: no beat task ever refreshed
    daily candles (the Phase-1 backfill script was the only writer), so
    nightly signal generation scored stale data.
    """
    return run_db_task(_run_equities_eod)


async def _run_equities_eod() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.eod_catchup import catchup_equities_eod

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        return await catchup_equities_eod(db, today_ist)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.market_data_tasks.sync_kite_instruments", bind=True, max_retries=2
)
def sync_kite_instruments(self: object) -> dict[str, object]:  # noqa: ARG001
    """Refresh `kite_instruments` from the PUBLIC dump. Beat: 08:00 IST weekdays.

    ⭐ U1 — this table had NO scheduled owner. Its only writer was an admin
    HTTP endpoint (`app/api/v1/broker.py`), so after the 2026-09-07 dev-DB
    loss it stayed EMPTY for five days and `live_worker` came up with
    `up: 0 instruments` every morning without failing.

    ⚠ Deliberately token-free (`sync_instruments(db)` with no access token).
    A Kite access token expires ~06:00 IST daily and is renewable only through
    an interactive OAuth login; a scheduled owner that needed one would go dark
    on exactly the mornings nobody logged in — the failure it exists to prevent.
    """
    return run_db_task(_run_sync_instruments)


async def _run_sync_instruments() -> dict[str, object]:
    from app.broker.kite_client import sync_instruments
    from app.db.session import AsyncSessionFactory

    async with AsyncSessionFactory() as db:
        synced = await sync_instruments(db)
    log.info("kite_instruments refreshed: %d rows", synced)
    return {"synced": synced}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.tasks.market_data_tasks.materialise_universe", bind=True, max_retries=2
)
def materialise_universe(self: object) -> dict[str, object]:  # noqa: ARG001
    """D2′a — record today's universe membership. Beat: 08:35 IST weekdays.

    ⚠ **SHADOW ONLY — this does not write `is_active`.** It evaluates the versioned
    rule and stores the outcome, so that "was X in the universe on date D" becomes
    answerable and the diff against the live flag is measurable. Making the rule the
    source of truth is D2′b.

    ⚠ Runs AFTER `sync_kite_instruments` (02:30 UTC): the rule reads
    `kite_instruments`, so evaluating first would judge the universe against
    yesterday's instrument dump.
    """
    return run_db_task(_run_materialise_universe)


async def _run_materialise_universe() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.universe_materialiser import (
        diff_against_live,
        load_inputs,
        materialise,
    )

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        inputs = await load_inputs(db)
        members = await materialise(db, as_of=today_ist, inputs=inputs)
        d = await diff_against_live(db, inputs=inputs)
    log.info(
        "universe %s: %d member(s); vs is_active would activate %d, deactivate %d",
        today_ist, members, len(d.would_activate), len(d.would_deactivate),
    )
    return {
        "members": members,
        "would_activate": len(d.would_activate),
        "would_deactivate": len(d.would_deactivate),
    }
