"""U4′ — the coverage-aware feed alarm.

The 6.8.6 staleness check read ✅ throughout the 2026-09-07 universe outage, which
froze daily bars for 1,278 names — every blue chip among them — across five sessions.
These tests exist because of that, and the centrepiece is built the way the project's
`instrument_self_validation` rule demands: on ONE fixture it first reproduces the
SILENCE of both instruments that already existed, and only then asserts that the new
one fires. An alarm never run against the failure it claims to cover has not been
validated.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.config import get_settings
from app.models.fo_data import FoBhavcopy
from app.models.market_data import FiiDiiDaily, OhlcvDaily
from app.models.stock import Stock
from app.services import feed_health
from app.services.daily_report import build_daily_report, render_markdown
from app.services.feed_health import (
    COVERAGE_BASELINE_SESSIONS,
    COVERAGE_MIN_BASELINE_SESSIONS,
    FeedCoverage,
    FeedStatus,
    _coverage_from_series,
    check_feed_coverage,
    check_feed_staleness,
    coverage_to_notification,
    render_feed_coverage,
    render_feed_health,
)
from app.services.funnel import load_funnel
from app.services.notifier import Level
from app.tasks.health_tasks import _coverage_alert_payload
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user

_IST = ZoneInfo("Asia/Kolkata")


def _recent_sessions(count: int) -> list[date]:
    """`count` weekday sessions ending at the most recent weekday on or before today,
    oldest first.

    ⚠ Anchored to the real clock on purpose: `funnel.load_funnel` windows its breadth
    reference on `now()`, so a fixture seeded at fixed 2026 dates would drift out of
    that window as the calendar moves and the blindness half of the acceptance test
    would stop measuring anything. The coverage check itself reads only the feed's own
    max session and is indifferent to the wall clock."""
    out: list[date] = []
    d = date.today()
    while len(out) < count:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


async def _make_stocks(db: AsyncSession, n: int, *, active: int) -> list[Stock]:
    """`n` stocks of which the first `active` are in the tradeable universe.

    ⚠ `is_active` is set at INSERT: the D2′b single-writer trigger is BEFORE UPDATE,
    so seeding is unaffected, but flipping a row afterwards would be refused."""
    rows = [
        Stock(symbol=f"COV{i:04d}", exchange="NSE", company_name=f"Coverage Test {i}",
              lot_size=1, is_active=i < active)
        for i in range(n)
    ]
    db.add_all(rows)
    await db.flush()
    return rows


async def _seed_bars(db: AsyncSession, stock_ids: list[int], sessions: list[date]) -> None:
    payload = [
        {"time": datetime(d.year, d.month, d.day, tzinfo=UTC), "stock_id": sid,
         "open": Decimal("100"), "high": Decimal("101"), "low": Decimal("99"),
         "close": Decimal("100"), "volume": 1000, "is_complete": True}
        for d in sessions for sid in stock_ids
    ]
    if payload:
        await db.execute(insert(OhlcvDaily), payload)


def _equity(rows: list[FeedCoverage]) -> FeedCoverage:
    return next(r for r in rows if r.table == "ohlcv_1d")


def _equity_status(rows: list[FeedStatus]) -> FeedStatus:
    return next(r for r in rows if r.table == "ohlcv_1d")


class TestOutageAcceptance:
    """§7/U4's stated acceptance: replay the breadth collapse, assert the alarm fires."""

    async def test_replays_the_outage_where_both_existing_instruments_are_silent(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """⭐ THE ACCEPTANCE TEST. 40 names priced for 31 sessions; on the 32nd only
        the 20 that are still `is_active` get a bar — the exact 2026-09-07 mechanism,
        since `bhavcopy_service` writes bars for active names only.

        Three assertions on one fixture, in the order that makes the case:
          1. ⛔ the 6.8.6 STALENESS alarm is silent — the feed is current, only thin;
          2. ⛔ the V1 FUNNEL's breadth stage is silent too, because it joins
             `is_active`, so its numerator and its own baseline collapsed together;
          3. ✅ the coverage alarm fires at ~50% below its reference.
        """
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=20)
        survivors = [s.id for s in stocks[:20]]
        await _seed_bars(db, [s.id for s in stocks], sessions[:-1])
        await _seed_bars(db, survivors, sessions[-1:])  # the collapse
        # The other two EOD feeds stay current, so the staleness header below reads
        # green in FULL — reproducing the 2026-09-12 report line verbatim in shape
        # ("✅ Feeds current … Equity EOD 2026-09-11") while half the universe was
        # five sessions stale. A partially-seeded fixture would have alarmed for an
        # unrelated reason and the reproduction would have proved nothing.
        db.add(FoBhavcopy(trade_date=sessions[-1], symbol="NIFTY", instrument="FUT",
                          expiry_date=sessions[-1], strike=Decimal("0")))
        db.add(FiiDiiDaily(trade_date=sessions[-1], investor_type="FII", segment="cash",
                           buy_value_cr=Decimal("100.00"), sell_value_cr=Decimal("90.00")))
        await db.commit()

        # ── 1. the instrument that existed: RECENCY. Silent, correctly — the feed
        #       wrote today's session. It has no way to ask how MUCH it wrote.
        at_1900_ist = datetime.combine(sessions[-1], time(19, 0), tzinfo=_IST)
        stale = await check_feed_staleness(db, now=at_1900_ist)
        assert _equity_status(stale).days_behind == 0
        assert all(not r.is_stale for r in stale)
        header = "\n".join(render_feed_health(stale))
        assert "Feeds current" in header and "STALENESS ALARM" not in header

        # ── 2. the other instrument that existed: the V1 funnel. ⛔ Also silent, and
        #       this is the structural reason coverage must NOT be scoped to the
        #       universe: 20 active names priced today against a median of 20 active
        #       names priced per session reads perfectly healthy.
        funnel = await load_funnel(db)
        assert funnel.priced_today == 20
        assert funnel.breadth_median == 20
        assert funnel.breadth_shortfall_pct == 0.0

        # ── 3. the new instrument: COVERAGE, measured raw. Fires.
        caplog.set_level(logging.WARNING)
        cov = _equity(await check_feed_coverage(db))
        assert cov.session == sessions[-1]
        assert cov.names == 20  # raw — not the 20-name universe's own view of itself
        assert cov.baseline == 40
        # 31 prior sessions were seeded; the reference is capped at
        # COVERAGE_BASELINE_SESSIONS, and it reports what it actually rests on (H11).
        assert cov.baseline_sessions == COVERAGE_BASELINE_SESSIONS == 30
        assert cov.shortfall_pct == 50.0
        assert cov.is_collapsed

        md = "\n".join(render_feed_coverage([cov]))
        assert "FEED COVERAGE ALARM" in md
        # ⚠ Bolded forms, not bare "20"/"40": a bare digit pair matches any date in the
        # rendered line, so the loose version passed on a renderer printing nothing
        # (test-guardian, 2026-09-14).
        assert "**20** names" in md and "**40** median" in md and "50.0% below" in md
        # Loud without the report, too — and the VALUES must be in the log line, not just
        # the prefix; a warning formatting the wrong numbers is not an alarm.
        warning = next(r for r in caplog.records if "FEED COVERAGE COLLAPSE" in r.message)
        rendered = warning.getMessage()
        assert "20 names" in rendered and "40 median" in rendered and "50.0% below" in rendered


