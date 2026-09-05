"""Tick-mode assertion for the depth path — A25.

We subscribe ``KiteTicker.MODE_FULL`` and harvest 5-level depth out of the ticks
it returns (6.8.1). Kite is **documented to deliver quote-mode ticks on a
full-mode subscription** — an observed broker behaviour, not a bug of ours. A
quote-mode tick simply has no ``depth`` key, so:

    quote-mode tick → extract_top_of_book() → None → ``depth:{stock_id}`` is
    never refreshed → the key expires after 60 s → 6.8.2's spread-aware fill
    model finds no book → paper fills fall back to the flat
    ``paper_slippage_bps`` floor.

Every step of that is the fail-open behaviour we deliberately designed, which is
exactly why it is dangerous: the only symptom is paper fills getting quietly
CHEAPER than reality, on the book we use to judge whether a −0.303R expectancy is
improving. Same shape as the 6.8.6 silent-feed-outage alarm — a quiet data
failure needs a loud signal.

**This module detects and counts; it does not react.** The contrasting library
(repo 8) reopens its socket on a mode downgrade. We do not: we have never
observed this against us, re-subscribing from the consumer thread reaches across
into the ticker's own thread, and a reconnect loop on a misread would cost more
than the degradation. Detect, count, shout, name the remedy — the point is that
the degradation must never happen quietly.

Three surfaces, cheapest first:
  1. ``WorkerState.stats`` → the existing live-worker heartbeat + shutdown line.
  2. A rate-limited ``log.warning`` naming the counts, the consequence and the
     remedy (fires immediately on the FIRST degraded tick).
  3. A durable Redis day hash ``tickmode:health:{day}`` (7-day TTL, written into
     the tick loop's own pipeline and only when there is something to record),
     read back by the daily report — a log line alone hid the provisional
     hot-set flood for weeks (A26).
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

# Mirrors KiteTicker.MODE_FULL. Deliberately NOT imported from kiteconnect: this
# module is pure and is exercised by tests that never touch the SDK, and the
# value is part of the wire protocol, not of our configuration.
MODE_FULL = "full"

# Durable per-day counters. HASH ``tickmode:health:{day}`` → {full, degraded,
# unknown, depth_missing, mode:<label>}; 7-day TTL, matching provisional:health.
TICK_MODE_HEALTH_KEY = "tickmode:health:{day}"
TICK_MODE_HEALTH_TTL_SECONDS = 7 * 24 * 3600

# A degraded feed stays degraded for as long as the broker says so; one warning
# per minute is loud enough to notice and quiet enough to leave the log readable.
_WARN_INTERVAL_S = 60.0


@dataclass(frozen=True)
class ModeTally:
    """Mode census over ONE tick batch.

    Counted over every tick in the batch, including ones the FFI conversion
    later drops (unknown token) or the snapshot-echo guard skips: the mode is a
    property of the SUBSCRIPTION, not of a tick's usability downstream.
    """

    full: int = 0
    degraded: int = 0  # mode present and != "full" — the documented downgrade
    unknown: int = 0  # no `mode` key at all (synthetic/replayed ticks)
    by_mode: Mapping[str, int] = field(default_factory=dict)  # degraded modes only

    @property
    def total(self) -> int:
        return self.full + self.degraded + self.unknown

    @property
    def is_degraded(self) -> bool:
        """True only for an OBSERVED non-full mode. `unknown` is not an alarm:
        recorded/replayed ticks legitimately carry no mode field, and warning on
        those would train us to ignore the warning."""
        return self.degraded > 0

    def describe(self) -> str:
        """`quote=412 ltp=3` — the actual modes seen, for the log line."""
        return " ".join(f"{m}={n}" for m, n in sorted(self.by_mode.items())) or "—"


def tally_tick_modes(ticks: Iterable[Mapping[str, Any]]) -> ModeTally:
    """Census the ``mode`` field of a tick batch. Pure; never raises."""
    full = degraded = unknown = 0
    by_mode: dict[str, int] = {}
    for tick in ticks:
        mode = tick.get("mode")
        if not isinstance(mode, str):
            unknown += 1
        elif mode == MODE_FULL:
            full += 1
        else:
            degraded += 1
            by_mode[mode] = by_mode.get(mode, 0) + 1
    return ModeTally(full=full, degraded=degraded, unknown=unknown, by_mode=by_mode)


class TickModeMonitor:
    """Accumulates the census across batches and owns the rate-limited alarm.

    Stateful and single-threaded by construction — it lives on ``WorkerState``
    and is only ever touched by the consumer thread, like every other counter
    there.
    """

    def __init__(
        self,
        *,
        warn_interval_s: float = _WARN_INTERVAL_S,
        clock: Any = time.monotonic,
    ) -> None:
        self._warn_interval_s = warn_interval_s
        self._clock = clock
        self._last_warn: float | None = None
        self.full = 0
        self.degraded = 0
        self.unknown = 0
        self.depth_missing = 0
        self.by_mode: dict[str, int] = {}

    def observe(self, tally: ModeTally) -> ModeTally:
        """Fold one batch's census in, warning if the feed is degraded."""
        self.full += tally.full
        self.degraded += tally.degraded
        self.unknown += tally.unknown
        for mode, n in tally.by_mode.items():
            self.by_mode[mode] = self.by_mode.get(mode, 0) + n
        if tally.is_degraded and self._should_warn():
            log.warning(
                "live-worker TICK MODE DEGRADED: %d of %d ticks in this batch were not "
                "full mode (%s); cumulative degraded=%d full=%d. Kite is documented to "
                "send quote-mode ticks on a MODE_FULL subscription — those ticks carry "
                "no order book, so depth:{stock_id} goes stale and 6.8.2's spread-aware "
                "paper fills silently fall back to the flat paper_slippage_bps floor "
                "(fills get CHEAPER than reality). Remedy: restart live-worker to "
                "re-subscribe MODE_FULL; counters are durable in %s.",
                tally.degraded,
                tally.total,
                tally.describe(),
                self.degraded,
                self.full,
                TICK_MODE_HEALTH_KEY.format(day="<day>"),
            )
        return tally

    def observe_ticks(self, ticks: Iterable[Mapping[str, Any]]) -> ModeTally:
        return self.observe(tally_tick_modes(ticks))

    def note_depth_missing(self, n: int = 1) -> None:
        """A tradable full-mode tick whose book was unusable. The SYMPTOM, where
        the mode counters are the CAUSE — counted separately because a one-sided
        pre-open book is normal and must not raise the mode alarm."""
        self.depth_missing += n

    def _should_warn(self) -> bool:
        now = self._clock()
        if self._last_warn is not None and now - self._last_warn < self._warn_interval_s:
            return False
        self._last_warn = now
        return True

    def counters(self) -> dict[str, int]:
        """Cumulative counters for the durable hash — EMPTY unless something
        actionable happened, so a clean feed costs zero Redis round trips.

        `unknown` alone is deliberately NOT actionable: a recorded or replayed
        tick legitimately carries no mode field, and a day hash written on every
        replay would make the key mean "we ran" instead of "the feed degraded".
        It still rides the heartbeat counters, where a mode-less LIVE feed would
        show up. Values are cumulative since worker start."""
        if not self.degraded and not self.depth_missing:
            return {}
        out = {
            "full": self.full,
            "degraded": self.degraded,
            "unknown": self.unknown,
            "depth_missing": self.depth_missing,
        }
        for mode, n in self.by_mode.items():
            out[f"mode:{mode}"] = n
        return out


