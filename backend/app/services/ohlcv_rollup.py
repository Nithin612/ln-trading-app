"""Session-aligned ohlcv_1h rollup (Phase 3, slice 3.2).

ONE definition of the 1h rebuild SQL, executed by both the alembic
migration (sync) and the async service entry point — the SQL itself is
the single source so the two cannot drift.

Bucket canon (slice 3.1, ARCHITECTURE.md §Live bucket canon): buckets
anchor at the session open — 09:15 IST — so the hourly set is
09:15, 10:15, …, 15:15, the last being the 15:15–15:30 stub. Source is
the backfilled/consumer 5m table (finest committed granularity):

  - only `is_complete` 5m bars aggregate;
  - pre-open (< 09:15 IST) and post-close (≥ 15:30 IST) bars are excluded,
    matching the backfill session guard;
  - a 1h row is minted only once its bucket has fully ENDED (clamped to
    the 15:30 session close) at execution time — the forming hour of a
    live session never lands as `is_complete`;
  - `ON CONFLICT DO NOTHING`: reruns never replace history (the same
    never-replace discipline as the intraday backfill).

The v1 rows this replaces were UTC-hour floors (…09:30, 10:30 IST — plus
post-close pollution): every pre-rebuild row is wrong, which is why the
migration deletes the table body outright before rolling up.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: `time AT TIME ZONE 'Asia/Kolkata'` on a timestamptz yields naive
# IST; the reverse cast at the end returns timestamptz. IST has no DST.
REBUILD_OHLCV_1H_SQL = """
INSERT INTO ohlcv_1h (time, stock_id, open, high, low, close, volume, is_complete)
SELECT
    (bucket_ist AT TIME ZONE 'Asia/Kolkata')  AS time,
    stock_id,
    (array_agg(open  ORDER BY time ASC))[1]   AS open,
    max(high)                                 AS high,
    min(low)                                  AS low,
    (array_agg(close ORDER BY time DESC))[1]  AS close,
    sum(volume)::bigint                       AS volume,
    true                                      AS is_complete
FROM (
    SELECT
        time, stock_id, open, high, low, close, volume, ts_ist,
        session_open
          + (floor(extract(epoch FROM (ts_ist - session_open)) / 3600.0)
             * interval '1 hour')             AS bucket_ist
    FROM (
        SELECT *,
               (time AT TIME ZONE 'Asia/Kolkata')            AS ts_ist,
               (date_trunc('day', time AT TIME ZONE 'Asia/Kolkata')
                  + interval '9 hours 15 minutes')           AS session_open
        FROM ohlcv_5m
        WHERE is_complete IS TRUE
    ) anchored
    WHERE ts_ist >= session_open
      AND ts_ist <  date_trunc('day', ts_ist) + interval '15 hours 30 minutes'
) bucketed
GROUP BY stock_id, bucket_ist
HAVING (
    least(
        bucket_ist + interval '1 hour',
        date_trunc('day', bucket_ist) + interval '15 hours 30 minutes'
    ) AT TIME ZONE 'Asia/Kolkata'
) <= :as_of
ON CONFLICT (time, stock_id) DO NOTHING
"""

DELETE_OHLCV_1H_SQL = "DELETE FROM ohlcv_1h"


async def rebuild_ohlcv_1h(
    db: AsyncSession, *, as_of: datetime | None = None, delete_first: bool = False
) -> int:
    """Roll up ohlcv_1h from 5m bars; returns rows inserted.

    as_of (default: now UTC) is the completeness cutoff — only buckets
    fully ended by it are minted; injected rather than read from the DB
    clock so tests pin it (testing.md: freeze or inject time). With
    delete_first the table body is replaced (the migration's behavior);
    without it the call is a pure never-replace top-up."""
    if delete_first:
        await db.execute(text(DELETE_OHLCV_1H_SQL))
    cutoff = as_of if as_of is not None else datetime.now(tz=UTC)
    result = await db.execute(text(REBUILD_OHLCV_1H_SQL).bindparams(as_of=cutoff))
    inserted = getattr(result, "rowcount", 0)
    await db.commit()
    return int(inserted or 0)
