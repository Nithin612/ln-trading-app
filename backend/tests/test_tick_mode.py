"""Tick-mode assertion on the depth path — A25.

Kite is documented to deliver quote-mode ticks on a MODE_FULL subscription.
Such a tick carries no order book, so `depth:{stock_id}` stops being refreshed,
expires after 60 s, and 6.8.2's spread-aware fill model falls back to the flat
`paper_slippage_bps` floor — paper fills quietly get CHEAPER than reality, on the
book we judge expectancy with. Every step of that is deliberate fail-open
behaviour, which is why nothing about it is visible today.

These pin the detector, the rate limit on its alarm, the durable day counters,
and the two rules that keep the alarm trustworthy: a mode-less tick is NOT a
degradation (replay would cry wolf every run), and an index tick — full mode, no
book by design — is NOT a depth miss.
"""

import logging

import pytest
from app.broker.tick_mode import (
    MODE_FULL,
    TICK_MODE_HEALTH_KEY,
    TICK_MODE_HEALTH_TTL_SECONDS,
    ModeTally,
    TickModeMonitor,
    read_tick_mode_health,
    record_tick_mode_health,
    render_tick_mode_health,
    tally_tick_modes,
)


def _tick(mode: str | None = MODE_FULL, **extra) -> dict:
    t: dict = {"instrument_token": 777, "last_price": 100.0, **extra}
    if mode is not None:
        t["mode"] = mode
    return t


class _PipeSpy:
    """Buffers like the real pipeline: ops land only on execute()."""

    def __init__(self) -> None:
        self.buffered: list[tuple] = []
        self.executed: list[tuple] = []

    def hset(self, key: str, mapping: dict) -> None:
        self.buffered.append(("hset", key, dict(mapping)))

    def expire(self, key: str, ttl: int) -> None:
        self.buffered.append(("expire", key, ttl))

    def execute(self) -> None:
        self.executed.extend(self.buffered)
        self.buffered.clear()


class TestTally:
    """The census itself — pure, over the whole batch."""

    def test_counts_each_mode_and_names_the_degraded_ones(self) -> None:
        tally = tally_tick_modes(
            [_tick(), _tick(), _tick("quote"), _tick("quote"), _tick("ltp")]
        )
        assert (tally.full, tally.degraded, tally.unknown) == (2, 3, 0)
        assert dict(tally.by_mode) == {"quote": 2, "ltp": 1}
        assert tally.total == 5
        assert tally.is_degraded
        assert tally.describe() == "ltp=1 quote=2"

    def test_missing_mode_is_unknown_and_is_not_an_alarm(self) -> None:
        """Recorded/replayed ticks carry no mode field. Alarming on those would
        fire on every replay run and train us to ignore the warning."""
        tally = tally_tick_modes([_tick(None), _tick(None)])
        assert (tally.full, tally.degraded, tally.unknown) == (0, 0, 2)
        assert tally.is_degraded is False
        assert tally.describe() == "—"

    def test_non_string_mode_is_unknown_not_degraded(self) -> None:
        assert tally_tick_modes([{"mode": 3}]).unknown == 1

    def test_empty_batch(self) -> None:
        t = tally_tick_modes([])
        assert (t.total, t.is_degraded) == (0, False)


