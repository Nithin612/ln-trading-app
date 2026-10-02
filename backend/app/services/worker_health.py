"""Worker liveness and the absence alarm — A40.

## What this exists to catch, and why A11 could not

A11 pushes from `finally` blocks, so it reports what **ran**. The failure that actually
costs us is the opposite shape: **the window passed and nothing ran.** No `finally` fires
for a task that never started, so a silent worker produces a silent channel, and a quiet
channel gets read as "fine".

Two standing human rituals are exactly this failure wearing a costume:

  - **CAS capture** — `make worker` must be up 15:15–15:33 IST and **a missed window cannot
    be back-filled.** The protocol is "check the row count each morning."
  - **Provisional health** — no scheduler at all; "run the script yourself each session."

Both are worker-liveness problems. A40 turns them into an alarm. It **strengthens A11
rather than replacing it**: A11 still owns "something ran and failed", this owns "nothing
ran at all".

## A staleness check, not a metrics stack

The same ruling as 6.8.6: a Prometheus/Grafana stack is over-engineering for a solo
platform, and the thing we need is a question — *is this role alive, and was it alive when
it mattered?* Heartbeats are Redis keys with a TTL; absence IS the signal, so there is no
counter to scrape and nothing to keep up.

## The layering, and what each layer cannot see

  1. **Heartbeat** (`worker:heartbeat:{role}`, TTL `HEARTBEAT_TTL_S`). Written by each
     long-running role. Missing ⇒ that role has not run within the TTL.
     *Cannot see:* a role that dies mid-window and restarts before anyone looks.
  2. **The CAS watch** (`scripts/cas_watch.py`, run by **cron**, not beat — moved
     2026-10-02). Before and during the window it asks *is the `celery` heartbeat
     present?* — the one ACTIONABLE alarm, because a window that has not opened can still
     be saved. After 15:33 it asks *did `cas_daily` get rows?*, after 16:05 the same of
     `cas_postclose_daily`. It used to be a beat task, which made it blind to exactly the
     case that cost 2026-10-01: `live_worker` ran all day, `make worker` never did, and the
     check that would have said so was itself scheduled by the beat that was not running.
     *Cannot see:* a laptop asleep at the cron times (cron does not run catch-up).
  3. **The daily-report section** — an independent human-read surface that states each
     role's heartbeat age and whether the last trading day's window was covered. This is
     what catches case 2's blind spot, because `make analysis` runs from a different
     process than the worker.

⚠ **No layer is self-sufficient and the module says so on purpose.** A checker that lives
inside the thing it checks cannot report its own death; that is why layer 3 exists and why
the daily report is the surface that must not be skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.services.notifier import Level, Notification

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

#: Redis KEY carrying one role's last heartbeat (ISO-8601 UTC). Import this — never retype.
HEARTBEAT_KEY = "worker:heartbeat:{role}"

#: TTL on a heartbeat. Comfortably longer than any emitter's cadence, so a missing key means
#: "did not run", not "ran slightly late". Absence is the signal, so this doubles as the
#: staleness threshold.
HEARTBEAT_TTL_S = 600

#: The roles we expect to be alive on a trading day, and what each one's silence costs.
EXPECTED_ROLES: dict[str, str] = {
    "celery": "beat-driven tasks: CAS capture, EOD ingestion, position monitor",
    "live_worker": "the live tick path — provisional scoring and depth capture",
}


@dataclass(frozen=True)
class RoleStatus:
    role: str
    last_seen: datetime | None  # None = no heartbeat at all within the TTL
    age_s: float | None
    purpose: str

    @property
    def is_stale(self) -> bool:
        return self.last_seen is None or (self.age_s or 0) > HEARTBEAT_TTL_S


async def beat(redis: Any, role: str, *, now: datetime | None = None) -> None:
    """Record that `role` is alive. Best-effort: a heartbeat failure must never take down
    the thing it is reporting on."""
    stamp = (now or datetime.now(tz=UTC)).isoformat()
    try:
        await redis.set(HEARTBEAT_KEY.format(role=role), stamp, ex=HEARTBEAT_TTL_S)
    except Exception:
        log.debug("heartbeat write failed for role=%s (non-fatal)", role, exc_info=True)


def beat_sync(redis: Any, role: str, *, now: datetime | None = None) -> None:
    """Sync twin, for the live worker's thread-based monitor loop."""
    stamp = (now or datetime.now(tz=UTC)).isoformat()
    try:
        redis.set(HEARTBEAT_KEY.format(role=role), stamp, ex=HEARTBEAT_TTL_S)
    except Exception:
        log.debug("heartbeat write failed for role=%s (non-fatal)", role, exc_info=True)


