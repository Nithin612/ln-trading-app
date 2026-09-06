"""Provisional-layer health: did the hot-set cap stop biting, and does the
cadence still overrun?

Read-only. Two independent sides, deliberately:

  MEASURED  — `provisional:health:{day}` as the worker's own refresher thread
              recorded it (cumulative per IST session day, TTL one week). This
              is the only durable record of cadence/clip health: `make
              live-worker` writes no log file, so before this key a day's
              evidence lived in a terminal and died with it.
  INDEPENDENT — the hot-set INPUT recomputed here from Postgres + the alert
              stream, the same way `load_hot_set` assembles it. It answers
              "how big WOULD the hot set be" without trusting the worker, so a
              filter that silently stopped working is still visible.

Usage:
    uv run python scripts/provisional_health.py            # last 7 days
    uv run python scripts/provisional_health.py --days 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import redis as redis_sync  # noqa: E402
from app.broker.provisional import (  # noqa: E402
    _IST,
    HEALTH_KEY,
    _recent_alert_sids,
    read_cycle_stats,
)
from app.core.config import settings  # noqa: E402
from app.services.notifier import (  # noqa: E402
    Level,
    Notification,
    notify,
    notify_exception,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402


def _alert_tag_mix(redis: Any) -> tuple[Counter[str], Counter[str]]:
    """Whole-stream tag mix: entries and DISTINCT stocks per tag. Market-level
    tags are what flooded the cap, so their share is the thing to watch."""
    entries: Counter[str] = Counter()
    stocks: dict[str, set[str]] = {}
    last = "+"
    while True:
        page = redis.xrevrange(settings.live_alert_stream, max=last, count=500)
        for _eid, fields in page:
            tag = str(fields.get("tag", "?"))
            style = str(fields.get("style", "market"))
            key = f"{tag} [{'market' if style == 'market' else 'signal-bound'}]"
            entries[key] += 1
            stocks.setdefault(key, set()).add(str(fields.get("sid")))
        if len(page) < 500:
            break
        last = "(" + page[-1][0]
    return entries, Counter({k: len(v) for k, v in stocks.items()})


async def _hot_set_input(db: Any, redis: Any, now_utc: datetime) -> dict[str, int]:
    """Recompute the hot-set INPUT (pre-cap), independent of the worker."""
    signal_stocks = (
        await db.execute(
            text(
                "SELECT count(DISTINCT stock_id) FROM signals WHERE status = 'active'"
                " AND (validity_until IS NULL OR validity_until > now())"
            )
        )
    ).scalar() or 0
    watchlist = (
        await db.execute(
            text(
                "SELECT count(DISTINCT wi.stock_id) FROM watchlist_items wi"
                " JOIN stocks st ON st.id = wi.stock_id WHERE st.is_active"
            )
        )
    ).scalar() or 0
    triggers, market_ordered = _recent_alert_sids(redis, now_utc)
    trigger_active = 0
    if triggers:
        trigger_active = (
            await db.execute(
                text("SELECT count(*) FROM stocks WHERE id = ANY(:s) AND is_active"),
                {"s": sorted(triggers)},
            )
        ).scalar() or 0
    market_admitted = min(
        len(market_ordered), settings.live_provisional_trigger_market_max
    )
    return {
        "signal": int(signal_stocks),
        "trigger": int(trigger_active),
        "watchlist": int(watchlist),
        # what the discovery dial would admit, and what it is declining
        "market_admitted": int(market_admitted),
        "market_available": int(len(market_ordered)),
        # an upper bound: the three sources overlap, so the real raw hot set
        # is ≤ this — good enough to see whether the CAP is threatened
        "raw_upper_bound": (
            int(signal_stocks)
            + int(trigger_active)
            + int(watchlist)
            + int(market_admitted)
        ),
        "cap": settings.live_provisional_hotset_max,
    }


def _verdict(days: list[dict[str, Any]]) -> str:
    """Is the cadence change (option 2) required?"""
    scored = [d for d in days if d.get("cycles")]
    if not scored:
        return "NO DATA — no session recorded a cycle yet."
    clip = max(d.get("clip_pct", 0.0) for d in scored)
    overrun = max(d.get("overrun_pct", 0.0) for d in scored)
    mean = max(d.get("elapsed_mean_ms", 0.0) for d in scored)
    cadence = max(d.get("cadence_ms", 0.0) for d in scored)
    lines = [
        f"worst clip_pct={clip:.1f}%  worst overrun_pct={overrun:.1f}%  "
        f"worst mean cycle={mean:.0f} ms vs cadence {cadence:.0f} ms",
    ]
    if clip > 0:
        lines.append(
            "CLIPPING STILL BITES — the filter did not settle it; look at the "
            "hot-set input below before touching the cadence."
        )
    else:
        lines.append("CLIPPING RESOLVED — the cap no longer binds.")
    if overrun >= 20.0 or mean > cadence:
        lines.append(
            f"OPTION 2 REQUIRED — cycles still miss the {cadence:.0f} ms target; "
            "raise live_provisional_refresh_s to fit the measured cost."
        )
    elif overrun > 0:
        lines.append(
            "OPTION 2 OPTIONAL — occasional overruns only (they self-throttle, "
            "never queue)."
        )
    else:
        lines.append("OPTION 2 NOT REQUIRED — no overruns.")
    return "\n".join(lines)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    redis = redis_sync.from_url(settings.redis_url, decode_responses=True)
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    now_utc = datetime.now(tz=UTC)
    today = now_utc.astimezone(_IST).date()

    print(f"── provisional health @ {now_utc.astimezone(_IST):%Y-%m-%d %H:%M %Z} ──")
    print(
        f"knobs: cadence={settings.live_provisional_refresh_s}s "
        f"cap={settings.live_provisional_hotset_max} "
        f"market_max={settings.live_provisional_trigger_market_max} "
        f"trigger_window={settings.live_provisional_trigger_window_s}s"
    )

    print("\nMEASURED (worker's own per-day counters)")
    days: list[dict[str, Any]] = []
    for back in range(args.days):
        day = (today - timedelta(days=back)).isoformat()
        doc = read_cycle_stats(redis, day)
        if doc is None:
            continue
        days.append(doc)
        last = doc.get("last", {})
        # `as_of` is the staleness signal the key documents — a thread that
        # died at 10:05 leaves plausible-looking counters and nothing else
        # says so. Every field via .get: one schema change must not turn the
        # health report into a KeyError.
        as_of = doc.get("as_of", "?")
        try:
            as_of = datetime.fromisoformat(str(as_of)).astimezone(_IST).strftime(
                "%H:%M:%S IST"
            )
        except (TypeError, ValueError):
            pass
        flag = "  ⚠ SEED FAILED (undercounts)" if doc.get("seed_failed") else ""
        print(
            f"  {day}  last write {as_of}  cycles={doc.get('cycles', 0):>6}  "
            f"overrun={doc.get('overrun_pct', 0.0):>5.1f}%  "
            f"clip={doc.get('clip_pct', 0.0):>5.1f}%  "
            f"mean={doc.get('elapsed_mean_ms', 0.0):>6.0f}ms  "
            f"max={doc.get('elapsed_max_ms', 0.0):>6.0f}ms  "
            f"restarts={doc.get('restarts', 0)}{flag}"
        )
        # A26: a protected overflow means the cap was knowingly exceeded to avoid
        # dropping committed work. It must be impossible to miss in this readout — the
        # original incident hid in a log line for weeks.
        overflow = last.get("protected_overflow") or 0
        over_txt = f", ⛔ PROTECTED OVERFLOW {overflow}" if overflow else ""
        print(
            f"      last cycle: hot={last.get('hot')} (raw {last.get('hot_raw')}, "
            # a stock can hold several sources, so these OVERLAP — they are
            # not a partition of `hot`
            f"clipped {last.get('clipped')}{over_txt})  "
            f"src (overlapping) sig/trig/wl/mkt="
            f"{last.get('src_signal')}/{last.get('src_trigger')}/"
            f"{last.get('src_watchlist')}/{last.get('src_market')}  "
            f"engine_calls={last.get('engine_calls')}  windows={last.get('windows')}"
        )
        if overflow:
            print(
                f"      ⛔ the hot-set cap ({overflow} over) could not hold every "
                "signal/trigger-bound stock. REMEDY: raise `live_provisional_hotset_max`."
            )
            # A26's escalation, now pushed rather than only printed — a signal-bound stock
            # that is never scored is a signal that silently does not exist, and the
            # original incident hid in a log line for weeks.
            notify(
                Notification(
                    event="provisional_overflow",
                    level=Level.WARNING,
                    title="Hot-set cap exceeded by protected stocks",
                    lines=[
                        f"day={day} protected_overflow={overflow}",
                        f"cap={settings.live_provisional_hotset_max}",
                        "REMEDY: raise `live_provisional_hotset_max`",
                    ],
                )
            )
    if not days:
        print(f"  (no {HEALTH_KEY.format(day='<day>')} key in the last {args.days} days")
        print("   — the worker did not run, or ran before this build)")
        # A11 — THE alarm this script exists for. No health key across the whole window
        # means the provisional layer has not run, and today that is discovered only by
        # someone remembering to run this script (it has no scheduler at all).
        notify(
            Notification(
                event="provisional_health",
                level=Level.ERROR,
                title="Provisional layer silent",
                lines=[
                    f"no {HEALTH_KEY.format(day='<day>')} key in the last {args.days} days",
                    "the live-worker's provisional layer did not run",
                    "REMEDY: check `make live-worker` is up; keys carry a 7-day TTL",
                ],
            )
        )

    print("\nINDEPENDENT (hot-set input recomputed now)")
    async with AsyncSession(engine) as db:
        inp = await _hot_set_input(db, redis, now_utc)
    fits = "fits" if inp["raw_upper_bound"] <= inp["cap"] else "OVER CAP"
    print(
        f"  signal={inp['signal']}  trigger={inp['trigger']}  "
        f"watchlist={inp['watchlist']}  market={inp['market_admitted']}"
        f"/{inp['market_available']} admitted  →  ≤{inp['raw_upper_bound']} vs "
        f"cap {inp['cap']}  ({fits})"
    )
    idle = inp["cap"] - inp["raw_upper_bound"]
    if idle > 0 and inp["market_available"] > inp["market_admitted"]:
        print(
            f"  {idle} of {inp['cap']} slots idle while "
            f"{inp['market_available'] - inp['market_admitted']} breadth-movers go "
            f"unscored — `live_provisional_trigger_market_max` is the dial"
        )

    print("\nALERT STREAM tag mix (whole stream)")
    entries, stocks = _alert_tag_mix(redis)
    for key, count in entries.most_common():
        print(f"  {key:<34} {count:>6} entries  {stocks[key]:>5} stocks")

    print(f"\nVERDICT\n{_verdict(days)}")
    await engine.dispose()
    redis.close()


if __name__ == "__main__":
    # A11 — an exception here always notifies. This script is the forward watch for a
    # failure that degrades silently, so it failing quietly would be the worst case.
    try:
        asyncio.run(main())
    except BaseException as exc:  # noqa: BLE001 — notified, then re-raised
        notify_exception("provisional_health", "provisional-health check failed", exc)
        raise