class TestMonitor:
    """Accumulation + the rate-limited alarm."""

    def test_accumulates_across_batches(self) -> None:
        m = TickModeMonitor()
        m.observe_ticks([_tick(), _tick("quote")])
        m.observe_ticks([_tick("quote"), _tick("ltp"), _tick(None)])
        assert (m.full, m.degraded, m.unknown) == (1, 3, 1)
        assert m.by_mode == {"quote": 2, "ltp": 1}

    def test_first_degraded_batch_warns_immediately(self, caplog) -> None:
        m = TickModeMonitor()
        with caplog.at_level(logging.WARNING, logger="app.broker.tick_mode"):
            m.observe_ticks([_tick(), _tick("quote")])
        assert len(caplog.records) == 1
        msg = caplog.records[0].getMessage()
        # The warning has to carry the counts, the consequence and the remedy —
        # a bare "degraded" line is how a quiet failure stays quiet.
        assert "TICK MODE DEGRADED" in msg
        assert "quote=1" in msg
        assert "paper_slippage_bps" in msg
        assert "restart live-worker" in msg.lower()

    def test_clean_batches_never_warn(self, caplog) -> None:
        m = TickModeMonitor()
        with caplog.at_level(logging.WARNING, logger="app.broker.tick_mode"):
            m.observe_ticks([_tick(), _tick()])
            m.observe_ticks([_tick(None), _tick(None)])  # replay-shaped
        assert caplog.records == []

    def test_warning_is_rate_limited_then_repeats(self, caplog) -> None:
        """A degraded feed stays degraded; one line per batch would bury the log.
        But it must not go silent either — after the interval it speaks again."""
        now = [1000.0]
        m = TickModeMonitor(warn_interval_s=60.0, clock=lambda: now[0])
        with caplog.at_level(logging.WARNING, logger="app.broker.tick_mode"):
            m.observe_ticks([_tick("quote")])
            now[0] += 30.0
            m.observe_ticks([_tick("quote")])  # inside the window — suppressed
            assert len(caplog.records) == 1
            now[0] += 31.0
            m.observe_ticks([_tick("quote")])  # window elapsed — speaks again
        assert len(caplog.records) == 2
        assert "cumulative degraded=3" in caplog.records[1].getMessage()


class TestCounters:
    """What reaches the durable hash — and what deliberately does not."""

    def test_clean_feed_records_nothing(self) -> None:
        """The zero-round-trip guarantee: nothing to say, no Redis write."""
        m = TickModeMonitor()
        m.observe_ticks([_tick(), _tick()])
        assert m.counters() == {}

    def test_unknown_alone_records_nothing(self) -> None:
        """Otherwise every replay run writes a day hash and the key comes to mean
        'we ran' instead of 'the feed degraded'."""
        m = TickModeMonitor()
        m.observe_ticks([_tick(None)] * 5)
        assert m.counters() == {}

    def test_degradation_records_the_full_picture(self) -> None:
        m = TickModeMonitor()
        m.observe_ticks([_tick(), _tick(), _tick("quote"), _tick(None)])
        m.note_depth_missing()
        assert m.counters() == {
            "full": 2,
            "degraded": 1,
            "unknown": 1,
            "depth_missing": 1,
            "mode:quote": 1,
        }

    def test_depth_miss_alone_is_recorded(self) -> None:
        """The symptom is worth recording even when the mode looks clean — that
        is the case the mode counters cannot explain."""
        m = TickModeMonitor()
        m.observe_ticks([_tick()])
        m.note_depth_missing(4)
        assert m.counters()["depth_missing"] == 4
        assert m.counters()["degraded"] == 0


class TestRecord:
    def test_queues_hset_and_ttl_on_the_callers_pipeline(self) -> None:
        pipe = _PipeSpy()
        assert record_tick_mode_health(pipe, "2026-09-05", {"degraded": 2, "full": 8})
        pipe.execute()
        assert pipe.executed == [
            ("hset", "tickmode:health:2026-09-05", {"degraded": 2, "full": 8}),
            ("expire", "tickmode:health:2026-09-05", TICK_MODE_HEALTH_TTL_SECONDS),
        ]

    def test_overwrites_rather_than_increments(self) -> None:
        """Counters are cumulative since worker start, so HSET — HINCRBY would
        double-count everything the previous run already wrote after a restart."""
        pipe = _PipeSpy()
        record_tick_mode_health(pipe, "2026-09-05", {"degraded": 2})
        assert pipe.buffered[0][0] == "hset"

    @pytest.mark.parametrize(
        ("day", "counters"), [("", {"degraded": 1}), ("2026-09-05", {})]
    )
    def test_nothing_to_record_queues_nothing(self, day, counters) -> None:
        pipe = _PipeSpy()
        assert record_tick_mode_health(pipe, day, counters) is False
        assert pipe.buffered == []


