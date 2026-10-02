"""Worker liveness and the absence alarm — A40.

A11 pushes from `finally` blocks, so it reports what **ran**. The failure that actually
costs us is the opposite shape: **the window passed and nothing ran** — no `finally` fires
for a task that never started, so a silent worker produces a silent channel. Two standing
human rituals are that failure in costume: CAS capture (**a missed window cannot be
back-filled**) and provisional health (no scheduler at all).

These pin the three layers and, more importantly, the seams between them — including the
one that was actually broken: a beat entry naming a task that was never registered.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from app.services import worker_health as wh
from app.services.worker_health import HEARTBEAT_TTL_S, CasCoverage, RoleStatus

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _status(role: str, age_s: float | None) -> RoleStatus:
    seen = None if age_s is None else NOW - timedelta(seconds=age_s)
    return RoleStatus(role=role, last_seen=seen, age_s=age_s, purpose="p")


class TestStaleness:
    def test_a_fresh_heartbeat_is_alive(self) -> None:
        assert _status("celery", 30).is_stale is False

    def test_a_missing_heartbeat_is_stale(self) -> None:
        """Absence IS the signal — there is no counter to scrape."""
        assert _status("celery", None).is_stale is True

    def test_an_expired_heartbeat_is_stale(self) -> None:
        assert _status("celery", HEARTBEAT_TTL_S + 1).is_stale is True


class TestCasCoverageIsTheAbsenceAlarm:
    def _cov(self, *, trading: bool, closed: bool, rows: int) -> CasCoverage:
        return CasCoverage(
            day=date(2026, 9, 4), is_trading_day=trading, window_closed=closed, rows=rows
        )

    def test_a_closed_window_with_no_rows_is_a_miss(self) -> None:
        """⭐ The alarm A11 structurally could not give: it fires on a thing that did NOT
        happen, and no `finally` exists for that."""
        assert self._cov(trading=True, closed=True, rows=0).is_missed is True

    def test_before_the_window_closes_zero_is_not_yet_a_miss(self) -> None:
        """Otherwise the alarm fires every morning and gets muted."""
        assert self._cov(trading=True, closed=False, rows=0).is_missed is False

    def test_a_holiday_is_never_a_miss(self) -> None:
        assert self._cov(trading=False, closed=True, rows=0).is_missed is False

    def test_rows_captured_is_not_a_miss(self) -> None:
        assert self._cov(trading=True, closed=True, rows=1664).is_missed is False


class TestRendering:
    def test_a_stale_role_is_loud_and_names_what_it_covers(self) -> None:
        out = "\n".join(wh.render_lines([_status("celery", None)], None))
        assert "WORKER LIVENESS ALARM" in out
        assert "never seen" in out
        assert "nothing raises when a task never starts" in out or "silent by nature" in out

    def test_all_current_still_says_so_explicitly(self) -> None:
        """⭐ The opposite of A11's policy, deliberately: this is the ONLY place an absence
        can be seen, so its silence must be a positive statement rather than nothing."""
        out = "\n".join(wh.render_lines([_status("celery", 60)], None))
        assert "✅ all roles current" in out

    def test_a_missed_window_says_it_is_unrecoverable(self) -> None:
        cov = CasCoverage(
            day=date(2026, 9, 4), is_trading_day=True, window_closed=True, rows=0
        )
        out = "\n".join(wh.render_lines([_status("celery", 60)], cov))
        assert "CAS WINDOW MISSED" in out
        assert "cannot be replayed" in out

    def test_a_covered_window_reports_the_count(self) -> None:
        cov = CasCoverage(
            day=date(2026, 9, 4), is_trading_day=True, window_closed=True, rows=1664
        )
        out = "\n".join(wh.render_lines([_status("celery", 60)], cov))
        assert "1,664 rows" in out
        assert "MISSED" not in out


class TestHeartbeatIsBestEffort:
    """A heartbeat failure must never take down the thing it reports on."""

    @pytest.mark.asyncio
    async def test_an_async_write_failure_is_swallowed(self) -> None:
        class Broken:
            async def set(self, *_a, **_k):
                raise RuntimeError("redis down")

        await wh.beat(Broken(), "celery")  # must not raise

    def test_a_sync_write_failure_is_swallowed(self) -> None:
        class Broken:
            def set(self, *_a, **_k):
                raise RuntimeError("redis down")

        wh.beat_sync(Broken(), "live_worker")  # must not raise

    @pytest.mark.asyncio
    async def test_reading_with_redis_unreachable_reports_unknown_not_healthy(
        self, monkeypatch
    ) -> None:
        """Failing to READ must never look like 'alive' — it degrades to stale, which is
        the safe direction for a liveness check."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")
        statuses = await wh.read_statuses(now=NOW)
        assert statuses and all(s.is_stale for s in statuses)


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_a_written_heartbeat_reads_back_fresh(self) -> None:
        import redis.asyncio as aioredis
        from app.core.config import settings

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await wh.beat(r, "celery", now=NOW)
            statuses = await wh.read_statuses({"celery": "p"}, now=NOW)
            assert statuses[0].is_stale is False
            assert statuses[0].age_s == pytest.approx(0, abs=2)
        finally:
            await r.delete(wh.HEARTBEAT_KEY.format(role="celery"))
            await r.aclose()


