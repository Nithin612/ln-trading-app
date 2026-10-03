"""A41 cutover — copy the DURABLE-class keys from the main Redis to the durable one.

Run ONCE, with every worker STOPPED (`make worker`, `make live-worker`), after
`make up` has started `redis-durable` and BEFORE the env points at it:

  uv run python scripts/redis_split_cutover.py --target redis://localhost:6380/0          # dry run
  uv run python scripts/redis_split_cutover.py --target redis://localhost:6380/0 --apply

What moves (the A41 inventory, 2026-10-03): the alerts stream WITH its consumer group
(`outcome-recorder`'s offset + pending list are the at-least-once state — DUMP/RESTORE
carries them), the 7-day `tickmode:health:*` / `provisional:health:*` records and the
30-day universe-guard baseline. Each is copied with its REMAINING TTL. Source keys are
left in place so a rollback is "unset REDIS_DURABLE_URL" — the health records expire on
their own, but `alerts:live` has NO TTL: `DEL` it on the old instance once the split is
verified (RUNBOOK §9e).

Refuses: target == source · any fresh worker heartbeat (a running worker would keep
writing the old instance mid-copy) · a non-empty Celery queue on EITHER broker (old =
db 1 of the source instance, new = `--new-broker`; the queue is not copied, so a
non-empty one would be lost on restart) · any durable key already on the target (exit 4,
nothing copied) unless --replace. Run it BEFORE editing `.env`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import redis as redis_sync  # noqa: E402
from app.broker.provisional import HEALTH_KEY  # noqa: E402
from app.broker.tick_mode import TICK_MODE_HEALTH_KEY  # noqa: E402
from app.broker.universe_guard import UNIVERSE_KEY  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.worker_health import HEARTBEAT_KEY  # noqa: E402


def durable_patterns() -> list[str]:
    """The durable families, each read from its owning constant (W5)."""
    return [
        settings.live_alert_stream,
        TICK_MODE_HEALTH_KEY.format(day="*"),
        HEALTH_KEY.format(day="*"),
        UNIVERSE_KEY,
    ]


@dataclass
class Plan:
    key: str
    ttl_ms: int  # -1 = no TTL
    exists_on_target: bool


def plan(source: Any, target: Any) -> list[Plan]:
    out: list[Plan] = []
    for pattern in durable_patterns():
        for raw in source.scan_iter(match=pattern, count=500):
            key = raw.decode() if isinstance(raw, bytes) else raw
            out.append(Plan(key, int(source.pttl(key)), bool(target.exists(key))))
    return sorted(out, key=lambda p: p.key)


def fresh_heartbeats(source: Any) -> list[str]:
    keys = source.keys(HEARTBEAT_KEY.format(role="*"))
    return sorted(k.decode() if isinstance(k, bytes) else k for k in keys)


def restore_ttl_ms(pttl: int) -> int | None:
    """PTTL → RESTORE's ttl argument, where RESTORE's 0 means "no expiry".

    -1 (persistent) → 0 · a positive PTTL → itself · 0 or -2 (expiring this millisecond,
    or gone) → None = skip. Mapping a PTTL of 0 to 0 would make a TTL'd record PERMANENT
    on a noeviction instance (bug-hunter 2026-10-03)."""
    if pttl == -1:
        return 0
    return pttl if pttl > 0 else None


def copy(source: Any, target: Any, items: list[Plan], *, replace: bool) -> int:
    """DUMP/RESTORE each key with its remaining TTL. Returns the number copied.
    Callers refuse BEFORE this when a key exists on the target and replace is False."""
    copied = 0
    for p in items:
        if p.exists_on_target and not replace:
            raise ValueError(f"{p.key} exists on target — refuse, or pass replace")
        ttl = restore_ttl_ms(int(source.pttl(p.key)))  # re-read: time passed since plan
        blob = source.dump(p.key)
        if ttl is None or blob is None:
            continue
        target.restore(p.key, ttl, blob, replace=replace)
        copied += 1
    return copied


def queue_lengths(urls: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for url in dict.fromkeys(urls):
        client: Any = redis_sync.from_url(url)  # sync client; redis-py types it as a union
        out[url] = int(client.llen("celery"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--source", default=settings.redis_url)
    ap.add_argument("--target", default=settings.durable_redis_url)
    ap.add_argument("--apply", action="store_true", help="copy (default: dry run)")
    ap.add_argument("--replace", action="store_true", help="overwrite keys already on target")
    ap.add_argument(
        "--new-broker",
        default=settings.celery_broker_url,
        help="the broker the workers will use after the split (default: CELERY_BROKER_URL)",
    )
    args = ap.parse_args()

    if args.source == args.target:
        print(f"source == target ({args.source}) — nothing to split. Pass --target.")
        return 2
    source = redis_sync.from_url(args.source)
    target = redis_sync.from_url(args.target)

    beats = fresh_heartbeats(source)
    if beats:
        print(f"REFUSED: fresh worker heartbeats {beats} — stop every worker first.")
        return 3

    old_broker = args.source.rsplit("/", 1)[0] + "/1"
    queues = queue_lengths([old_broker, args.new_broker])
    for url, n in queues.items():
        print(f"celery queue length on {url}: {n}")
    if any(queues.values()):
        print("REFUSED: a Celery queue is not empty — it is not copied, and would be lost.")
        return 5

    items = plan(source, target)
    print(f"{len(items)} durable key(s) on {args.source}:")
    for p in items:
        ttl = "no TTL" if p.ttl_ms < 0 else f"TTL {p.ttl_ms // 1000}s"
        note = "  ⚠ EXISTS on target" if p.exists_on_target else ""
        print(f"  {p.key:40s} {ttl}{note}")
    clashes = [p.key for p in items if p.exists_on_target]
    if clashes and not args.replace:
        print(f"REFUSED: {clashes} already on the target — inspect, then --replace.")
        return 4
    if not args.apply:
        print("dry run — pass --apply to copy")
        return 0
    n = copy(source, target, items, replace=args.replace)
    print(f"copied {n} of {len(items)} → {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
