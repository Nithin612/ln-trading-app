"""Deep backfill of index OHLC + India VIX from the NSE indices archive — MCE slice 4.

`index_ohlcv_1d` and `india_vix_daily` both come from the SAME daily NSE indices bhavcopy
CSV (`ind_close_all_DDMMYYYY.csv`), so this downloads it ONCE per session and feeds both
ingesters — half the requests of running two backfills. Idempotent (ON CONFLICT DO NOTHING),
resumable, polite to the archive (one download per session + `--delay`).

Why it exists: the EOD catch-up only heals the last ~21 days, but the 200-DMA market-regime
gate needs ~200 sessions and the §8 validation ~2 years. Run this once to seed that depth;
the nightly worker keeps it current thereafter.

Usage:
    uv run python scripts/backfill_indices.py 2023-07-01 2026-08-20 [--delay 0.7]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.index_ohlcv_service import ingest_index_ohlcv_date  # noqa: E402
from app.services.vix_service import download_indices_csv, ingest_vix_date  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402


async def _run(db: AsyncSession, from_date: date, to_date: date, delay: float) -> int:
    """EVERY calendar day in [from_date, to_date]; one CSV download each, fed to BOTH the
    index-OHLC and VIX ingesters (half the requests of two backfills). Holidays and
    non-sessions come back as an unavailable CSV and are skipped. Idempotent per row.

    ⛔⛔ **The `weekday() < 5` filter was REMOVED 2026-09-19 (item 18).** It is the same defect
    `backfill_ohlcv_history` already had fixed, surviving here in the sibling script: NSE holds
    weekend sessions — eight of them are in our own `ohlcv_1d`, including **two Sundays** — and
    a weekday filter makes them **structurally unreachable, because the request is never made**.
    Verified against the live archive the day this was fixed: `ind_close_all_02032024.csv`
    (Saturday 2024-03-02) returns **110 lines**, and this enumerator would never have asked
    for it.

    ⭐ **The enumerator now asserts NOTHING about which days are sessions: offer every calendar
    day and let the archive's 404 decide.** A filter over a calendar you do not own is an
    unverifiable claim — and the last time that claim was pinned in a test, the test was wrong.

    ⚠ The cost is real and bounded: ~2/7 more requests over the range, each a cheap miss.
    Paying it is strictly better than silently never asking.
    """
    sessions = [
        from_date + timedelta(days=i)
        for i in range((to_date - from_date).days + 1)
    ]
    total = len(sessions)
    print(
        f"Backfilling indices + VIX over {total} calendar days {from_date} → {to_date} "
        f"(non-sessions return an unavailable CSV and are skipped)",
        flush=True,
    )

    ok = skipped = idx_rows = vix_rows = 0
    for i, d in enumerate(sessions, 1):
        # Per-day isolation (matches eod_catchup.catchup_fo_eod): a transient NSE blip on
        # ONE session must not abort the whole run — over hundreds of archive hits a
        # timeout is near-certain, and committed rows make re-runs idempotent + resumable.
        # DB errors still propagate and abort loudly.
        try:
            csv_text = await download_indices_csv(d)
            if csv_text is None:  # weekend/holiday/not-yet-published — skip, one request
                skipped += 1
            else:
                idx = await ingest_index_ohlcv_date(db, d, csv_text=csv_text)
                vix = await ingest_vix_date(db, d, csv_text=csv_text)
                if idx.get("status") == "ok" or vix.get("status") == "ok":
                    ok += 1
                    inserted = idx.get("inserted", 0)
                    idx_rows += inserted if isinstance(inserted, int) else 0
                    vix_rows += 1 if vix.get("inserted") else 0
                else:
                    skipped += 1
        except httpx.HTTPError as exc:
            print(
                f"[{i}/{total}] {d} — network failure, skipping (heals on re-run): {exc!r}",
                flush=True,
            )
            skipped += 1
        if i % 25 == 0 or i == total:
            print(
                f"[{i}/{total}] {d} — ok={ok} skipped={skipped} "
                f"index_rows={idx_rows} vix_rows={vix_rows}",
                flush=True,
            )
        await asyncio.sleep(delay)

    print(f"DONE ok={ok} skipped={skipped} index_rows={idx_rows} vix_rows={vix_rows}", flush=True)
    return 0


async def backfill(
    from_date: date, to_date: date, delay: float, db: AsyncSession | None = None
) -> int:
    """Backfill index OHLC + VIX over [from_date, to_date]. Opens its own session for
    script use; pass `db` to run inside an existing session (tests)."""
    if db is not None:
        return await _run(db, from_date, to_date, delay)
    async with AsyncSessionFactory() as own:
        return await _run(own, from_date, to_date, delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("from_date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("to_date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
    parser.add_argument("--delay", type=float, default=0.7, help="seconds between downloads")
    args = parser.parse_args()
    if args.from_date > args.to_date:
        print("from_date must be <= to_date", file=sys.stderr)
        return 2
    return asyncio.run(backfill(args.from_date, args.to_date, args.delay))


if __name__ == "__main__":
    raise SystemExit(main())