class TestBeatScheduleIsWired:
    def test_every_beat_entry_names_a_registered_task(self) -> None:
        """⭐ Found by writing this: `app.tasks.health_tasks` was missing from Celery's
        `include`, so the heartbeat beat entry pointed at a task that would never register
        — the alarm would have been silently dead, which is the exact failure mode A40
        exists to prevent.
        """
        import importlib

        from app.celery_app import celery_app

        for module in celery_app.conf.include:
            importlib.import_module(module)
        missing = {
            name: entry["task"]
            for name, entry in celery_app.conf.beat_schedule.items()
            if entry["task"] not in celery_app.tasks
        }
        assert not missing, f"beat entries with no registered task: {missing}"


# ── CAS watch (moved out of beat to cron, 2026-10-02) ─────────────────────────

_IST_TZ = wh._IST
DAY = date(2026, 10, 1)  # a Thursday — the day the beat-only check was blind


def _ist(h: int, m: int) -> datetime:
    return datetime(2026, 10, 1, h, m, tzinfo=_IST_TZ)


def _cov(*, trading: bool = True, at: datetime, rows: int = 0, post: int = 0) -> CasCoverage:
    return CasCoverage(
        day=DAY,
        is_trading_day=trading,
        window_closed=at >= _ist(*wh.CAS_WINDOW_CLOSE),
        rows=rows,
        postclose_closed=at >= _ist(*wh.POSTCLOSE_WINDOW_CLOSE),
        postclose_rows=post,
    )


def _celery(age_s: float | None) -> RoleStatus:
    return RoleStatus(
        role="celery", last_seen=None if age_s is None else NOW, age_s=age_s, purpose="p"
    )


