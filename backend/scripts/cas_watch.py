"""CAS watch — the A40 absence alarm, run from CRON so it does not depend on Celery beat.

Why cron (2026-10-02): on 2026-10-01 `make live-worker` ran all day while `make worker` (Celery
worker + beat) never did, so the CAS capture and the post-close capture both recorded nothing.
The coverage check was itself a beat task, so it was down for exactly the reason it existed to
report. This process shares nothing with either worker except the database and Redis.

Each run evaluates `worker_health.cas_watch_alerts` for "now" and pushes what it returns:
  - 14:30–15:33 IST with the `celery` heartbeat stale  → "make worker is NOT running"
  - after 15:33 with zero `cas_daily` rows             → auction window missed
  - after 16:05 with zero `cas_postclose_daily` rows   → post-close window missed
Holidays and weekends push nothing — the NSE calendar decides, not the cron line.

Read-only. Exit 0 whatever it finds (cron mails/logs a non-zero exit, and a missed window is
not a crash of this script); exit 1 only if the check itself could not run.

Usage (cron sets NOTIFIER_DESKTOP=true so the alarm reaches the desktop):
    uv run python scripts/cas_watch.py
    uv run python scripts/cas_watch.py --dry-run                 # print, push nothing
    uv run python scripts/cas_watch.py --at 2026-10-01T15:40     # replay a past moment

⚠ `--at` replays the ROW COUNTS faithfully but reads TODAY's heartbeat, which has a 600 s TTL —
a past heartbeat cannot be reconstructed, so the liveness alarm in a replay reflects now.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.notifier import Notification, dispatch  # noqa: E402
from app.services.worker_health import (  # noqa: E402
    cas_coverage,
    cas_watch_alerts,
    read_statuses,
)

_IST = ZoneInfo("Asia/Kolkata")


async def evaluate(now: datetime) -> list[Notification]:
    """Gather the inputs and return what should be pushed. Separated from `main` for tests."""
    day = now.astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        cov = await cas_coverage(db, day=day, now=now)
    (celery,) = await read_statuses({"celery": "CAS capture + every beat-driven task"}, now=now)
    return cas_watch_alerts(cov, celery, now=now)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print alerts, push nothing")
    parser.add_argument(
        "--at",
        type=datetime.fromisoformat,
        default=None,
        help="evaluate as of this IST time, e.g. 2026-10-01T15:40 (replay; implies --dry-run)",
    )
    args = parser.parse_args(argv)
    if args.at is not None:
        args.dry_run = True
        at = args.at if args.at.tzinfo else args.at.replace(tzinfo=_IST)
        now = at.astimezone(UTC)
    else:
        now = datetime.now(tz=UTC)
    stamp = now.astimezone(_IST).strftime("%Y-%m-%d %H:%M IST")
    try:
        alerts = asyncio.run(evaluate(now))
    except Exception as exc:  # noqa: BLE001 — the check failing is itself worth a push
        from app.services.notifier import notify_exception

        notify_exception("cas_watch", "CAS watch could not run", exc)
        print(f"{stamp} cas_watch ERROR {type(exc).__name__}: {exc}")
        return 1
    if not alerts:
        print(f"{stamp} cas_watch ok — nothing to report")
        return 0
    for n in alerts:
        if args.dry_run:
            print(f"{stamp} cas_watch WOULD PUSH: {n.render()!r}")
            continue
        r = dispatch(n)
        print(
            f"{stamp} cas_watch PUSHED {n.event} desktop={r.desktop_sent} "
            f"webhook={'sent' if r.delivery and r.delivery.sent else 'no'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
