"""Silent-feed-outage alarms — Phase 6.8.6 (staleness) + U4′ (coverage).

TWO independent questions about the same feeds, because one of them was answered
alone for a year and missed the outage it existed to catch:

  RECENCY  (6.8.6) — is the feed's newest row current with the trading calendar?
  COVERAGE (U4′)  — did it carry as many NAMES as it usually does?

A feed can be current and thin, stale and broad, or both; each verdict is reported
separately. The coverage half and the argument for it start at the "U4′ · coverage"
banner below.


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
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.fo_data import FoBhavcopy
from app.models.market_data import FiiDiiDaily, OhlcvDaily
from app.services.market_calendar import (
    is_trading_day,
    prev_trading_day,
    trading_days_between,
)

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from app.services.notifier import Notification

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


# ── U4′ · coverage ───────────────────────────────────────────────────────────────
#
# ⭐ WHY THIS EXISTS, AND WHY IT IS A SECOND MEASURE RATHER THAN A TUNED FIRST ONE.
# The 2026-09-07 universe outage froze daily bars for 1,278 names — every blue chip
# among them — for five sessions, and the staleness check above read ✅ throughout.
# It asserts RECENCY (`max(time)`) and is structurally incapable of asserting
# COVERAGE: a feed that halves its breadth overnight while still writing today's row
# is exactly the silent failure it exists to catch, and it cannot see it. Per the
# project's `instrument_self_validation` rule, an alarm never run against the failure
# it claims to cover has not been validated — so this ships with a regression test
# that FIRST reproduces the silence, then fires.
#
# ⛔⛔ COVERAGE IS MEASURED RAW, AND NEVER SCOPED TO THE TRADEABLE UNIVERSE. This is
# the single decision the detector turns on. Scoping the count to `stocks.is_active`
# makes the numerator and its own baseline share one mutable set: during the outage
# the active set WAS the thing that collapsed, so "active names with a bar today"
# (1,322) against "median active names with a bar" (1,322, the same survivors, which
# had bars all along) reads 100% healthy. That is not hypothetical — it is precisely
# why `funnel.py`'s breadth stage, which joins `is_active`, cannot serve as this
# detector, and `test_feed_coverage.py` pins both silences on one fixture.
#
# ⚠⚠ AND IT IS AN UNWEIGHTED COUNT, WHICH BOUNDS WHAT IT CAN SEE. The threshold is a
# fraction of the WHOLE archive (~2,637 names ⇒ ~264 must vanish). Measured 2026-09-14:
# the 50 active Nifty-50 constituents are 1.90% of that and all 210 active F&O
# underlyings are 7.96% — so an ingestion bug that drops EVERY blue chip, or every F&O
# name, sits UNDER the threshold and fires nothing. The funnel cannot see those either
# (they stay `is_active`). The 09-07 outage is written up as "1,278 names, every blue
# chip among them": it is the 1,278 this detects, not the blue chips. A per-segment or
# held-names check is a DIFFERENT instrument and is deliberately not built here.
#
# ⚠ SHORTFALL ONLY, NEVER GROWTH. D3 deliberately widened ingestion to every known
# NSE symbol; measured, that produced a +9.4% step against the trailing median in
# August 2026. A symmetric alarm would have fired on a correct change. The growth
# side is the universe materialiser's rail (`live_universe_max_count`) — a different
# instrument for a different failure. A feed's own job is to notice LOSS.
#
# ⚠ THE BASELINE IS 30 SESSIONS, NOT THE 5 THE SPEC ASKED FOR (§7/U4), and the
# arithmetic is the reason: a median is overtaken once half its window is collapsed,
# so a 5-session reference goes SILENT on the 4th session of a persistent outage (its
# prior five are then 3 collapsed and 2 healthy, so the median has already moved). The
# outage that motivated this ran 5 sessions unnoticed — an alarm that switches itself
# off inside the failure is worse than none. 30 sessions keeps it up for ~16.
# `check_feed_coverage` takes the window as an argument so a test can demonstrate
# both, rather than leaving the choice as an assertion.
#
# ⚠ FEEDS WITHOUT A NAME DIMENSION ARE ABSENT HERE, NOT ZERO. `fii_dii_daily` holds
# one aggregate row per session; it HAS no breadth, so it carries no coverage row and
# the rendered line names exactly which feeds were measured (A24).

#: Sessions the breadth reference is taken over. See the note above for why not 5.
COVERAGE_BASELINE_SESSIONS = 30
#: Below this many prior sessions a median means nothing — report "not assessable"
#: (A24) rather than alarming on a reference built from two numbers.
COVERAGE_MIN_BASELINE_SESSIONS = 5


@dataclass(frozen=True)
class FeedCoverage:
    """How many NAMES a feed carried on its latest session, against its own recent
    normal. Independent of `FeedStatus`: a feed can be current and thin (the 09-07
    failure), stale and broad (a missed cycle), or both."""

    name: str  # human label
    table: str  # underlying table
    session: date | None  # the session measured — the feed's own latest
    names: int | None  # distinct names carrying a row in that session
    baseline: int | None  # median names over the prior sessions; None = unjudgeable
    baseline_sessions: int  # how many prior sessions the median rests on
    min_fraction: float  # the threshold this verdict was taken against

    @property
    def is_measurable(self) -> bool:
        """A count without a reference is decoration (A24)."""
        return self.names is not None and bool(self.baseline)

    @property
    def shortfall_pct(self) -> float | None:
        """How far below its own normal the feed sits. Negative = broader than usual."""
        if not self.is_measurable:
            return None
        assert self.names is not None and self.baseline  # narrowed by is_measurable
        return round((1.0 - self.names / self.baseline) * 100.0, 1)

    @property
    def deviation_pct(self) -> float | None:
        """The same quantity signed the way a reader expects when it is NOT an alarm:
        positive = broader than normal. `shortfall_pct` is signed for the alarm line,
        where the label says "below"; rendering that one in a healthy summary prints
        `-0.3%` for a feed that is doing BETTER than usual."""
        pct = self.shortfall_pct
        if pct is None:
            return None
        # ⚠ `-0.0` is a real float and `:+.1f` renders it "-0.0%" — a minus sign on a
        # feed that is exactly normal, which is the one thing this property exists to
        # prevent. Observed live on `fo_bhavcopy` (216 names vs a 216 median).
        return 0.0 if pct == 0 else -pct

    @property
    def is_collapsed(self) -> bool:
        # ⚠ The `min_fraction <= 0` arm is DEFENSIVE AND CURRENTLY UNREACHABLE AS
        # BEHAVIOUR: `is_measurable` already forces `baseline >= 1`, and the SQL cannot
        # emit a session with a zero count, so `names < baseline * 0` is False by
        # arithmetic anyway. It is kept because "0 disables" is a documented contract in
        # `.env.example` and a later change to the comparison must not silently revoke it
        # — but no test can separate it from the arithmetic, and pretending otherwise
        # would be a hollow pin (test-guardian, 2026-09-14).
        if not self.is_measurable or self.min_fraction <= 0:
            return False
        assert self.names is not None and self.baseline
        return self.names < self.baseline * self.min_fraction


# Two feeds carry a name dimension, and their shapes differ enough that an explicit
# statement each is clearer — and safer — than a table-name template. No identifier
# here is caller-supplied, so there is no interpolation to guard.
_COVERAGE_SQL_OHLCV_1D = """
WITH latest AS (
    SELECT max((time AT TIME ZONE 'UTC')::date) AS d
      FROM ohlcv_1d
     -- ⚠ One future-dated row (a misparsed vendor date) would otherwise become `latest`,
     -- leaving the window holding a single session, no baseline, and therefore a "not
     -- assessable" line INSTEAD of an alarm — quiet in the wrong direction.
     WHERE time < (current_date + 2)::timestamptz
)
SELECT (time AT TIME ZONE 'UTC')::date AS d, count(DISTINCT stock_id) AS n
  FROM ohlcv_1d
 -- Filter on `time` itself so Timescale can still exclude chunks; `AT TIME ZONE 'UTC'`
 -- pins the boundary rather than inheriting whatever the session TimeZone happens to be
 -- (the app pins no `server_settings`).
 WHERE time >= ((SELECT d FROM latest) - make_interval(days => :window)) AT TIME ZONE 'UTC'
   AND time < (current_date + 2)::timestamptz
 GROUP BY 1 ORDER BY 1 DESC LIMIT :limit
