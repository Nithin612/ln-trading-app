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

    ⭐ **D2′b: this now APPLIES.** It evaluates the versioned rule, records the outcome,
    and adopts it — `apply_to_stocks` is the single writer a database trigger permits.
    That is the point: `is_active` had three uncoordinated writers, and on 2026-09-07
    one of them wrote it wrong and the system scanned micro-caps for five days.

    ⛔ **A collapse is refused, not applied.** The rule's input is a CSV fetched over
    the internet and this runs unattended; a truncated feed must never switch off the
    market. The task logs the refusal and leaves the universe alone.

    ⚠ Runs AFTER `sync_kite_instruments` (02:30 UTC): the rule reads
    `kite_instruments`, so evaluating first would judge the universe against
    yesterday's instrument dump.
    """
    return run_db_task(_run_materialise_universe)


async def _run_materialise_universe() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.universe_materialiser import (
        apply_to_stocks,
        download_equity_l,
        load_inputs,
        materialise,
        record_inputs,
    )

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        # ⭐ The raw source is fetched HERE rather than inside `load_inputs` so the exact
        # bytes can be recorded. §73: the artifact is contents, not a hash — a hash gives
        # you `H(input)` while every consumer needs `input`, and `kite_instruments` is
        # upserted in place, so its state is otherwise gone by tomorrow.
        csv_text = await download_equity_l()
        inputs = await load_inputs(db, csv_text=csv_text)
        # ⚠ BEFORE the decision, and committed on its own. The refusal path below is the
        # single most important thing to be able to audit, and it is precisely the path
        # where the later steps do not run.
        await record_inputs(db, as_of=today_ist, csv_text=csv_text, inputs=inputs)
        members = await materialise(db, as_of=today_ist, inputs=inputs)
        try:
            activated, deactivated = await apply_to_stocks(db, as_of=today_ist)
        except ValueError as exc:
            # ⭐ CORRECTED (§73/2): this used to claim the snapshot alone made a refusal
            # "inspectable". It did not — the rail fires on a property of the INPUT while
            # `universe_snapshot` records the rule's OUTPUT, so a firing could be seen but
            # never explained, and `universe_apply_min_fraction` could never be tuned.
            # `universe_rule_inputs` is what actually makes this line true.
            log.error("universe %s NOT applied: %s", today_ist, exc)
            return {"members": members, "applied": False, "reason": str(exc)}

    if activated or deactivated:
        log.warning(
            "universe %s: %d member(s); is_active changed — +%d activated, -%d deactivated",
            today_ist, members, activated, deactivated,
        )
    else:
        log.info("universe %s: %d member(s); no change", today_ist, members)
    return {
        "members": members,
        "applied": True,
        "activated": activated,
        "deactivated": deactivated,
    }
