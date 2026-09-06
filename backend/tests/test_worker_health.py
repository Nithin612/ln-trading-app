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
