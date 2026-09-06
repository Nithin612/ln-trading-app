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
  2. **The CAS window-coverage check** — after the window closes, did today actually
     produce rows? This is the alarm A11 structurally could not give, because it fires on
     an absence. It runs as a beat task, which means **it needs the worker back up to
     report** — it catches "died during the window, returned later", the common case.
     *Cannot see:* a worker down continuously past the check time.
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

    @property
    def is_missed(self) -> bool:
        """A trading day whose window has closed with nothing captured. **Unrecoverable** —
        the auction cannot be replayed, so this is reported once and then it is history."""
        return self.is_trading_day and self.window_closed and self.rows == 0


#: 15:33 IST — the moment after which a zero row-count is a MISS rather than "not yet".
CAS_WINDOW_CLOSE = (15, 33)


async def cas_coverage(db: Any, *, day: date, now: datetime | None = None) -> CasCoverage:
    """Whether `day`'s CAS window was covered. The absence check A11 cannot perform."""
    from sqlalchemy import func, select

    from app.models.stock import CasDaily
    from app.services.market_calendar import is_trading_day

    at_ist = (now or datetime.now(tz=UTC)).astimezone(_IST)
    close = datetime.combine(
        day, datetime.min.time(), tzinfo=_IST
    ) + timedelta(hours=CAS_WINDOW_CLOSE[0], minutes=CAS_WINDOW_CLOSE[1])
    trading = await is_trading_day(db, day)
    rows = (
        await db.execute(
            select(func.count()).select_from(CasDaily).where(CasDaily.trade_date == day)
        )
    ).scalar() or 0
    return CasCoverage(
        day=day, is_trading_day=bool(trading), window_closed=at_ist >= close, rows=int(rows)
    )


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
    return out
