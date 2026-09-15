"""Q-R6 / V8 — the daily report's own heartbeat.

⭐ **The measurement that forced this: 26 reports against 30 trading sessions since
2026-08-01 — four missing, and nobody noticed.** The report is where every other alarm in
this system is READ (feed staleness and coverage, worker liveness, universe health, token
and calendar horizons), so a session without one ran unwatched — and **its silence is
indistinguishable from a quiet day.**
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.models.market_calendar import NseHoliday
from app.services.report_health import (
    GRACE_SESSIONS,
    LOOKBACK_SESSIONS,
    read_report_health,
    render_lines,
    to_notification,
)
from app.tasks.health_tasks import _report_health_payload
from sqlalchemy.ext.asyncio import AsyncSession

_IST = ZoneInfo("Asia/Kolkata")
# Fri 2026-09-11 · Mon 09-14 · Tue 09-15. 20:00 IST is past the report's usual window.
TUE_2000 = datetime(2026, 9, 15, 20, 0, tzinfo=_IST)


def _write(tmp: Path, *days: str) -> Path:
    for d in days:
        (tmp / f"{d}.md").write_text("# report\n")
    # Sidecars and weeklies must NOT be mistaken for day reports — they share the folder.
    (tmp / "chase-shadow-2026-09-14.md").write_text("x")
    (tmp / "WEEK-2026-09-14.md").write_text("x")
    (tmp / "LEDGER.md").write_text("x")
    return tmp


class TestMissingReportsAreVisible:
    async def test_a_gap_is_named_session_by_session(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        # Everything present except Friday 09-11 and Monday 09-14.
        days = [f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10)]
        _write(tmp_path, *days)
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert date(2026, 9, 11) in h.missing
        assert date(2026, 9, 14) in h.missing
        assert date(2026, 9, 10) in h.present
        assert h.is_alarming

        md = "\n".join(render_lines(h))
        assert "MISSING DAILY REPORTS" in md and "2026-09-11" in md
        assert "make analysis" in md

        n = to_notification(h)
        assert n is not None and n.event == "report_missing"
        assert "REMEDY" in n.render()

    async def test_a_complete_history_is_quiet(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """The canary: without it, a checker that reports everything missing passes the
        test above."""
        h_all = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        for d in h_all.expected:
            (tmp_path / f"{d.isoformat()}.md").write_text("# report\n")
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert h.missing == () and not h.is_alarming
        assert h.coverage_pct == 100.0
        assert "Report history complete" in "\n".join(render_lines(h))
        assert to_notification(h) is None


class TestItCountsSESSIONSNotDays:
    async def test_a_weekend_is_not_a_missing_report(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """⚠ Trading days, not calendar days. Counting calendar days would report two
        misses every single week and be ignored within a fortnight."""
        h_all = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert all(d.weekday() < 5 for d in h_all.expected)

    async def test_a_holiday_run_is_not_a_missing_run(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        holiday = date(2026, 9, 10)
        db.add(NseHoliday(holiday_date=holiday, name="test holiday"))
        await db.commit()
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert holiday not in h.expected

    async def test_todays_report_is_not_yet_late(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """⚠ A grace session. A report for the latest session is not missing at 09:40 the
        next morning — alarming on it would fire every single day."""
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert GRACE_SESSIONS == 1
        assert date(2026, 9, 15) not in h.expected
        assert len(h.expected) == LOOKBACK_SESSIONS - GRACE_SESSIONS


class TestSidecarsAreNotReports:
    async def test_prefixed_artifacts_do_not_count_as_a_days_report(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """⛔ The folder holds `chase-shadow-<date>.md`, `WEEK-<monday>.md`, `LEDGER.md`
        and more. A loose date match would count a SIDECAR as the day's report and
        declare the history complete on a day the report never ran — the precise failure
        this exists to catch, reintroduced by a sloppy regex."""
        _write(tmp_path)  # sidecars only, no day reports at all
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert h.present == ()
        assert date(2026, 9, 14) in h.missing


class TestProbeNeverRaises:
    async def test_a_missing_directory_is_not_a_crash(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path / "nope")
        assert h.present == () and h.is_alarming  # unknown reads as missing, not as fine

    async def test_a_failing_calendar_read_degrades_to_unknown(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def boom(*_a: object, **_k: object) -> list[date]:
            raise RuntimeError("calendar unavailable")

        monkeypatch.setattr("app.services.report_health.trading_days_between", boom)
        h = await read_report_health(db, now=TUE_2000, directory=tmp_path)
        assert h.expected == () and not h.is_alarming  # nothing claimed either way
        assert render_lines(h) == []


class TestBeatTask:
    async def test_the_beat_pushes_and_reports_the_measured_gap(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("app.services.report_health.REPORT_DIR", tmp_path)
        sent: list[object] = []
        monkeypatch.setattr("app.services.notifier.notify", sent.append)
        result = await _report_health_payload(db)
        assert result["status"] == "alert"
        assert result["present"] == 0
        assert isinstance(result["missing"], list) and result["missing"]
        assert len(sent) == 1
