"""Self-healing EOD catch-up (Phase 3 incident, 2026-07-17).

EOD ingestion was silently DOWN 2026-07-03 → 2026-07-17: the Celery
worker/beat never ran in the v2 era, and every EOD beat task ingested
only `today` — so each quiet evening became a permanent hole nobody
noticed until soak trigger levels turned out to be two weeks stale.

Every catch-up function heals ALL missing trading sessions inside a
bounded lookback window. Presence is checked per session (not via
max(date)), so interior holes — e.g. a late-published archive between
two ingested days — heal too. Beat tasks and the manual runner
(scripts/catchup_eod.py) share these functions, so one evening run
converges the tables no matter how long the box was quiet. Holes older
than LOOKBACK_DAYS need scripts/backfill_eod.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import fii_dii_service
from app.services.bhavcopy_service import ingest_bhavcopy_date
from app.services.ca_detector import scan_for_discontinuities
from app.services.fo_bhavcopy_service import ingest_fo_bhavcopy_date
from app.services.market_calendar import trading_days_between
from app.services.vix_service import ingest_vix_date

log = logging.getLogger(__name__)

# Bounds NSE archive hits per run; a quiet spell longer than this needs
# the explicit backfill script.
LOOKBACK_DAYS = 21

# Recovery evenings download many sessions back-to-back; NSE archives get
# a breather between days so a burst doesn't look like scraping.
_INTER_DAY_PAUSE_S = 0.5

# Whitelist (python rules): raw table names never come from callers.
# The ::date casts are tz-pinned — a session TimeZone other than UTC must
# not shift which trade date a UTC-midnight bar reports as present.
_PRESENT_DATES_SQL = {
    "ohlcv_1d": (
        "SELECT DISTINCT (time AT TIME ZONE 'UTC')::date FROM ohlcv_1d WHERE time >= :start"
    ),
    "fo_bhavcopy": ("SELECT DISTINCT trade_date FROM fo_bhavcopy WHERE trade_date >= :start"),
    "india_vix_daily": (
        "SELECT DISTINCT trade_date FROM india_vix_daily WHERE trade_date >= :start"
    ),
    "fii_dii_daily": ("SELECT DISTINCT trade_date FROM fii_dii_daily WHERE trade_date >= :start"),
}


async def missing_sessions(
    db: AsyncSession, table: str, today: date, lookback_days: int = LOOKBACK_DAYS
) -> list[date]:
    """Trading sessions in [today − lookback, today] with no rows in `table`."""
    sql = _PRESENT_DATES_SQL.get(table)
    if sql is None:
        raise ValueError(f"not an EOD catch-up table: {table!r}")
    start = today - timedelta(days=lookback_days)
    # Daily bars sit at UTC midnight of the trade date; a tz-aware bind
    # keeps hypertable chunk pruning exact for ohlcv_1d.
    start_bind: object = (
        datetime(start.year, start.month, start.day, tzinfo=UTC) if table == "ohlcv_1d" else start
    )
    rows = (await db.execute(text(sql), {"start": start_bind})).scalars().all()
    present = set(rows)
    return [d for d in await trading_days_between(db, start, today) if d not in present]


async def catchup_equities_eod(
    db: AsyncSession, today: date, lookback_days: int = LOOKBACK_DAYS
) -> dict[str, object]:
    """Heal ohlcv_1d up to `today`, then CA-sweep every present session
    in the window.

    The sweep runs over the WHOLE window (not just sessions healed right
    now) and is idempotent — scan_for_discontinuities flags only
    still-unflagged stocks — so a sweep lost to a crash between a day's
    bar-commit and its scan, or skipped entirely by backfill_eod.py
    (which never sweeps), is repaired on the next run. Presence of bars
    therefore implies "eventually swept", never "assumed swept".
    """
    sessions = await missing_sessions(db, "ohlcv_1d", today, lookback_days)
    ingested: list[str] = []
    skipped: list[str] = []
    rows_inserted = 0
    for i, d in enumerate(sessions):
        if i:
            await asyncio.sleep(_INTER_DAY_PAUSE_S)
        try:
            result = await ingest_bhavcopy_date(db, d)
        except httpx.HTTPError as exc:
            # A transport failure on one session must not forfeit the rest
            # of the run — the day stays missing and heals on a later run.
            # DB errors still propagate and abort loudly.
            log.warning("EOD catch-up ohlcv_1d %s: network failure, retrying next run: %s", d, exc)
            skipped.append(d.isoformat())
            continue
        if result.status == "ok":
            ingested.append(d.isoformat())
            rows_inserted += result.rows_inserted
        else:
            # Not published yet, or an unseeded holiday — retried on every
            # run until it ages out of the lookback window.
            skipped.append(d.isoformat())

    still_missing = set(await missing_sessions(db, "ohlcv_1d", today, lookback_days))
    window_start = today - timedelta(days=lookback_days)
    ca_flagged = 0
    for d in await trading_days_between(db, window_start, today):
        if d not in still_missing:
            ca_flagged += len(await scan_for_discontinuities(db, d))

    status = "ok" if sessions else "up_to_date"
    log.info(
        "EOD catch-up ohlcv_1d: status=%s ingested=%s skipped=%s rows=%d ca_flagged=%d",
        status,
        ingested,
        skipped,
        rows_inserted,
        ca_flagged,
    )
    return {
        "status": status,
        "sessions_ingested": ingested,
        "sessions_skipped": skipped,
        "rows_inserted": rows_inserted,
        "ca_flagged": ca_flagged,
    }


async def catchup_fo_eod(
    db: AsyncSession, today: date, lookback_days: int = LOOKBACK_DAYS
) -> dict[str, object]:
    """Heal fo_bhavcopy and india_vix_daily independently up to `today`."""
    payload: dict[str, object] = {}
    for table, ingest_one in (
        ("fo_bhavcopy", ingest_fo_bhavcopy_date),
        ("india_vix_daily", ingest_vix_date),
    ):
        sessions = await missing_sessions(db, table, today, lookback_days)
        ingested: list[str] = []
        skipped: list[str] = []
        for i, d in enumerate(sessions):
            if i:
                await asyncio.sleep(_INTER_DAY_PAUSE_S)
            try:
                result = await ingest_one(db, d)
            except httpx.HTTPError as exc:
                # Per-day isolation: one bad download must not forfeit the
                # rest of this table's heal NOR the other table's loop.
                log.warning(
                    "EOD catch-up %s %s: network failure, retrying next run: %s", table, d, exc
                )
                skipped.append(d.isoformat())
                continue
            if result.get("status") == "ok":
                ingested.append(d.isoformat())
            else:
                skipped.append(d.isoformat())
        payload[table] = {
            "status": "ok" if sessions else "up_to_date",
            "sessions_ingested": ingested,
            "sessions_skipped": skipped,
        }
        log.info("EOD catch-up %s: ingested=%s skipped=%s", table, ingested, skipped)
    return payload


async def catchup_fii_dii(
    db: AsyncSession, today: date, lookback_days: int = LOOKBACK_DAYS
) -> dict[str, object]:
    """Heal fii_dii_daily with whatever the NSE endpoint serves.

    The live endpoint returns only the LATEST trading day (verified
    2026-07-18), so this heals at most one session per run — flows are
    capture-as-you-go. `still_missing` reports the sessions the fetch
    did not cover; those are permanently unavailable from this source
    (a historical fetcher is Phase-4 scope, like bulk deals). The §2.7
    rollup treats missing days as zero by design.
    """
    missing = await missing_sessions(db, "fii_dii_daily", today, lookback_days)
    if not missing:
        return {"status": "up_to_date", "inserted": 0, "skipped": 0, "still_missing": []}

    try:
        records = await fii_dii_service.fetch_fii_dii_data()
    except httpx.HTTPError as exc:
        # Non-200/non-JSON already degrade to [] inside the fetch; transport
        # errors get the same treatment — report and heal on a later run.
        log.warning("EOD catch-up fii_dii_daily: network failure, retrying next run: %s", exc)
        return {
            "status": "fetch_failed",
            "inserted": 0,
            "skipped": 0,
            "still_missing": [d.isoformat() for d in missing],
        }
    inserted, skipped = await fii_dii_service.upsert_fii_dii(db, records)
    still_missing = await missing_sessions(db, "fii_dii_daily", today, lookback_days)
    log.info(
        "EOD catch-up fii_dii_daily: inserted=%d skipped=%d still_missing=%s",
        inserted,
        skipped,
        still_missing,
    )
    return {
        "status": "ok",
        "inserted": inserted,
        "skipped": skipped,
        "still_missing": [d.isoformat() for d in still_missing],
    }
