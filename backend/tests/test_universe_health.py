"""§77 — is the universe rule still running, and were its inputs captured?

⭐ The failure being detected has NO SYMPTOM OF ITS OWN. `materialise_universe` is the
only writer of `stocks.is_active`, and that flag gates ingestion breadth, the scan
universe and the live subscription — so a beat that silently stopped leaves everything
running confidently on a decision nobody re-took. That is the 2026-09-07 shape exactly:
the absence of a write is not an error anyone raises.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.services.universe_health import (
    STALE_ALARM_DAYS,
    read_universe_health,
    render_lines,
    to_notification,
)
from app.services.universe_rule import RULE_VERSION
from app.tasks.health_tasks import _universe_health_payload
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

_IST = ZoneInfo("Asia/Kolkata")
# Fri 2026-09-11, Mon 2026-09-14, Tue 2026-09-15. 10:00 IST is past the 09:00 due time,
# so "today" counts as owed on a trading day.
FRI = date(2026, 9, 11)
MON = date(2026, 9, 14)
TUE = date(2026, 9, 15)
TUE_1000 = datetime(2026, 9, 15, 10, 0, tzinfo=_IST)


async def _snapshot(db: AsyncSession, as_of: date, stock_ids: list[int]) -> None:
    for sid in stock_ids:
        await db.execute(
            text(
                "INSERT INTO universe_snapshot (as_of, stock_id, rule_version)"
                " VALUES (:d, :s, :v) ON CONFLICT DO NOTHING"
            ),
            {"d": as_of, "s": sid, "v": RULE_VERSION},
        )


async def _inputs(db: AsyncSession, as_of: date) -> None:
    await db.execute(
        text(
            "INSERT INTO universe_rule_inputs"
            " (as_of, source_url, csv_gz, csv_sha256, eq_listed, kite_tradable,"
            "  rule_version)"
            " VALUES (:d, 'http://x', '\\x1f8b'::bytea, 'sha', '{AAA}', '{AAA}', :v)"
        ),
        {"d": as_of, "v": RULE_VERSION},
    )


class TestStaleness:
    async def test_todays_evaluation_is_current_and_quiet(
        self, db: AsyncSession
    ) -> None:
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, TUE, [s.id])
        await _inputs(db, TUE)
        await db.commit()
        h = await read_universe_health(db, now=TUE_1000)
        assert h.snapshot_as_of == TUE and h.snapshot_days_behind == 0
        assert h.snapshot_members == 1 and h.active_stocks == 1
        assert not h.is_alarming and h.inputs_match_snapshot
        md = "\n".join(render_lines(h))
        assert "Universe current" in md and "UNIVERSE RULE STALE" not in md
        assert "Rule inputs on record" in md
        assert to_notification(h) is None

    async def test_one_day_behind_is_reported_but_not_alarmed(
        self, db: AsyncSession
    ) -> None:
        """⚠ One day behind is the NORMAL state for much of a trading day — the beat runs
        in the morning. Alarming on it would train the reader to ignore the channel."""
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, MON, [s.id])
        await _inputs(db, MON)
        await db.commit()
        h = await read_universe_health(db, now=TUE_1000)
        assert h.snapshot_days_behind == 1
        assert h.snapshot_is_stale and not h.is_alarming
        assert to_notification(h) is None
        assert "UNIVERSE RULE STALE" not in "\n".join(render_lines(h))

    async def test_two_days_behind_alarms_and_pushes(self, db: AsyncSession) -> None:
        for sym in ("AAA", "BBB", "CCC"):
            await make_stock(db, symbol=sym)
        ids = [
            r[0] for r in (await db.execute(text("SELECT id FROM stocks"))).fetchall()
        ]
        await _snapshot(db, FRI, ids)
        await _inputs(db, FRI)
        await db.commit()
        h = await read_universe_health(db, now=TUE_1000)
        assert h.snapshot_days_behind == STALE_ALARM_DAYS == 2
        assert h.is_alarming
        md = "\n".join(render_lines(h))
        assert "UNIVERSE RULE STALE" in md and "2** trading day(s) behind" in md
        # The count of names riding on the stale decision is the actionable part.
        assert "3** stocks are active" in md or "3 stocks are active" in md
        n = to_notification(h)
        assert n is not None and n.event == "universe_stale"
        assert "REMEDY" in n.render() and "materialise-universe" in n.render()

    async def test_a_never_evaluated_universe_is_maximally_stale(
        self, db: AsyncSession
    ) -> None:
        await make_stock(db, symbol="AAA")
        await db.commit()
        h = await read_universe_health(db, now=TUE_1000)
        assert h.snapshot_as_of is None and h.snapshot_days_behind is None
        assert h.is_alarming
        assert "NEVER evaluated" in "\n".join(render_lines(h))

    async def test_a_weekend_run_does_not_expect_a_weekend_evaluation(
        self, db: AsyncSession
    ) -> None:
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, FRI, [s.id])
        await db.commit()
        sat = datetime(2026, 9, 12, 12, 0, tzinfo=_IST)
        h = await read_universe_health(db, now=sat)
        assert h.expected == FRI and h.snapshot_days_behind == 0
        assert not h.is_alarming

    async def test_before_the_beat_is_due_today_is_not_owed(
        self, db: AsyncSession
    ) -> None:
        """⚠ The beat lands 08:35 IST. Inheriting the EOD feeds' 18:45 cutoff would have
        made every morning read a day behind — which is why `due` is a parameter."""
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, MON, [s.id])
        await db.commit()
        tue_0800 = datetime(2026, 9, 15, 8, 0, tzinfo=_IST)
        h = await read_universe_health(db, now=tue_0800)
        assert h.expected == MON and h.snapshot_days_behind == 0


class TestInputsAreADifferentFact:
    async def test_a_snapshot_without_recorded_inputs_says_so(
        self, db: AsyncSession
    ) -> None:
        """⭐ "The rule ran" and "we can explain what it decided" are different facts, and
        merging them would hide a defect with a different remedy. Every day before
        2026-09-14 has no inputs because the table did not exist — hence "not captured"
        rather than "missing" (A24)."""
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, TUE, [s.id])  # rule ran…
        await db.commit()  # …but nothing recorded its source
        h = await read_universe_health(db, now=TUE_1000)
        assert not h.is_alarming  # the rule is current…
        assert not h.inputs_match_snapshot  # …and its source is not on record
        md = "\n".join(render_lines(h))
        assert "Universe current" in md
        assert "Rule inputs NOT captured" in md and "never" in md

    async def test_inputs_from_an_older_day_do_not_count_as_matching(
        self, db: AsyncSession
    ) -> None:
        """A canary: yesterday's inputs must not vouch for today's verdict."""
        s = await make_stock(db, symbol="AAA")
        await _snapshot(db, TUE, [s.id])
        await _inputs(db, MON)
        await db.commit()
        h = await read_universe_health(db, now=TUE_1000)
        assert h.inputs_as_of == MON and h.snapshot_as_of == TUE
        assert not h.inputs_match_snapshot
        assert "2026-09-14" in "\n".join(render_lines(h))


class TestProbeNeverRaises:
    async def test_a_failing_read_reports_unknown_rather_than_raising(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The rule `calendar_health` states and `feed_health` learned the expensive way:
        a health probe that can take down its own report has inverted its purpose."""

        async def boom(*_a: object, **_k: object) -> date:
            raise RuntimeError("relation does not exist")

        monkeypatch.setattr(
            "app.services.universe_health.expected_latest_trading_day", boom
        )
        h = await read_universe_health(db, now=TUE_1000)  # must not raise
        assert h.snapshot_as_of is None and h.is_alarming  # unknown, never "fine"


class TestBeatTask:
    async def test_the_task_pushes_and_reports_the_measured_numbers(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for sym in ("AAA", "BBB"):
            await make_stock(db, symbol=sym)
        await db.commit()
        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _universe_health_payload(db)
        assert result["status"] == "alert"  # never evaluated
        assert result["active_stocks"] == 2
        assert result["inputs_on_record"] is False
        assert len(sent) == 1

    async def test_a_current_universe_reports_ok_and_pushes_nothing(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        s = await make_stock(db, symbol="AAA")
        today = datetime.now(UTC).astimezone(_IST).date()
        # Use a recent weekday so the calendar treats it as the expected session.
        d = today - timedelta(days=1) if today.weekday() == 6 else today
        await _snapshot(db, d, [s.id])
        await _inputs(db, d)
        await db.commit()
        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _universe_health_payload(db)
        assert result["status"] == "ok" and sent == []
        assert result["inputs_on_record"] is True