class TestCasWatchAlerts:
    def test_worker_down_before_the_window_is_the_actionable_alarm(self) -> None:
        """⭐ test_beat_only_cas_check_blind_to_dead_beat: 2026-10-01, live_worker up all day,
        `make worker` never started. The beat-scheduled check could not fire; this must, at
        14:45, with the time left in the message."""
        at = _ist(14, 45)
        alerts = wh.cas_watch_alerts(_cov(at=at), _celery(None), now=at)
        assert [a.event for a in alerts] == ["cas_worker_down"]
        assert alerts[0].level is wh.Level.ERROR
        assert "opens in 30 min" in alerts[0].lines[0]
        assert "never seen" in alerts[0].lines[1]

    def test_worker_down_inside_the_window_says_it_is_open(self) -> None:
        at = _ist(15, 20)
        (a,) = wh.cas_watch_alerts(_cov(at=at), _celery(900), now=at)
        assert "OPEN NOW" in a.lines[0]
        assert "15 min ago" in a.lines[1]

    def test_a_live_worker_is_silent(self) -> None:
        at = _ist(15, 5)
        assert wh.cas_watch_alerts(_cov(at=at), _celery(60), now=at) == []

    def test_before_the_watch_starts_a_dead_worker_is_not_a_cas_alarm(self) -> None:
        at = _ist(14, 29)
        assert wh.cas_watch_alerts(_cov(at=at), _celery(None), now=at) == []

    def test_dead_worker_at_1540_still_says_start_it_post_close_can_be_saved(self) -> None:
        """test_liveness_alarm_silent_after_1533_while_post_close_savable (bug-hunter
        2026-10-02): the alarm used to stop at 15:33, so the 15:40 run said only "missed —
        ensure the worker is up before the next session" with the post-close window still
        four minutes from opening."""
        at = _ist(15, 40)
        alerts = wh.cas_watch_alerts(_cov(at=at), _celery(None), now=at)
        assert [a.event for a in alerts] == ["cas_worker_down", "cas_window_missed"]
        assert "post-close capture can still be saved" in alerts[0].lines[0]
        assert "start `make worker` NOW" in alerts[1].lines[-1]

    def test_after_1605_the_remedy_is_the_next_session(self) -> None:
        at = _ist(16, 10)
        alerts = wh.cas_watch_alerts(_cov(at=at, post=5), _celery(None), now=at)
        assert [a.event for a in alerts] == ["cas_window_missed"]
        assert "before the next session" in alerts[0].lines[-1]

    def test_before_post_close_existed_the_watch_ends_at_1533(self) -> None:
        old = date(2026, 9, 29)
        at = datetime(2026, 9, 29, 15, 40, tzinfo=_IST_TZ)
        cov = CasCoverage(day=old, is_trading_day=True, window_closed=True, rows=0)
        alerts = wh.cas_watch_alerts(cov, _celery(None), now=at)
        assert [a.event for a in alerts] == ["cas_window_missed"]
        assert "before the next session" in alerts[0].lines[-1]

    def test_both_windows_missed_after_1605(self) -> None:
        at = _ist(16, 10)
        alerts = wh.cas_watch_alerts(_cov(at=at), _celery(None), now=at)
        assert [a.event for a in alerts] == ["cas_window_missed", "cas_postclose_missed"]

    def test_both_captured_is_silent(self) -> None:
        at = _ist(16, 10)
        assert wh.cas_watch_alerts(_cov(at=at, rows=210, post=210), _celery(60), now=at) == []

    def test_post_close_miss_alone_is_reported(self) -> None:
        at = _ist(16, 10)
        alerts = wh.cas_watch_alerts(_cov(at=at, rows=210, post=0), _celery(60), now=at)
        assert [a.event for a in alerts] == ["cas_postclose_missed"]

    def test_a_holiday_pushes_nothing_even_with_everything_down(self) -> None:
        at = _ist(16, 10)
        assert wh.cas_watch_alerts(_cov(trading=False, at=at), _celery(None), now=at) == []

    def test_the_window_constants_match_their_owners(self) -> None:
        """W5: the copies in worker_health must equal the capture task's own constants."""
        from app.tasks import cas_tasks as ct

        assert (ct._CAS_START.hour, ct._CAS_START.minute) == wh.CAS_WINDOW_OPEN
        assert (ct._CAS_END.hour, ct._CAS_END.minute) == wh.CAS_WINDOW_CLOSE
        assert (ct._POSTCLOSE_END.hour, ct._POSTCLOSE_END.minute) == wh.POSTCLOSE_WINDOW_CLOSE

    def test_the_cas_check_is_not_scheduled_by_beat(self) -> None:
        """A beat task cannot report that the beat is down — the reason it moved to cron."""
        from app.celery_app import celery_app

        tasks = {e["task"] for e in celery_app.conf.beat_schedule.values()}
        assert not any("cas_coverage" in t for t in tasks)

    def test_the_report_states_the_post_close_outcome(self) -> None:
        at = _ist(16, 10)
        missed = "\n".join(wh.render_lines([_celery(60)], _cov(at=at, rows=5, post=0)))
        assert "CAS post-close 2026-10-01:** ⛔ MISSED" in missed
        ok = "\n".join(wh.render_lines([_celery(60)], _cov(at=at, rows=5, post=210)))
        assert "CAS post-close 2026-10-01:** ✅ captured 210 rows" in ok


class TestCasCoverageCountsBothTables:
    @pytest.mark.asyncio
    async def test_coverage_counts_auction_and_post_close_rows_for_the_day_only(self, db) -> None:
        from app.models.stock import CasDaily, CasPostCloseDaily

        from tests.helpers import make_stock

        a = await make_stock(db, symbol="AAA")
        b = await make_stock(db, symbol="BBB")
        db.add_all(
            [
                CasDaily(stock_id=a.id, trade_date=DAY),
                CasDaily(stock_id=b.id, trade_date=DAY),
                CasDaily(stock_id=a.id, trade_date=date(2026, 9, 30)),  # another day — excluded
                CasPostCloseDaily(stock_id=a.id, trade_date=DAY),
            ]
        )
        await db.flush()

        cov = await wh.cas_coverage(db, day=DAY, now=_ist(16, 10))
        assert (cov.is_trading_day, cov.window_closed, cov.postclose_closed) == (True, True, True)
        assert (cov.rows, cov.postclose_rows) == (2, 1)
        assert not cov.is_missed and not cov.postclose_missed

        early = await wh.cas_coverage(db, day=DAY, now=_ist(15, 50))
        assert early.window_closed and not early.postclose_closed

    @pytest.mark.asyncio
    async def test_a_day_before_post_close_existed_is_never_a_post_close_miss(
        self, db
    ) -> None:
        """test_pre_capture_day_reads_as_post_close_missed (bug-hunter 2026-10-02): a
        regenerated 09-29 report claimed "post-close MISSED — unrecoverable" for a day the
        capture did not exist yet."""
        old = date(2026, 9, 29)
        cov = await wh.cas_coverage(
            db, day=old, now=datetime(2026, 9, 29, 16, 10, tzinfo=_IST_TZ)
        )
        assert cov.is_trading_day and cov.window_closed
        assert cov.postclose_closed is False and cov.postclose_missed is False
        assert "post-close" not in "\n".join(wh.render_lines([_celery(60)], cov))
