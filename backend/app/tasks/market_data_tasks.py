"""Market-data ingestion tasks (Phase 2 slice 3).

FII/DII daily flows were previously ingestable only via the manual admin
endpoint — the ±5-weight §2.7 factor scored zero forever. This task puts
ingestion on the beat (18:30 IST, after NSE publishes EOD flows).

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
    """Fetch + upsert today's FII/DII flows. Beat: 18:30 IST weekdays."""
    return run_db_task(_run_ingest)


async def _run_ingest() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.fii_dii_service import fetch_fii_dii_data, upsert_fii_dii
    from app.services.market_calendar import is_trading_day

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, today_ist):
            log.info("FII/DII ingestion skipped: %s is not a trading day", today_ist)
            return {"status": "skipped", "message": "not a trading day"}
        records = await fetch_fii_dii_data()
        inserted, skipped = await upsert_fii_dii(db, records)
    log.info("FII/DII ingestion: %d inserted, %d skipped", inserted, skipped)
    return {"status": "ok", "inserted": inserted, "skipped": skipped}


@celery_app.task(name="app.tasks.market_data_tasks.ingest_equities_eod", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def ingest_equities_eod(self: object) -> dict[str, object]:  # noqa: ARG001
    """Ingest today's equities bhavcopy into ohlcv_1d. Beat: 18:40 IST.

    Closes a pipeline gap found in Phase 2: no beat task ever refreshed
    daily candles (the Phase-1 backfill script was the only writer), so
    nightly signal generation scored stale data.
    """
    return run_db_task(_run_equities_eod)


async def _run_equities_eod() -> dict[str, object]:
    from app.db.session import AsyncSessionFactory
    from app.services.bhavcopy_service import ingest_bhavcopy_date
    from app.services.market_calendar import is_trading_day

    today_ist = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        if not await is_trading_day(db, today_ist):
            log.info("Equities EOD skipped: %s is not a trading day", today_ist)
            return {"status": "skipped", "message": "not a trading day"}
        result = await ingest_bhavcopy_date(db, today_ist)
        # CA quarantine sweep (slice 6): catch split/bonus discontinuities
        # in the fresh session BEFORE tonight's generation scores them.
        from app.services.ca_detector import scan_for_discontinuities

        flagged = await scan_for_discontinuities(db, today_ist)
    log.info("Equities EOD ingestion: %s (CA flags: %d)", result, len(flagged))
    payload = result.model_dump(mode="json")
    payload["ca_flagged"] = len(flagged)
    return payload