async def read_statuses(
    roles: dict[str, str] | None = None, *, now: datetime | None = None
) -> list[RoleStatus]:
    """Every expected role's liveness. Never raises — an unreachable Redis reports every
    role as unknown rather than throwing into a report."""
    import contextlib

    roles = roles or EXPECTED_ROLES
    at = now or datetime.now(tz=UTC)
    raw: dict[str, str | None] = dict.fromkeys(roles)
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            keys = [HEARTBEAT_KEY.format(role=role) for role in roles]
            values = await r.mget(keys)
            raw = dict(zip(roles, values, strict=True))
        finally:
            with contextlib.suppress(Exception):
                await r.aclose()
    except Exception:
        log.debug("heartbeat read failed (non-fatal)", exc_info=True)

    out: list[RoleStatus] = []
    for role, purpose in roles.items():
        seen: datetime | None = None
        value = raw.get(role)
        if value:
            with contextlib.suppress(ValueError):
                seen = datetime.fromisoformat(value)
        age = (at - seen).total_seconds() if seen is not None else None
        out.append(RoleStatus(role=role, last_seen=seen, age_s=age, purpose=purpose))
    return out


@dataclass(frozen=True)
class CasCoverage:
    """Did the closing-auction window actually produce anything on `day`?"""

    day: date
    is_trading_day: bool
    window_closed: bool  # has 15:33 IST passed for this day?
    rows: int
    #: DA-7 post-close capture (15:44–16:05 IST → `cas_postclose_daily`). Defaulted so a
    #: caller that only knows the auction window still constructs a valid coverage.
    postclose_closed: bool = False
    postclose_rows: int = 0

    @property
    def postclose_missed(self) -> bool:
        """Same shape as `is_missed`, for the post-close window — equally unrecoverable."""
        return self.is_trading_day and self.postclose_closed and self.postclose_rows == 0

    @property
    def is_missed(self) -> bool:
        """A trading day whose window has closed with nothing captured. **Unrecoverable** —
        the auction cannot be replayed, so this is reported once and then it is history."""
        return self.is_trading_day and self.window_closed and self.rows == 0


#: 15:33 IST — the moment after which a zero row-count is a MISS rather than "not yet".
#: ⚠ Copies of `cas_tasks._CAS_END` / `_POSTCLOSE_END` (importing the Celery task module here
#: would drag Celery into the report and the cron script); a test pins them equal (W5).
CAS_WINDOW_CLOSE = (15, 33)
#: 16:05 IST — the post-close capture's last poll (DA-7).
POSTCLOSE_WINDOW_CLOSE = (16, 5)
#: The first day the post-close capture existed (DA-7, deployed 2026-09-30 17:17 IST). An
#: earlier day had nothing to miss, so it must never read as "MISSED — unrecoverable"
#: (bug-hunter 2026-10-02: a regenerated 09-29 report would otherwise claim a loss).
POSTCLOSE_FIRST_DAY = date(2026, 10, 1)
#: 15:15 IST — the auction window opens; the liveness alarm says how long is left.
CAS_WINDOW_OPEN = (15, 15)
#: 14:30 IST — from here a missing `celery` heartbeat is a CAS emergency, not just a gap.
#: Early enough that a 14:45 cron run leaves half an hour to start the worker.
CAS_WATCH_FROM = (14, 30)


def _at(day: date, hm: tuple[int, int]) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=_IST) + timedelta(
        hours=hm[0], minutes=hm[1]
    )


async def cas_coverage(db: Any, *, day: date, now: datetime | None = None) -> CasCoverage:
    """Whether `day`'s CAS window was covered. The absence check A11 cannot perform."""
    from sqlalchemy import func, select

    from app.models.stock import CasDaily, CasPostCloseDaily
    from app.services.market_calendar import is_trading_day

    at_ist = (now or datetime.now(tz=UTC)).astimezone(_IST)
    trading = await is_trading_day(db, day)
    rows = (
        await db.execute(
            select(func.count()).select_from(CasDaily).where(CasDaily.trade_date == day)
        )
    ).scalar() or 0
    post_rows = (
        await db.execute(
            select(func.count())
            .select_from(CasPostCloseDaily)
            .where(CasPostCloseDaily.trade_date == day)
        )
    ).scalar() or 0
    return CasCoverage(
        day=day,
        is_trading_day=bool(trading),
        window_closed=at_ist >= _at(day, CAS_WINDOW_CLOSE),
        rows=int(rows),
        # Before POSTCLOSE_FIRST_DAY there was no capture, so the window never "closes" on it.
        postclose_closed=(
            day >= POSTCLOSE_FIRST_DAY and at_ist >= _at(day, POSTCLOSE_WINDOW_CLOSE)
        ),
        postclose_rows=int(post_rows),
    )