def record_tick_mode_health(pipe: Any, day: str, counters: Mapping[str, int]) -> bool:
    """Queue the day hash onto the tick loop's EXISTING pipeline (never a
    connection of its own — this runs in the hot path). Values are cumulative
    since worker start, so HSET-overwrite, not HINCRBY: a restart re-counts from
    zero and must not double-count what the previous run already wrote. Returns
    True if anything was queued."""
    if not day or not counters:
        return False
    key = TICK_MODE_HEALTH_KEY.format(day=day)
    pipe.hset(key, mapping=dict(counters))
    pipe.expire(key, TICK_MODE_HEALTH_TTL_SECONDS)
    return True


async def read_tick_mode_health(day: str) -> dict[str, int]:
    """Read back one day's counters. ``{}`` for a clean day, a day past the TTL,
    or an unreachable Redis — every caller treats absence as "nothing to report",
    never as "verified healthy" (the report says which)."""
    if not day:
        return {}
    try:
        import redis.asyncio as aioredis

        # Any-typed client: redis-py's async HGETALL is declared as a
        # sync-or-awaitable union, which mypy cannot await through.
        r: Any = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            raw: dict[str, str] = await r.hgetall(TICK_MODE_HEALTH_KEY.format(day=day))
        finally:
            with contextlib.suppress(Exception):
                await r.aclose()
        out: dict[str, int] = {}
        for k, v in (raw or {}).items():
            with contextlib.suppress(TypeError, ValueError):
                out[k] = int(v)
        return out
    except Exception:
        return {}


def render_tick_mode_health(counters: Mapping[str, int]) -> list[str]:
    """Daily-report lines. Silent on a clean day: this alarm shares the report
    with 6.8.6's feed-staleness header, and two green ticks for the same class of
    problem is noise. Loud when the feed degraded."""
    degraded = counters.get("degraded", 0)
    missing = counters.get("depth_missing", 0)
    if not degraded and not missing:
        return []
    full = counters.get("full", 0)
    modes = " · ".join(
        f"{k.split(':', 1)[1]} {v}" for k, v in sorted(counters.items()) if k.startswith("mode:")
    )
    out = [
        "> ## ⚠️ TICK-MODE DEGRADATION (A25)",
        ">",
        "> The live feed delivered ticks the depth path cannot use, so "
        "`depth:{stock_id}` went stale for those stocks and their paper fills "
        "silently fell back to the flat `paper_slippage_bps` floor — **fills "
        "cheaper than reality, on the book expectancy is judged with**.",
        ">",
    ]
    if degraded:
        out.append(
            f"> - **Non-full-mode ticks:** **{degraded:,}** vs {full:,} full "
            f"({modes or 'mode unrecorded'}) — Kite downgraded a MODE_FULL "
            "subscription. Remedy: restart live-worker to re-subscribe."
        )
    if missing:
        out.append(
            f"> - **Full-mode ticks with no usable book:** **{missing:,}** — "
            "one-sided/crossed/empty depth. Normal around the open; a large "
            "count during the session is not."
        )
    out.append("")
    return out
