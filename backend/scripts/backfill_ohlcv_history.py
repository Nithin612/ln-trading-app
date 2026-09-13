"""Extend `ohlcv_1d` backwards from the NSE bhavcopy archive.

    uv run python scripts/backfill_ohlcv_history.py --start 2019-10-01 --end 2023-07-02
    uv run python scripts/backfill_ohlcv_history.py --start 2019-10-01 --limit 5 --dry-run

## Why

`ohlcv_1d` begins **2023-07-03** — about 3.2 years, and all of it one broad regime. Every
trial we run (factor sweeps, walk-forwards, regime tests) is measured against that single
sample, which is the standing objection to all of them. The Q5 sourcing spike established
that the `sec_bhavdata_full` archive serves back to roughly **2019-10-01** (2019-09-02
returns 404, 2019-10-01 returns 200), so this takes us to ~7 years **including the COVID
crash** — the most violent regime change available to us.

## ⭐ Survivorship safety is the point, not a side effect

Run with `historical=True`, so a symbol the bhavcopy names but `stocks` has never heard of
is CREATED as an inactive historical stock. Our `stocks` table is a *today* snapshot from
Kite instruments; without this, every company that delisted or was wound up between 2019
and now would be silently missing and the reconstructed universe would contain only
survivors. That flatters results in exactly the direction that would make us confident.

A bhavcopy is the day's trading record — it lists what traded THAT day — so the
point-in-time universe falls out of ingesting the files. See `_ensure_historical_stocks`.

## ⚠ Limits you must carry into any study built on this data

- **Prices are UNADJUSTED for corporate actions.** This is not new — daily ingestion has
  always stored raw bhavcopy prices — but over 7 years there are far more splits and
  bonuses, and each one appears as a large overnight gap that is not a tradeable move. Any
  multi-year backtest MUST handle that or it will find spectacular fake edges. We have a
  `corporate_actions` table but no historical CA history for these names.
- **EQ series only**, matching daily ingestion and the T2T ruling (`-BE`/`-BZ`/`-T2T`
  names get no EOD bars). Consistent, but it means a name that moved to T2T disappears
  rather than continuing.
- **Symbol churn is not resolved.** A company that renamed appears as two unrelated
  symbols. `LIKE 'sym-%'` before concluding a symbol vanished (the T2T lesson).
- **This changes no recorded number.** It adds historical bars; it does not touch any
  position, signal or P&L, so it is safe to run during cycle-1 accrual.

## Resumability

The run is long and network-bound, so it is **idempotent and resumable**: dates that
already hold a full day of bars are skipped before any request is made, and the insert is
`ON CONFLICT DO NOTHING`. Interrupt it and re-run with the same arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.bhavcopy_service import (  # noqa: E402
    _NSE_HEADERS,
    ingest_bhavcopy_date,
)
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

# ⛔ U15 (2026-09-13). This was a FIXED floor of 500 rows, and a fixed floor can only
# see a MISSING session — never a THIN one. On 2026-09-07 → 09-11 five sessions were
# ingested at ~1,170 rows against a normal ~2,630 (the universe outage), and every one
# of them cleared 500: running this script over that range printed "nothing to fetch —
# range already complete" and did nothing. The repair had to bypass it.
#
# ⭐ Same blindness as the 6.8.6 feed alarm and `load_frames`: an instrument asserting
# PRESENCE where the failure mode is COVERAGE. So completeness is now judged against the
# MEDIAN SESSION ALREADY PRESENT IN THE REQUESTED RANGE, not a constant — a session holding
# less than this fraction of it is treated as partial and re-fetched.
#
# ⚠ It is the median of the WHOLE range, not a local window. A range spanning eras of
# different breadth (2019 carried ~1,700 EQ rows a day, 2026 carries ~2,630) therefore
# judges the thin era against a blended median and re-fetches some legitimately-complete
# early sessions. That is WASTE, not corruption — the ingest is idempotent
# (`ON CONFLICT DO NOTHING`) — and it is bounded by one HTTP request per affected day.
# Pass `--min-rows` to pin the bar explicitly when backfilling across eras.
#
# ⚠ Raising the constant would reproduce the defect at a new threshold; the point is that
# no constant can be right for a quantity that grows with the listed universe.
_COMPLETE_DAY_FRACTION = 0.80
# Floor for the degenerate cases the median cannot serve: an empty range, or one whose own
# median is itself depressed. Kept deliberately low — it is a backstop, not the test.
_COMPLETE_DAY_ROWS = 500

# The archive's own floor, established by probing in the Q5 sourcing spike: 2019-09-02
# (a Monday, so not a holiday artefact) 404s and 2019-10-01 serves.
ARCHIVE_START = date(2019, 10, 1)


def complete_day_threshold(
    counts: list[int], fraction: float = _COMPLETE_DAY_FRACTION, floor: int = _COMPLETE_DAY_ROWS
) -> int:
    """Rows a session must hold to count as complete, from the range's own shape.

    Pure, so the rule is testable without a database. Returns the larger of the
    absolute floor and `fraction` × the median session in `counts`; an empty range
    falls back to the floor.
    """
    if not counts:
        return floor
    ordered = sorted(counts)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) // 2
    return max(floor, int(median * fraction))


async def _already_done(start: date, end: date, min_rows: int | None = None) -> set[date]:
    """Dates that already hold a full day of bars, so no request is made for them.

    "Full" is measured against the range's own trailing median unless `min_rows`
    overrides it — see `_COMPLETE_DAY_FRACTION`.
    """
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT time::date AS d, count(*) AS n FROM ohlcv_1d"
                    " WHERE time >= :s AND time < :e GROUP BY 1"
                ),
                {
                    "s": datetime(start.year, start.month, start.day, tzinfo=UTC),
                    "e": datetime(end.year, end.month, end.day, tzinfo=UTC)
                    + timedelta(days=1),
                },
            )
        ).fetchall()
        counts = [int(r.n) for r in rows]
        threshold = min_rows if min_rows is not None else complete_day_threshold(counts)
        thin = [(r.d, int(r.n)) for r in rows if int(r.n) < threshold]
        if thin:
            print(
                f"  {len(thin)} session(s) below the completeness threshold "
                f"({threshold} rows) will be RE-FETCHED: "
                + ", ".join(f"{d} ({n})" for d, n in sorted(thin)[:8])
                + ("…" if len(thin) > 8 else ""),
                flush=True,
            )
        return {r.d for r in rows if int(r.n) >= threshold}


def _weekdays(start: date, end: date) -> list[date]:
    """Every Mon-Fri in the range. Holidays are not enumerated — the archive answers 404
    for them, which is indistinguishable from a holiday and handled the same way."""
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


@dataclass
class RunStats:
    ok: int = 0
    holiday: int = 0
    failed: int = 0
    inserted: int = 0
    first_err: str | None = None


async def _fetch_all(todo: list[date], sleep: float) -> RunStats:
    """Walk the dates, one HTTP session and one DB session per date.

    A 7-year run must not hold a single transaction open, and committing per day is
    exactly what makes an interrupted run resumable. One bad day is logged and stepped
    over rather than ending the run — with a longer backoff, since the usual cause is
    NSE rate-limiting us.
    """
    st = RunStats()
    async with httpx.AsyncClient(
        headers=_NSE_HEADERS, timeout=60, follow_redirects=True
    ) as client:
        # NSE sets a cookie on the landing page that the archive host then expects.
        # Primed ONCE for the whole run rather than per date.
        try:
            await client.get("https://www.nseindia.com/", timeout=15)
        except httpx.HTTPError:
            pass

        for i, d in enumerate(todo, 1):
            try:
                async with AsyncSessionFactory() as db:
                    res = await ingest_bhavcopy_date(db, d, historical=True, client=client)
            except Exception as exc:  # noqa: BLE001 — one bad day must not end the run
                st.failed += 1
                if st.first_err is None:
                    st.first_err = f"{d}: {type(exc).__name__}: {exc}"
                print(f"  [{i}/{len(todo)}] {d} FAILED {type(exc).__name__}: {exc}", flush=True)
                await asyncio.sleep(sleep * 3)
                continue

            if res.status == "ok":
                st.ok += 1
                st.inserted += res.rows_inserted
                print(
                    f"  [{i}/{len(todo)}] {d} +{res.rows_inserted} bars "
                    f"({res.rows_skipped} skipped)",
                    flush=True,
                )
            else:
                st.holiday += 1
                print(f"  [{i}/{len(todo)}] {d} — {res.message}", flush=True)

            await asyncio.sleep(sleep)
    return st


async def _run(args: argparse.Namespace) -> int:
    start, end = args.start, args.end
    if start < ARCHIVE_START:
        print(
            f"⚠ {start} is before the archive floor {ARCHIVE_START} — those dates 404. "
            f"Clamping to {ARCHIVE_START}.",
            flush=True,
        )
        start = ARCHIVE_START
    if start > end:
        print(f"nothing to do: start {start} is after end {end}")
        return 1

    done = await _already_done(start, end, args.min_rows)
    todo = [d for d in _weekdays(start, end) if d not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(
        f"range {start} → {end}: {len(todo)} weekdays to fetch "
        f"({len(done)} already complete)",
        flush=True,
    )
    if args.dry_run:
        print("dry run — no requests made. First 10:", [str(d) for d in todo[:10]])
        return 0
    if not todo:
        print("nothing to fetch — range already complete")
        return 0

    st = await _fetch_all(todo, args.sleep)

    async with AsyncSessionFactory() as db:
        span = (
            await db.execute(
                text(
                    "SELECT min(time)::date AS lo, max(time)::date AS hi,"
                    " count(*) AS bars, count(DISTINCT stock_id) AS names,"
                    " count(DISTINCT time::date) AS days FROM ohlcv_1d"
                )
            )
        ).one()
        hist = (
            await db.execute(
                text("SELECT count(*) AS n FROM stocks WHERE is_active = false")
            )
        ).scalar_one()

    now = datetime.now(UTC).astimezone(_IST)
    lines = [
        f"# `ohlcv_1d` history backfill ({now.date()})",
        "",
        f"Requested **{start} → {end}**; {len(todo)} weekdays fetched this run.",
        "",
        "| outcome | days |",
        "|---|--:|",
        f"| ingested | {st.ok} |",
        f"| holiday / not published (404) | {st.holiday} |",
        f"| failed | {st.failed} |",
        "",
        f"**{st.inserted:,} bars inserted this run.**",
        "",
        "## `ohlcv_1d` now",
        "",
        f"- **{span.lo} → {span.hi}** — {span.days:,} trading days",
        f"- {span.bars:,} bars across {span.names:,} distinct names",
        f"- {hist:,} inactive stocks (delisted/historical names carrying the point-in-time",
        "  universe — see `_ensure_historical_stocks`)",
        "",
        "## ⚠ Carry these into any study built on this data",
        "",
        "- **Prices are UNADJUSTED for corporate actions.** Over 7 years every split and",
        "  bonus reads as a large overnight gap that is not a tradeable move. A multi-year",
        "  backtest must handle this or it will find spectacular fake edges.",
        "- **EQ series only** — consistent with daily ingestion and the T2T ruling, but a",
        "  name that moved to T2T disappears rather than continuing.",
        "- **Symbol churn is unresolved** — a renamed company appears as two unrelated",
        "  symbols. Check `LIKE 'sym-%'` before concluding a symbol vanished.",
        "- **No recorded number changed.** This adds historical bars only.",
    ]
    if st.first_err:
        lines += ["", f"First failure: `{st.first_err}`"]

    report = "\n".join(lines)
    print("\n" + report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"ohlcv-backfill-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0 if st.failed == 0 else 1


def _date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=_date, default=ARCHIVE_START)
    p.add_argument("--end", type=_date, default=date(2023, 7, 2))
    p.add_argument("--limit", type=int, default=0, help="stop after N dates (a smoke run)")
    p.add_argument("--sleep", type=float, default=1.0, help="seconds between requests")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--min-rows",
        type=int,
        default=None,
        help="override the completeness threshold (default: 80%% of the range's median session)",
    )
    return asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