class TestCoverageVerdicts:
    async def test_steady_breadth_is_quiet(self, db: AsyncSession) -> None:
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        await _seed_bars(db, [s.id for s in stocks], sessions)
        await db.commit()
        cov = _equity(await check_feed_coverage(db))
        assert cov.names == 40 and cov.baseline == 40
        assert cov.shortfall_pct == 0.0 and not cov.is_collapsed
        md = "\n".join(render_feed_coverage([cov]))
        assert "Feed breadth normal" in md and "FEED COVERAGE ALARM" not in md

    async def test_growth_never_alarms(self, db: AsyncSession) -> None:
        """⚠ D3 widened ingestion to every known NSE symbol and that produced a
        measured +9.4% step against the trailing median in August 2026. A symmetric
        alarm would have fired on a CORRECT change, so only shortfall is an alarm."""
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        await _seed_bars(db, [s.id for s in stocks[:20]], sessions[:-1])
        await _seed_bars(db, [s.id for s in stocks], sessions[-1:])  # breadth doubles
        await db.commit()
        cov = _equity(await check_feed_coverage(db))
        assert cov.names == 40 and cov.baseline == 20
        assert cov.shortfall_pct == -100.0 and cov.deviation_pct == 100.0
        assert not cov.is_collapsed
        assert "FEED COVERAGE ALARM" not in "\n".join(render_feed_coverage([cov]))

    @pytest.mark.parametrize(
        ("names", "collapsed"),
        [(90, False), (89, True)],  # threshold 0.90 of a 100-name baseline
    )
    async def test_threshold_boundary_is_exclusive(
        self, db: AsyncSession, names: int, collapsed: bool
    ) -> None:
        sessions = _recent_sessions(10)
        stocks = await _make_stocks(db, 100, active=100)
        ids = [s.id for s in stocks]
        await _seed_bars(db, ids, sessions[:-1])
        await _seed_bars(db, ids[:names], sessions[-1:])
        await db.commit()
        cov = _equity(await check_feed_coverage(db, baseline_sessions=9, min_fraction=0.90))
        assert cov.names == names and cov.baseline == 100
        assert cov.is_collapsed is collapsed

    async def test_zero_fraction_still_measures_but_never_alarms(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The documented "0 disables" contract, end to end: the number is still
        reported, nothing alarms, and nothing is logged.

        ⚠ HONEST LABEL: this pins the CONTRACT, not the `min_fraction <= 0` guard.
        Deleting that guard leaves this green, because `names < baseline * 0` is already
        False by arithmetic — test-guardian proved exactly that by deleting it. The guard
        is documented in `is_collapsed` as defensive rather than load-bearing; claiming a
        test pinned it would have been a hollow assertion."""
        caplog.set_level(logging.WARNING)
        sessions = _recent_sessions(10)
        stocks = await _make_stocks(db, 40, active=40)
        await _seed_bars(db, [s.id for s in stocks], sessions[:-1])
        await _seed_bars(db, [s.id for s in stocks[:1]], sessions[-1:])
        await db.commit()
        cov = _equity(await check_feed_coverage(db, baseline_sessions=9, min_fraction=0.0))
        assert cov.shortfall_pct == 97.5  # still MEASURED …
        assert not cov.is_collapsed  # … and deliberately not alarmed …
        assert not any("FEED COVERAGE COLLAPSE" in r.message for r in caplog.records)
        assert coverage_to_notification([cov]) is None  # … and never pushed

    def test_the_shipped_threshold_sits_above_the_measured_benign_floor(self) -> None:
        """⭐ The most heavily-argued number in the change, and nothing pinned it —
        test-guardian set it to 0.55 and all 18 tests still passed.

        The worst BENIGN shortfall vs the trailing median, replayed over all 1,098
        `ohlcv_1d` sessions, is 8.17% (2020-07-03, the pre-gap ingestion era); over the
        791 post-gap sessions it is 3.21%, and over the recent 239 it is 2.21%. A
        threshold below the archive's worst arms an alarm that flaps on real history, so
        a retune past that floor must fail loudly rather than ship quietly."""
        threshold = get_settings().feed_coverage_min_fraction
        assert threshold == 0.90
        assert 1.0 - threshold > 0.0817, "threshold is below the measured benign floor"


class TestNotAssessable:
    """A24 — 'not assessable' is a legitimate rendering and beats implying zero."""

    async def test_short_baseline_is_unjudgeable_not_healthy(self, db: AsyncSession) -> None:
        sessions = _recent_sessions(3)  # 1 measured + 2 prior, below the floor of 5
        stocks = await _make_stocks(db, 40, active=40)
        await _seed_bars(db, [s.id for s in stocks], sessions[:-1])
        await _seed_bars(db, [s.id for s in stocks[:1]], sessions[-1:])  # a 97% drop
        await db.commit()
        cov = _equity(await check_feed_coverage(db))
        assert cov.names == 1 and cov.baseline is None
        assert cov.baseline_sessions == 2 < COVERAGE_MIN_BASELINE_SESSIONS
        assert not cov.is_measurable and not cov.is_collapsed
        assert cov.shortfall_pct is None
        md = "\n".join(render_feed_coverage([cov]))
        assert "Breadth not assessable" in md and "needs" in md
        assert "FEED COVERAGE ALARM" not in md and "normal" not in md

    async def test_empty_feed_is_unjudgeable_not_zero(self, db: AsyncSession) -> None:
        cov = _equity(await check_feed_coverage(db))
        assert cov.session is None and cov.names is None and cov.baseline is None
        assert not cov.is_measurable and not cov.is_collapsed
        assert "no data at all" in "\n".join(render_feed_coverage([cov]))


class TestBaselineConstruction:
    def test_measured_session_is_excluded_from_its_own_baseline(self) -> None:
        """A reference containing the observation it judges is dragged toward it by
        exactly the drop the alarm looks for. Prior = [10,10,10,20,20] → median 10;
        including the measured 20 would give median 15 and understate the shortfall."""
        d = date(2026, 9, 11)
        series = [(d, 20), (d, 20), (d, 20), (d, 10), (d, 10), (d, 10)]
        cov = _coverage_from_series("Equity EOD", "ohlcv_1d", series, 0.90)
        assert cov.names == 20
        assert cov.baseline == 10  # not 15
        assert cov.baseline_sessions == 5

    async def test_five_session_baseline_goes_silent_on_a_persistent_collapse(
        self, db: AsyncSession
    ) -> None:
        """⭐ WHY THE BASELINE IS 30 SESSIONS AND NOT THE 5 THE SPEC ASKED FOR.

        A median is overtaken once half its window is collapsed, so a 5-session
        reference has ALREADY adopted the outage as normal by its 4th session — it
        switches itself off inside the failure. The outage that motivated this alarm
        ran five sessions unnoticed. Same fixture, two windows, opposite verdicts."""
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        ids = [s.id for s in stocks]
        await _seed_bars(db, ids, sessions[:-4])
        await _seed_bars(db, ids[:20], sessions[-4:])  # four collapsed sessions
        await db.commit()

        short = _equity(await check_feed_coverage(db, baseline_sessions=5))
        assert short.baseline == 20  # the outage has become the reference
        assert short.shortfall_pct == 0.0 and not short.is_collapsed  # ⛔ SILENT

        long_ = _equity(await check_feed_coverage(db, baseline_sessions=30))
        assert long_.baseline == 40
        assert long_.shortfall_pct == 50.0 and long_.is_collapsed  # ✅ still firing


class TestPerFeed:
    async def test_fo_bhavcopy_breadth_is_measured_independently(
        self, db: AsyncSession
    ) -> None:
        sessions = _recent_sessions(10)
        for d in sessions[:-1]:
            for i in range(30):
                db.add(FoBhavcopy(trade_date=d, symbol=f"FO{i:03d}", instrument="FUT",
                                  expiry_date=d, strike=Decimal("0")))
        for i in range(5):  # the last session carries a sixth of the usual names
            db.add(FoBhavcopy(trade_date=sessions[-1], symbol=f"FO{i:03d}",
                              instrument="FUT", expiry_date=sessions[-1],
                              strike=Decimal("0")))
        await db.commit()
        rows = await check_feed_coverage(db, baseline_sessions=9)
        fo = next(r for r in rows if r.table == "fo_bhavcopy")
        assert fo.names == 5 and fo.baseline == 30 and fo.is_collapsed
        # ⚠ and the equity feed, which is empty here, does not borrow F&O's verdict
        assert not _equity(rows).is_measurable


class TestRegressionsFromReview:
    """Defects found by bug-hunter on 2026-09-14, each pinned by the case that found it."""

    def test_healthy_feeds_stay_visible_while_another_alarms(self) -> None:
        """⛔ The healthy summary used to live in the `else` of `if collapsed`, so the
        moment ANY feed alarmed every other feed's verdict vanished from the header —
        leaving "checked and fine" indistinguishable from "not checked at all", the
        exact A24 failure this module claims to avoid."""
        d = date(2026, 9, 11)
        bad = FeedCoverage("Equity EOD", "ohlcv_1d", d, 100, 1000, 30, 0.90)
        good = FeedCoverage("F&O bhavcopy", "fo_bhavcopy", d, 216, 216, 17, 0.90)
        md = "\n".join(render_feed_coverage([bad, good]))
        assert "FEED COVERAGE ALARM" in md
        assert "Equity EOD" in md and "90.0% below" in md
        assert "F&O bhavcopy" in md and "Also measured, and normal" in md

    def test_an_exactly_normal_feed_renders_no_minus_sign(self) -> None:
        """`deviation_pct` exists to keep a minus off a healthy feed, and `-0.0` is a
        real float that `:+.1f` renders as `-0.0%`. Seen live on fo_bhavcopy (216/216)."""
        cov = FeedCoverage("F&O bhavcopy", "fo_bhavcopy", date(2026, 9, 11), 216, 216, 17, 0.9)
        assert cov.shortfall_pct == 0.0
        assert cov.deviation_pct == 0.0
        assert "-0.0%" not in "\n".join(render_feed_coverage([cov]))
        assert "+0.0%" in "\n".join(render_feed_coverage([cov]))

    async def test_a_future_dated_row_cannot_silence_the_alarm(
        self, db: AsyncSession
    ) -> None:
        """⛔ A misparsed vendor date would become `latest`; with the window anchored on
        it the series held ONE session, so there was no baseline and the renderer said
        "not assessable" INSTEAD of alarming — quiet in the wrong direction. `latest` is
        now bounded to reality, so the collapse on the real latest session still fires."""
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        ids = [s.id for s in stocks]
        await _seed_bars(db, ids, sessions[:-1])
        await _seed_bars(db, ids[:20], sessions[-1:])  # the real collapse
        await _seed_bars(db, ids[:1], [date.today() + timedelta(days=400)])  # the typo
        await db.commit()
        cov = _equity(await check_feed_coverage(db))
        assert cov.session == sessions[-1], "latest must ignore the future-dated row"
        assert cov.names == 20 and cov.baseline == 40 and cov.is_collapsed

    async def test_collapse_pushes_a_notification_without_a_report(
        self, db: AsyncSession
    ) -> None:
        """⭐ The alarm's only caller was `build_daily_report` — i.e. `make analysis`,
        run by hand — so a collapse on a day nobody ran it was never seen. The beat task
        turns the same verdict into a push."""
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        ids = [s.id for s in stocks]
        await _seed_bars(db, ids, sessions[:-1])
        await _seed_bars(db, ids[:20], sessions[-1:])
        await db.commit()
        rows = await check_feed_coverage(db)
        n = coverage_to_notification(rows)
        assert n is not None
        assert n.level is Level.ERROR
        assert n.event == "feed_coverage"  # stable key, so the throttle groups on it
        assert "50.0% below" in n.render()
        assert "REMEDY" in n.render()

    def test_no_notification_when_every_feed_is_normal(self) -> None:
        d = date(2026, 9, 11)
        rows = [
            FeedCoverage("Equity EOD", "ohlcv_1d", d, 2637, 2630, 30, 0.90),
            FeedCoverage("F&O bhavcopy", "fo_bhavcopy", d, 216, 216, 17, 0.90),
        ]
        assert coverage_to_notification(rows) is None

    def test_unjudgeable_feeds_do_not_push(self) -> None:
        """"Not assessable" is not an alarm — pushing on it would train the reader to
        ignore the channel during exactly the startup/backfill windows it is normal."""
        rows = [FeedCoverage("Equity EOD", "ohlcv_1d", None, None, None, 0, 0.90)]
        assert coverage_to_notification(rows) is None


class TestBeatTask:
    """⭐ Finding 1 (HIGH): the beat task is the ONLY surface that makes this a detector
    rather than a report section, and it had no tests. The `notify` seam is exactly the
    kind of seam `.claude/rules/testing.md` says to test through BOTH sides.

    ⚠ These call `_coverage_alert_payload(db)` — the task body — rather than
    `_run_check_feed_coverage()`, whose only extra work is opening a session from the
    module-level POOLED engine. Calling that twice in one run dies with "Event loop is
    closed" (function-scoped loops + a pooled engine), so the session is a parameter and
    the untested remainder is a three-line `async with`.

    ⛔ AND THE FIRST VERSION OF THIS TEST FOUND A REAL ONE: the fail-open guard added an
    hour earlier swallowed that loop error and reported "not assessable", so the task
    returned `status: ok` with no numbers in it. It was caught ONLY because the test
    asserts the measured VALUES rather than "did not raise" — a fail-open probe hides its
    own bugs, which is the cost of the guard and the reason to assert through it."""

    async def test_the_beat_task_pushes_and_reports_the_measured_numbers(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        ids = [s.id for s in stocks]
        await _seed_bars(db, ids, sessions[:-1])
        await _seed_bars(db, ids[:20], sessions[-1:])
        await db.commit()

        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _coverage_alert_payload(db)

        assert result["status"] == "alert"
        assert result["level"] == "error"
        feeds = result["feeds"]
        assert isinstance(feeds, dict)
        assert feeds["ohlcv_1d"] == {"names": 20, "baseline": 40, "shortfall_pct": 50.0}
        assert len(sent) == 1
        pushed = sent[0]
        assert getattr(pushed, "event", None) == "feed_coverage"
        assert "50.0% below" in pushed.render()  # type: ignore[attr-defined]

    async def test_a_healthy_feed_reports_ok_and_pushes_nothing(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silent success — the A11 rule. A channel that pings on a normal day is a
        channel nobody reads on the abnormal one."""
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=40)
        await _seed_bars(db, [s.id for s in stocks], sessions)
        await db.commit()

        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _coverage_alert_payload(db)

        assert result["status"] == "ok"
        assert sent == []
        feeds = result["feeds"]
        assert isinstance(feeds, dict)
        assert feeds["ohlcv_1d"]["shortfall_pct"] == 0.0