class TestReadBack:
    @pytest.mark.asyncio
    async def test_round_trip_through_real_redis(self) -> None:
        import redis.asyncio as aioredis
        from app.core.config import settings

        day = "2026-09-05"
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            await r.hset(
                TICK_MODE_HEALTH_KEY.format(day=day),
                mapping={"degraded": "7", "full": "93", "mode:quote": "7"},
            )
            assert await read_tick_mode_health(day) == {
                "degraded": 7,
                "full": 93,
                "mode:quote": 7,
            }
        finally:
            await r.delete(TICK_MODE_HEALTH_KEY.format(day=day))
            await r.aclose()

    @pytest.mark.asyncio
    async def test_absent_day_reads_empty(self) -> None:
        assert await read_tick_mode_health("1999-01-01") == {}

    @pytest.mark.asyncio
    async def test_empty_day_reads_empty(self) -> None:
        assert await read_tick_mode_health("") == {}


class TestRender:
    def test_clean_day_prints_nothing(self) -> None:
        """No green tick: an empty hash also means 'past the 7-day TTL' or
        'Redis unreachable', and the report must not claim what it cannot see."""
        assert render_tick_mode_health({}) == []
        assert render_tick_mode_health({"full": 900, "degraded": 0}) == []

    def test_degraded_day_is_loud_and_names_the_modes(self) -> None:
        out = "\n".join(
            render_tick_mode_health(
                {"full": 8000, "degraded": 1200, "unknown": 0, "mode:quote": 1200}
            )
        )
        assert "TICK-MODE DEGRADATION (A25)" in out
        assert "1,200" in out and "8,000" in out
        assert "quote 1200" in out
        assert "paper_slippage_bps" in out

    def test_depth_misses_render_on_their_own(self) -> None:
        out = "\n".join(render_tick_mode_health({"depth_missing": 42, "degraded": 0}))
        assert "no usable book" in out
        assert "42" in out
        assert "Non-full-mode" not in out


class TestModeTallyDefaults:
    def test_by_mode_defaults_are_not_shared(self) -> None:
        a, b = ModeTally(), ModeTally()
        assert a.by_mode == {} and b.by_mode == {}
        assert a.by_mode is not b.by_mode


class TestDailyReportSeam:
    """A25 reaches a human through the daily report, next to the 6.8.6 feed
    alarm — a log line alone is how the provisional hot-set flood hid for weeks."""

    @pytest.mark.asyncio
    async def test_report_reads_the_report_days_counters_and_renders_them(
        self, db
    ) -> None:
        from datetime import date

        import redis.asyncio as aioredis
        from app.core.config import settings
        from app.services.daily_report import build_daily_report, render_markdown

        from tests.helpers import create_test_user, make_stock

        day = date(2026, 7, 9)
        user = await create_test_user(db)
        await make_stock(db)
        await db.commit()

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = TICK_MODE_HEALTH_KEY.format(day=day.isoformat())
        try:
            await r.hset(
                key, mapping={"full": "8000", "degraded": "1200", "mode:quote": "1200"}
            )
            report = await build_daily_report(db, day=day, user_id=user.id)
            # Keyed by the REPORT day, not by now — a `make analysis DATE=…` run
            # must read that day's counters, not today's.
            assert report.tick_mode_health["degraded"] == 1200
            assert "TICK-MODE DEGRADATION (A25)" in render_markdown(report)
        finally:
            await r.delete(key)
            await r.aclose()

    @pytest.mark.asyncio
    async def test_clean_day_adds_nothing_to_the_report(self, db) -> None:
        from datetime import date

        from app.services.daily_report import build_daily_report, render_markdown

        from tests.helpers import create_test_user, make_stock

        user = await create_test_user(db)
        await make_stock(db)
        await db.commit()
        report = await build_daily_report(db, day=date(2026, 7, 10), user_id=user.id)
        assert report.tick_mode_health == {}
        assert "TICK-MODE DEGRADATION" not in render_markdown(report)
