"""Q-R6 / V8 — has the daily report actually been running?

⭐ **The measurement that forced this: 26 reports against 30 trading sessions since
2026-08-01 — four missing, and nobody noticed.** The report is where every other alarm in
this system is READ (feed staleness, feed coverage, worker liveness, universe health, the
token and calendar horizons), so a day with no report is a day with no alarms at all. And
its absence is invisible by construction: **silence is indistinguishable from a quiet
day.**

⚠ **This cannot live inside the report** — the same asymmetry A40 states for the worker: a
report that did not run cannot tell you it did not run. So the check runs in the Celery
beat, a different process, exactly as `worker_health` does.

⚠ **It reads the ARTIFACTS, not a new counter.** `docs/analysis/<date>.md` is the real
evidence a report was produced, it already exists, and counting it is what would have
caught the 26-of-30. §A8 is explicit that inventing a metrics stack here is the failure
mode to avoid, so there is no new table and no new writer — only a reader of what the job
already leaves behind.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.market_calendar import trading_days_between

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from app.services.notifier import Notification

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")

#: `backend/app/services/report_health.py` → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = _REPO_ROOT / "docs" / "analysis"
#: A day's report is `<YYYY-MM-DD>.md`; every sidecar carries a prefix
#: (`chase-shadow-…`, `WEEK-…`), so an anchored match picks out exactly the day reports.
_DAY_REPORT = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")

#: How far back to look. Long enough that a single missed day is visible against a habit,
#: short enough that a month-old gap nobody is going to back-fill stops nagging.
LOOKBACK_SESSIONS = 20
#: Today's report is not due until the EOD cycle has run and someone has generated it;
#: the most recent session is therefore never counted as missing.
GRACE_SESSIONS = 1


@dataclass(frozen=True)
class ReportHealth:
    expected: tuple[date, ...]
    present: tuple[date, ...]
    missing: tuple[date, ...]

    @property
    def coverage_pct(self) -> float | None:
        if not self.expected:
            return None
        return round(len(self.present) / len(self.expected) * 100.0, 1)

    @property
    def is_alarming(self) -> bool:
        return bool(self.missing)


def _reports_on_disk(directory: Path) -> set[date]:
    if not directory.is_dir():
        return set()
    out: set[date] = set()
    for entry in directory.iterdir():
        m = _DAY_REPORT.match(entry.name)
        if m:
            try:
                out.add(date.fromisoformat(m.group(1)))
            except ValueError:  # pragma: no cover - the regex already constrains this
                continue
    return out


async def read_report_health(
    db: AsyncSession, *, now: datetime | None = None, directory: Path | None = None
) -> ReportHealth:
    """Which recent trading sessions have no report. Read-only, and NEVER raises — a
    health probe that can take down its own caller has inverted its purpose."""
    today = (now or datetime.now(UTC)).astimezone(_IST).date()
    try:
        # A generous calendar span, then trimmed to the last N SESSIONS — trading days,
        # not calendar days, so a run of holidays never reads as a run of misses.
        sessions = await trading_days_between(
            db, today - timedelta(days=LOOKBACK_SESSIONS * 2 + 15), today
        )
    except Exception:  # noqa: BLE001 — a health probe must not raise into its caller
        log.exception("report-health calendar read failed; reporting as unknown")
        return ReportHealth((), (), ())

    window = sessions[-LOOKBACK_SESSIONS:] if sessions else []
    # ⚠ The most recent session is excluded: a report for today is not late at 09:40.
    expected = window[:-GRACE_SESSIONS] if len(window) > GRACE_SESSIONS else []
    have = _reports_on_disk(directory or REPORT_DIR)
    present = [d for d in expected if d in have]
    missing = [d for d in expected if d not in have]
    health = ReportHealth(tuple(expected), tuple(present), tuple(missing))
    if health.is_alarming:
        log.warning(
            "DAILY REPORT MISSING for %d of the last %d sessions: %s",
            len(missing), len(expected), ", ".join(d.isoformat() for d in missing),
        )
    return health


def to_notification(health: ReportHealth) -> Notification | None:
    from app.services.notifier import Level, Notification

    if not health.is_alarming:
        return None
    shown = [d.isoformat() for d in health.missing[-5:]]
    return Notification(
        event="report_missing",
        level=Level.WARNING,
        title=(
            f"DAILY REPORT MISSING for {len(health.missing)} of the last "
            f"{len(health.expected)} sessions"
        ),
        lines=[
            "missing: " + ", ".join(shown) + ("…" if len(health.missing) > 5 else ""),
            "the report is where every other alarm is READ — feed staleness and coverage, "
            "worker liveness, universe health, token and calendar horizons",
            "so a session with no report is a session with no alarms, and its silence "
            "looks exactly like a quiet day",
            "REMEDY: run `make analysis DATE=<date>` for each, and check why the habit "
            "lapsed",
        ],
    )


def render_lines(health: ReportHealth) -> list[str]:
    """⚠ Rendered INSIDE the report it is about, which is useful only for the days it DID
    run — a report cannot announce its own absence, which is why the beat exists. What
    this adds is the back-look: reading today's report tells you whether you missed any
    recent ones."""
    if not health.expected:
        return []
    if not health.is_alarming:
        return [
            f"> ✅ **Report history complete** — {len(health.present)}/"
            f"{len(health.expected)} of the last sessions have a report.",
            "",
        ]
    return [
        "> ## ⚠️ MISSING DAILY REPORTS",
        ">",
        f"> **{len(health.missing)} of the last {len(health.expected)}** trading sessions "
        f"have no report: {', '.join(d.isoformat() for d in health.missing)}. Every other "
        "alarm in this system is read HERE, so those sessions ran unwatched — and their "
        "silence looked exactly like a quiet day.",
        "> REMEDY: `make analysis DATE=<date>` per missing session.",
        "",
    ]
