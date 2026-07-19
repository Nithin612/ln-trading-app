"""Shadow-week runner — Rust vs frozen-Python decision double-check on a
day's committed 1d closes (Phase 3, slice 3.7).

Usage:
    uv run python scripts/shadow_week.py [--day YYYY-MM-DD]

Run once per trading day after EOD ingestion for the shadow week. Scores
every active stock's committed 1d close under BOTH engine implementations
(services/shadow_compare.sweep_day) and asserts ZERO decision diffs — the
UPGRADE_PLAN Phase-3 exit criterion. SCOPE: the BASE (flow-free) 1d
decision — the only Rust-vs-Python parity domain (tradecore raises on
flows/multipliers); the day's excluded §2.7 flows are stamped in the
report, and the committed nightly decision (which folds those flows) may
differ. Writes a per-day report to backend/shadow/shadow-<day>.json and
EXITS NONZERO on any diff OR error (so a cron/daily run fails loudly).
Read-only: never writes signals, outcomes, or engine state.

Default --day = today IST. Prior days re-compare faithfully (the window
loader takes an as-of cutoff), so a missed day can be run later.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Runnable from any cwd: backend/ (the `app` package root) onto sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.shadow_compare import sweep_day  # noqa: E402

_SHADOW_DIR = Path(__file__).resolve().parent.parent / "shadow"


async def run(day: date) -> int:
    print(f"shadow compare: 1d closes for {day.isoformat()}", flush=True)
    async with AsyncSessionFactory() as db:
        report = await sweep_day(db, day)

    _SHADOW_DIR.mkdir(exist_ok=True)
    out = _SHADOW_DIR / f"shadow-{day.isoformat()}.json"
    out.write_text(
        json.dumps(
            {
                "summary": report.summary(),
                "diffs": [d.to_dict() for d in report.diffs],
                # errors trip the nonzero exit too — the failing symbols +
                # reasons must live in the artifact, not just ephemeral logs
                # (bug-hunter MEDIUM 2026-07-19).
                "errors": [
                    {"stock_id": e.stock_id, "symbol": e.symbol, "detail": e.detail}
                    for e in report.errors
                ],
            },
            indent=2,
        )
    )
    print(json.dumps(report.summary(), indent=2), flush=True)
    print(f"report → {out}", flush=True)

    if not report.clean:
        print(
            f"SHADOW FAIL: {len(report.diffs)} decision diff(s), "
            f"{len(report.errors)} error(s) — Rust and the frozen reference "
            "disagree (or a window failed) on live data. Investigate before "
            "closing Phase 3 (zero diffs required).",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"shadow clean: {report.matched}/{report.compared} closes matched exactly "
        f"({report.both_emitted} were live signals agreed by both engines; "
        f"{report.skipped_no_data} skipped, insufficient history). "
        f"NOTE base decision only — excluded flows {report.flows_excluded}.",
        flush=True,
    )
    return 0


def _parse_day(raw: str | None) -> date:
    if raw is None:
        return datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
    return date.fromisoformat(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="shadow-week decision double-check")
    parser.add_argument("--day", default=None, help="YYYY-MM-DD (default: today IST)")
    args = parser.parse_args(argv)
    return asyncio.run(run(_parse_day(args.day)))


if __name__ == "__main__":
    raise SystemExit(main())
