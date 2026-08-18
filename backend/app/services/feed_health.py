"""Silent-feed-outage alarm — Phase 6.8.6.

The month-long v2-era EOD outage (ingestion frozen 07-02→07-17, found by accident)
is the cautionary tale. EOD tasks self-heal (≤21d) now, but nothing LOUDLY flags a
feed gone stale — today we find out by reading §7/§8 of the daily report. This is
the staleness check: for each EOD feed, how many TRADING days behind is its latest
row versus the last completed EOD cycle? Trading-calendar aware — a weekend or
holiday is not an outage, and a pre-EOD morning run doesn't yet expect today's row.

A staleness check, not a metrics stack (the review's Prometheus idea is
over-engineering for a solo platform). Loud output: a daily-report header + a
`log.warning` per stale feed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fo_data import FoBhavcopy
from app.models.market_data import FiiDiiDaily, OhlcvDaily
from app.services.market_calendar import (
    is_trading_day,
    prev_trading_day,
    trading_days_between,
)

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")
# EOD ingestion beats fire 18:30–18:45 IST; before that, TODAY's EOD isn't due yet.
_EOD_DUE_IST = time(18, 45)


@dataclass(frozen=True)
class FeedStatus:
    name: str  # human label
    table: str  # underlying table
    latest: date | None  # newest row's trade date, or None if the feed is empty
    expected: date  # the last completed EOD cycle we should have by now
    days_behind: int | None  # 0 = current; None = no data at all (maximally stale)

    @property
    def is_stale(self) -> bool:
        return self.days_behind is None or self.days_behind >= 1


async def _latest_ohlcv_1d(db: AsyncSession) -> date | None:
    """Newest daily-bar trade date. `ohlcv_1d.time` is tz-aware at the trade date's
    UTC — the trade date is its UTC date (matching ca_detector's convention)."""
    dt = (await db.execute(select(func.max(OhlcvDaily.time)))).scalar()
    return dt.astimezone(UTC).date() if dt is not None else None


async def _latest_trade_date(db: AsyncSession, column: Any) -> date | None:
    latest: date | None = (await db.execute(select(func.max(column)))).scalar()
    return latest


async def _expected_latest_trading_day(db: AsyncSession, now_ist: datetime) -> date:
    """The most recent trading day whose EOD is DUE as of `now`: today if it's a
    trading day past the ingestion window (18:45 IST), else the previous trading
    day. So a weekend/holiday — or a pre-EOD morning run — expects only through the
    last completed cycle, never raising a false alarm for data that isn't due yet."""
    d = now_ist.date()
    if now_ist.time() >= _EOD_DUE_IST and await is_trading_day(db, d):
        return d
    return await prev_trading_day(db, d)


async def _days_behind(db: AsyncSession, latest: date | None, expected: date) -> int | None:
    """Trading days MISSING between the feed's latest row and the expected cycle:
    the count of trading days STRICTLY AFTER `latest` up to and including `expected`.
    None if the feed is empty; 0 when current. Counting from `latest + 1` (rather
    than subtracting `latest` from an inclusive range) is robust when `latest` is
    itself NOT a trading day — a backfilled weekend row, or a holiday seeded after
    the row was written — where subtracting a not-in-range endpoint would erase a
    genuinely-missing day and under-report the outage (bug-hunter LOW, 2026-08-18)."""
    if latest is None:
        return None
    if latest >= expected:
        return 0
    return len(await trading_days_between(db, latest + timedelta(days=1), expected))


async def check_feed_staleness(
    db: AsyncSession, *, now: datetime | None = None
) -> list[FeedStatus]:
    """Staleness of each EOD feed vs the trading calendar. Logs a warning per stale
    feed (loud even without the report). Read-only."""
    now_ist = (now or datetime.now(UTC)).astimezone(_IST)
    expected = await _expected_latest_trading_day(db, now_ist)
    feeds: list[tuple[str, str, date | None]] = [
        ("Equity EOD", "ohlcv_1d", await _latest_ohlcv_1d(db)),
        ("F&O bhavcopy", "fo_bhavcopy", await _latest_trade_date(db, FoBhavcopy.trade_date)),
        ("FII/DII flows", "fii_dii_daily", await _latest_trade_date(db, FiiDiiDaily.trade_date)),
    ]
    out: list[FeedStatus] = []
    for name, table, latest in feeds:
        behind = await _days_behind(db, latest, expected)
        status = FeedStatus(
            name=name, table=table, latest=latest, expected=expected, days_behind=behind
        )
        if status.is_stale:
            log.warning(
                "FEED STALE: %s (%s) latest=%s expected>=%s — %s trading day(s) behind",
                name, table, latest, expected,
                "NO DATA" if behind is None else behind,
            )
        out.append(status)
    return out


def render_feed_health(rows: list[FeedStatus]) -> list[str]:
    """Daily-report header. A quiet one-line confirmation when all feeds are current;
    a loud, un-missable blockquote alarm when any is behind."""
    if not rows:
        return []
    stale = [r for r in rows if r.is_stale]
    if not stale:
        summary = " · ".join(f"{r.name} {r.latest}" for r in rows)
        # "as of generation" — this is a LIVE check, not the report day's state (a
        # historical `make analysis DATE=…` run still reflects feed health right now).
        return [
            f"> ✅ **Feeds current as of report generation** (≥ {rows[0].expected}): {summary}.",
            "",
        ]
    out = [
        "> ## ⚠️ FEED STALENESS ALARM (live — as of report generation)",
        ">",
        "> One or more EOD feeds are behind the trading calendar — the 07-02→07-17 "
        "silent-outage failure mode. Check ingestion (worker + Kite token) before "
        "trusting today's numbers; the self-healer catches ≤21 days.",
        ">",
    ]
    for r in stale:
        behind = (
            "**NO DATA AT ALL**"
            if r.days_behind is None
            else f"**{r.days_behind}** trading day(s) behind"
        )
        out.append(
            f"> - **{r.name}** (`{r.table}`): latest {r.latest or '—'}, expected ≥ "
            f"{r.expected} — {behind}"
        )
    out.append("")
    return out