class TestProbeNeverRaises:
    """⭐ Finding 4 was a CODE defect, not a test gap: the probe raised straight into
    `build_daily_report`, so one bad query would have taken down the whole `make analysis`
    run — including the staleness alarm rendered directly above it."""

    async def test_a_failing_probe_degrades_to_not_assessable(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def boom(*_a: object, **_k: object) -> list[tuple[date, int]]:
            raise RuntimeError("relation does not exist")

        monkeypatch.setattr("app.services.feed_health._coverage_series", boom)
        rows = await check_feed_coverage(db)  # must not raise
        assert rows and all(not r.is_measurable for r in rows)
        assert all(not r.is_collapsed for r in rows)  # degrade to unknown, never to green
        assert "Breadth not assessable" in "\n".join(render_feed_coverage(rows))

    async def test_one_broken_feed_does_not_blind_the_other(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The savepoint's real job: a failed statement poisons the enclosing
        transaction, so without it the first broken feed would blind every query after
        it — the other feed, and everything the report does next."""
        sessions = _recent_sessions(10)
        for d in sessions:
            for i in range(30):
                db.add(FoBhavcopy(trade_date=d, symbol=f"FO{i:03d}", instrument="FUT",
                                  expiry_date=d, strike=Decimal("0")))
        await db.commit()

        real = feed_health._coverage_series

        async def only_equity_fails(
            session: AsyncSession, sql: str, **kw: object
        ) -> list[tuple[date, int]]:
            if "ohlcv_1d" in sql:
                raise RuntimeError("simulated equity probe failure")
            return await real(session, sql, **kw)  # type: ignore[arg-type]

        monkeypatch.setattr("app.services.feed_health._coverage_series", only_equity_fails)
        rows = await check_feed_coverage(db, baseline_sessions=9)
        assert not _equity(rows).is_measurable
        fo = next(r for r in rows if r.table == "fo_bhavcopy")
        assert fo.is_measurable and fo.names == 30  # the survivor is still measured
        # …and the session is still usable afterwards, which is the point of the savepoint
        assert (await db.execute(select(func.count()).select_from(FoBhavcopy))).scalar()


class TestRenderEdges:
    def test_no_rows_renders_nothing(self) -> None:
        assert render_feed_coverage([]) == []

    def test_two_collapsed_feeds_both_render_and_the_worst_titles_the_push(self) -> None:
        d = date(2026, 9, 11)
        mild = FeedCoverage("F&O bhavcopy", "fo_bhavcopy", d, 150, 216, 17, 0.90)
        severe = FeedCoverage("Equity EOD", "ohlcv_1d", d, 100, 1000, 30, 0.90)
        md = "\n".join(render_feed_coverage([mild, severe]))
        assert "F&O bhavcopy" in md and "Equity EOD" in md
        assert "Also measured, and normal" not in md  # nothing was normal
        n = coverage_to_notification([mild, severe])
        assert n is not None
        assert "Equity EOD" in n.title  # the worst one titles it, not the first
        assert len(n.lines) == 4  # both feeds + the explanation + the remedy


class TestReportWiring:
    async def test_daily_report_carries_and_renders_coverage(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        sessions = _recent_sessions(32)
        stocks = await _make_stocks(db, 40, active=20)
        await _seed_bars(db, [s.id for s in stocks], sessions[:-1])
        await _seed_bars(db, [s.id for s in stocks[:20]], sessions[-1:])
        await db.commit()
        report = await build_daily_report(db, user_id=user.id, day=sessions[-1])
        assert report.feed_coverage, "wiring populated the field"
        assert _equity(report.feed_coverage).is_collapsed
        assert "FEED COVERAGE ALARM" in render_markdown(report)