def cas_watch_alerts(
    coverage: CasCoverage, celery: RoleStatus, *, now: datetime
) -> list[Notification]:
    """What the CAS watch should push right now. Pure — the cron script only gathers inputs.

    Three alarms, in the order they become possible:

      1. **`make worker` is not running** — from `CAS_WATCH_FROM` until the auction window
         closes, a stale `celery` heartbeat. The only one that can still SAVE the day, so it
         names the time left. This is the alarm 2026-10-01 needed.
      2. **auction window missed** — closed with zero `cas_daily` rows.
      3. **post-close window missed** — closed with zero `cas_postclose_daily` rows.

    A holiday or weekend returns nothing: the calendar, not the cron line, decides.
    """
    if not coverage.is_trading_day:
        return []
    at = now.astimezone(_IST)
    out: list[Notification] = []
    day = coverage.day
    # Until the POST-CLOSE window closes, not the auction's: after 15:33 the 15:44–16:05
    # capture can still be saved, so "start it now" stays the actionable message (bug-hunter
    # 2026-10-02 — it used to fall silent at 15:33 and the 15:40 run said "next session").
    postclose_open = day >= POSTCLOSE_FIRST_DAY and at < _at(day, POSTCLOSE_WINDOW_CLOSE)
    watch_until = POSTCLOSE_WINDOW_CLOSE if day >= POSTCLOSE_FIRST_DAY else CAS_WINDOW_CLOSE
    if _at(day, CAS_WATCH_FROM) <= at < _at(day, watch_until) and celery.is_stale:
        left = (_at(day, CAS_WINDOW_OPEN) - at).total_seconds() / 60
        if left > 0:
            when = f"the CAS window opens in {left:.0f} min (15:15 IST)"
        elif at < _at(day, CAS_WINDOW_CLOSE):
            when = "the CAS window is OPEN NOW — every minute lost is unrecoverable"
        else:
            when = "the auction is gone, but the 15:44–16:05 post-close capture can still be saved"
        seen = "never seen" if celery.age_s is None else f"{celery.age_s / 60:.0f} min ago"
        out.append(
            Notification(
                event="cas_worker_down",
                level=Level.ERROR,
                title="make worker is NOT running — start it now",
                lines=[
                    f"trade_date={day} · {when}",
                    f"celery heartbeat: {seen} (make live-worker does NOT run the CAS capture)",
                    "REMEDY: `make worker` in its own terminal",
                ],
            )
        )
    if coverage.is_missed:
        out.append(
            Notification(
                event="cas_window_missed",
                level=Level.ERROR,
                title="CAS window MISSED — unrecoverable",
                lines=[
                    f"trade_date={day}",
                    "the 15:15–15:33 IST window closed with ZERO rows captured",
                    "the closing auction cannot be replayed — this day is permanently absent",
                    (
                        "REMEDY: start `make worker` NOW — the post-close capture "
                        "can still be saved"
                        if postclose_open
                        else "REMEDY: ensure `make worker` is up before the next session"
                    ),
                ],
            )
        )
    if coverage.postclose_missed:
        out.append(
            Notification(
                event="cas_postclose_missed",
                level=Level.ERROR,
                title="CAS post-close window MISSED — unrecoverable",
                lines=[
                    f"trade_date={day}",
                    "the 15:44–16:05 IST post-close capture closed with ZERO rows",
                    "REMEDY: ensure `make worker` is up across 15:15–16:05 IST",
                ],
            )
        )
    return out


def render_lines(statuses: list[RoleStatus], coverage: CasCoverage | None) -> list[str]:
    """Daily-report block. Loud on a stale role or a missed window; one quiet line when
    everything is current — the opposite of A11's policy, deliberately: this section is the
    only place an ABSENCE can be seen, so its silence has to be a positive statement rather
    than nothing at all."""
    out: list[str] = []
    stale = [s for s in statuses if s.is_stale]
    if stale:
        out += [
            "> ## ⚠️ WORKER LIVENESS ALARM",
            ">",
            "> A role has not checked in. Beat-driven work is NOT running, and the failures "
            "that follow are silent by nature — nothing raises when a task never starts.",
            ">",
        ]
        for s in stale:
            age = "never seen" if s.age_s is None else f"{s.age_s / 60:.0f} min ago"
            out.append(f"> - **{s.role}** — last heartbeat {age}. Covers: {s.purpose}")
        out.append("")
    else:
        ages = " · ".join(f"{s.role} {(s.age_s or 0) / 60:.0f}m" for s in statuses)
        out.append(f"- **Worker liveness:** ✅ all roles current ({ages}).")

    if coverage is not None:
        if coverage.is_missed:
            out += [
                "",
                "> ## ⛔ CAS WINDOW MISSED — UNRECOVERABLE",
                ">",
                f"> {coverage.day} was a trading day, its 15:15–15:33 IST window has closed, "
                "and **zero rows were captured**. The closing auction cannot be replayed, so "
                "this day is permanently absent from the CAS study. Check that `make worker` "
                "is up before the next session.",
                "",
            ]
        elif coverage.is_trading_day and coverage.window_closed:
            out.append(f"- **CAS window {coverage.day}:** ✅ captured {coverage.rows:,} rows.")
        if coverage.postclose_missed:
            out.append(
                f"- **CAS post-close {coverage.day}:** ⛔ MISSED — zero rows in "
                "`cas_postclose_daily` (15:44–16:05 IST); unrecoverable."
            )
        elif coverage.is_trading_day and coverage.postclose_closed:
            out.append(
                f"- **CAS post-close {coverage.day}:** ✅ captured "
                f"{coverage.postclose_rows:,} rows."
            )
    return out