"""

_COVERAGE_SQL_FO_BHAVCOPY = """
WITH latest AS (
    -- `+ 2`, matching the equity statement: between 00:00 and 05:30 IST the host's
    -- date is a day ahead of Postgres's `current_date` (the server runs UTC), and
    -- `+ 1` sat exactly on that boundary with no margin.
    SELECT max(trade_date) AS d FROM fo_bhavcopy WHERE trade_date <= current_date + 2
)
SELECT trade_date AS d, count(DISTINCT symbol) AS n
  FROM fo_bhavcopy
 WHERE trade_date >= ((SELECT d FROM latest) - make_interval(days => :window))::date
   AND trade_date <= current_date + 2
 GROUP BY 1 ORDER BY 1 DESC LIMIT :limit
"""


async def _coverage_series(
    db: AsyncSession, sql: str, *, baseline_sessions: int
) -> list[tuple[date, int]]:
    """The feed's last `baseline_sessions + 1` sessions, newest first, as
    (session, distinct names). Bounded by a calendar window so the aggregate reads
    recent chunks only — generous enough (2x + 10 days) to span weekends, holidays
    and a short exchange break without ever truncating the reference silently."""
    rows = (
        await db.execute(
            text(sql),
            {"window": baseline_sessions * 2 + 10, "limit": baseline_sessions + 1},
        )
    ).all()
    return [(r.d, int(r.n)) for r in rows]


def _coverage_from_series(
    name: str, table: str, series: list[tuple[date, int]], min_fraction: float
) -> FeedCoverage:
    """⚠ The measured session is EXCLUDED from its own baseline — a reference that
    contains the observation it judges is dragged toward it by exactly the drop the
    alarm is looking for."""
    if not series:
        return FeedCoverage(name, table, None, None, None, 0, min_fraction)
    session, names = series[0]
    prior = [n for _, n in series[1:]]
    baseline = (
        round(statistics.median(prior)) if len(prior) >= COVERAGE_MIN_BASELINE_SESSIONS else None
    )
    return FeedCoverage(name, table, session, names, baseline, len(prior), min_fraction)


async def check_feed_coverage(
    db: AsyncSession,
    *,
    baseline_sessions: int = COVERAGE_BASELINE_SESSIONS,
    min_fraction: float | None = None,
) -> list[FeedCoverage]:
    """Breadth of each name-carrying EOD feed vs its own trailing median. Read-only, and
    NEVER raises: a feed whose probe fails degrades to "not assessable", never to green.

    Logs a warning per collapsed feed, so a collapse lands in the log as well as in the
    report — and `app.tasks.health_tasks.check_feed_coverage` turns the same verdict into
    a push, which is what makes this a detector rather than a report section."""
    threshold = settings.feed_coverage_min_fraction if min_fraction is None else min_fraction
    feeds = [
        ("Equity EOD", "ohlcv_1d", _COVERAGE_SQL_OHLCV_1D),
        ("F&O bhavcopy", "fo_bhavcopy", _COVERAGE_SQL_FO_BHAVCOPY),
    ]
    out: list[FeedCoverage] = []
    for label, table, sql in feeds:
        try:
            # ⭐ PER FEED, and inside a SAVEPOINT. Two separate reasons, both learned here:
            # a probe that can take down its own report has inverted its purpose
            # (`calendar_health.read_calendar_status` states the rule, and this is read by
            # `build_daily_report` — an exception here would have killed the whole
            # `make analysis` run INCLUDING the staleness alarm rendered directly above);
            # and a failed statement poisons the enclosing transaction, so without the
            # savepoint the first broken feed would blind the second and everything the
            # report does afterwards. Same fail-open-in-a-`begin_nested` shape the
            # order-path overlays use. Degrades to "not assessable" (A24), never to green.
            async with db.begin_nested():
                series = await _coverage_series(db, sql, baseline_sessions=baseline_sessions)
        except Exception:  # noqa: BLE001 — a health probe must not raise into its own report
            log.exception(
                "FEED COVERAGE probe failed for %s (%s); reporting as not assessable",
                label, table,
            )
            out.append(FeedCoverage(label, table, None, None, None, 0, threshold))
            continue
        cov = _coverage_from_series(label, table, series, threshold)
        if cov.is_collapsed:
            log.warning(
                "FEED COVERAGE COLLAPSE: %s (%s) carried %s names on %s vs a %s median "
                "over the prior %s sessions — %s%% below (threshold %s%%)",
                label, table, cov.names, cov.session, cov.baseline,
                cov.baseline_sessions, cov.shortfall_pct,
                round((1 - threshold) * 100, 1),
            )
        out.append(cov)
    return out


def coverage_to_notification(rows: list[FeedCoverage]) -> Notification | None:
    """The proactive push (A11), or None when there is nothing worth a human's attention.

    ⭐ WHY THIS EXISTS AT ALL. Before it, `check_feed_coverage` had exactly one caller —
    `build_daily_report` — whose only caller is `make analysis`, run by hand. So the
    "loud" `log.warning` could only ever fire inside a report a human had already chosen
    to read, and a collapse on a day nobody ran it was never seen: the detector examines
    the newest session only, and that session then joins the baseline. A primary
    detector that waits to be asked is not a detector (bug-hunter, 2026-09-14).

    Deferred notifier import, matching `calendar_health.to_notification`."""
    from app.services.notifier import Level, Notification

    collapsed = [r for r in rows if r.is_collapsed]
    if not collapsed:
        return None
    worst = max(collapsed, key=lambda r: r.shortfall_pct or 0.0)
    lines = [
        f"{r.name} ({r.table}): {r.names:,} names on {r.session} vs a {r.baseline:,} "
        f"median over {r.baseline_sessions} sessions — {r.shortfall_pct}% below"
        for r in collapsed
    ]
    lines.append(
        "the feed is CURRENT but THIN — the staleness alarm cannot see this "
        "(it asserts recency, not coverage)"
    )
    lines.append("REMEDY: check the universe rule (materialise-universe) and the EOD ingest")
    return Notification(
        # Stable key — the notifier throttles on it, so a persistent collapse pushes
        # once per window rather than once per beat.
        event="feed_coverage",
        level=Level.ERROR,
        title=f"FEED COVERAGE COLLAPSE — {worst.name} {worst.shortfall_pct}% below normal",
        lines=lines,
    )


def render_feed_coverage(rows: list[FeedCoverage]) -> list[str]:
    """Daily-report header. A loud blockquote when a current feed has gone thin; a
    quiet one-liner naming what was measured and against what, otherwise."""
    if not rows:
        return []
    collapsed = [r for r in rows if r.is_collapsed]
    measured = [r for r in rows if r.is_measurable]
    unjudgeable = [r for r in rows if not r.is_measurable]
    out: list[str] = []
    if collapsed:
        out += [
            "> ## ⚠️ FEED COVERAGE ALARM (live — as of report generation)",
            ">",
            # ⚠ Not "today's session": this check reads no clock and no calendar, only
            # the feed's own max. A feed five sessions STALE whose last written session
            # was also thin lands here too, and saying "today" would misreport it.
            "> A feed is **current in shape but THIN** — it wrote its latest session while "
            "carrying far fewer names than its own recent normal. This is the 2026-09-07 "
            "failure mode, and the staleness alarm cannot see it: that one asserts "
            "recency, this one asserts coverage. Check the universe rule and the "
            "ingestion path before trusting any breadth-dependent number below.",
            ">",
        ]
        for r in collapsed:
            out.append(
                f"> - **{r.name}** (`{r.table}`): **{r.names:,}** names on {r.session} vs a "
                f"**{r.baseline:,}** median over the prior {r.baseline_sessions} sessions "
                f"— **{r.shortfall_pct}% below** (alarms past "
                f"{round((1 - r.min_fraction) * 100, 1)}%)."
            )
        # ⭐ The healthy feeds are named INSIDE the alarm too. Putting this summary in an
        # `else` meant that the moment any feed alarmed, every other feed's verdict
        # vanished from the report — leaving "checked and fine" indistinguishable from
        # "not checked at all", which is the exact A24 failure this module claims to
        # avoid two paragraphs up (bug-hunter, 2026-09-14).
        healthy = [r for r in measured if not r.is_collapsed]
        if healthy:
            out.append(
                "> - Also measured, and normal: "
                + " · ".join(f"{r.name} {r.names:,} vs {r.baseline:,} median" for r in healthy)
                + "."
            )
        out.append("")
    elif measured:
        summary = " · ".join(
            f"{r.name} {r.names:,} vs {r.baseline:,} median over {r.baseline_sessions} "
            f"sessions ({r.deviation_pct:+.1f}%)"
            for r in measured
        )
        out += [f"> ✅ **Feed breadth normal** (vs each feed's own median): {summary}.", ""]
    for r in unjudgeable:
        # A24 — "not assessable" is a legitimate rendering and beats implying zero.
        reason = (
            "no data at all"
            if r.names is None
            else f"only {r.baseline_sessions} prior session(s); needs "
            f"≥ {COVERAGE_MIN_BASELINE_SESSIONS}"
        )
        out += [f"> ⚠ **Breadth not assessable** for {r.name} (`{r.table}`): {reason}.", ""]
    return out
