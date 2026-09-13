"""U1 — the live worker's subscription-universe startup guard.

⛔ **The failure this exists for.** Between 2026-09-07 and 09-12 the dev DB's
`kite_instruments` table was empty, so `_build_token_stock_map` returned `{}`
and `live_worker` came up every morning logging

    live-worker up: 0 instruments, session 2026-09-XX

and then ran a full session doing nothing. **A zero was indistinguishable from
a quiet market**, because nothing asserted that the universe was non-empty. Five
sessions of tick, CAS and intraday capture were lost permanently — capture is
real-time-only and cannot be back-filled.

The guard therefore refuses to start rather than running dark, on two
conditions:

  * **EMPTY** — a universe of 0 can never be correct; there is no market in
    which the worker has nothing to subscribe to.
  * **FLOOR** — below `min_count` instruments outright. A ratio test alone
    cannot catch a collapse that arrives in small steps, and it has nothing to
    compare against on a first run.
  * **COLLAPSE** — a universe below `min_fraction` of the **high-water** size.
    This mirrors `_SWEEP_MIN_FRACTION` in `kite_client`, which protects the
    instrument sweep from a truncated dump for the same reason.

⚠ **The baseline RATCHETS UP ONLY, and that is load-bearing** (bug-hunter,
2026-09-13). Re-recording every accepted start compares each morning only
against the morning before, so a collapse delivered in sub-threshold steps is
accepted at every step and silently becomes the new bar: from 2,655, six
consecutive 45 % drops (2655 → 1460 → 803 → 441 → 242 → 133) all pass a 50 %
ratio test. **95 % of the universe gone, guard silent.** Nor is that a margin
case — the real 2026-09-07 event was 1,182 of 2,646 = 44.7 %, clearing the 50 %
bar by 5.3 points, so a slightly milder `is_active` regression fires nothing
*and then becomes the baseline*.

⚠ **The cost of the ratchet, stated:** a universe that legitimately shrinks for
good needs ONE manual baseline reset. Organic drift cannot reach 50 % (NSE
listings grow), and the refusal message carries the exact command.

⚠ The collapse arm deliberately does NOT fire on the first ever run (no
previous count recorded) or on GROWTH. A universe that doubles is a repaired
universe, which is exactly what the pending rebuild will produce.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# Redis, not the DB: this is worker-local operational state, and the worker
# already holds a Redis handle at the point the guard runs. TTL per the Redis
# contract (trading-domain.md) — long enough to survive a holiday stretch,
# short enough that a months-idle worker starts from a clean slate rather than
# comparing against a universe from another era.
UNIVERSE_KEY = "liveworker:universe:last"
UNIVERSE_TTL_S = 30 * 86_400


_RESET_CMD = (
    "cd backend && uv run python -c \"import redis; from app.core.config import "
    f"settings; redis.from_url(settings.redis_url).delete('{UNIVERSE_KEY}')\""
)


def assess_universe(
    count: int, previous: int | None, min_fraction: float, min_count: int = 0
) -> str | None:
    """Return a refusal reason, or None when the universe is usable.

    Pure: no Redis, no clock. `previous is None` means "never recorded".
    """
    if count <= 0:
        return (
            "subscription universe is EMPTY — kite_instruments is unpopulated or the "
            "join to active stocks yields nothing. Run "
            "`app.tasks.market_data_tasks.sync_kite_instruments` (or POST "
            "/broker/kite/instruments/sync), verify stocks.is_active, then restart. "
            "Refusing to start: a dark session cannot be back-filled."
        )
    if min_count and count < min_count:
        return (
            f"subscription universe {count} is below the absolute floor {min_count}. "
            "A ratio test cannot see a collapse that arrives in small steps, or one that "
            "happens before any baseline exists — this arm can. Refusing to start; fix "
            "the universe, or lower LIVE_UNIVERSE_MIN_COUNT if the shrink is intended."
        )
    if previous is not None and previous > 0 and count < min_fraction * previous:
        return (
            f"subscription universe COLLAPSED: {count} instruments vs a high-water "
            f"{previous} (< {min_fraction:.0%}). A real market never does this; a bad "
            "instruments dump or a universe write does. Refusing to start — investigate, "
            f"then clear the baseline to accept the new size:  {_RESET_CMD}"
        )
    return None


def check_and_record_universe(
    redis_client: Any, count: int, min_fraction: float, min_count: int = 0
) -> str | None:
    """Assess `count` against the high-water size, then ratchet the baseline.

    Fails OPEN on any Redis error: the guard must never be the reason a healthy
    worker cannot start. The EMPTY and FLOOR arms are evaluated first and need no
    Redis, so they survive an outage of the very thing that stores the baseline.
    """
    previous: int | None = None
    try:
        raw = redis_client.get(UNIVERSE_KEY)
        if raw is not None:
            previous = int(raw)
    except Exception:  # noqa: BLE001 — a guard must not block a healthy start
        log.warning("universe guard: previous size unreadable; collapse arm skipped")

    reason = assess_universe(count, previous, min_fraction, min_count)
    if reason is not None:
        return reason

    try:
        if previous is None or count > previous:
            redis_client.set(UNIVERSE_KEY, count, ex=UNIVERSE_TTL_S)
        else:
            # Accepted, but SMALLER: keep the high-water mark and only refresh its
            # lifetime. Writing `count` here is what lets a staged collapse walk
            # under the guard one sub-threshold step at a time.
            redis_client.expire(UNIVERSE_KEY, UNIVERSE_TTL_S)
    except Exception:  # noqa: BLE001
        log.warning("universe guard: could not record size %d", count)
    return None
