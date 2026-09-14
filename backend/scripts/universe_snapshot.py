"""D2′a — evaluate the universe rule: record the day's membership, or show the diff.

    uv run python scripts/universe_snapshot.py --diff          # default, read-only
    uv run python scripts/universe_snapshot.py --materialise   # write today's snapshot

⚠ `--diff` and `--materialise` are SHADOW: neither writes `is_active`. **`--apply` is the
one path that does** (D2′b) — a database trigger refuses every other writer, because three
uncoordinated writers is what broke the universe on 2026-09-07.

`--diff` reports what adopting the rule WOULD do; `--materialise` records membership in
`universe_snapshot`; `--apply` does both and then adopts the recorded verdict.
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
from app.services.universe_materialiser import (  # noqa: E402
    apply_to_stocks,
    diff_against_live,
    load_inputs,
    materialise,
)
from app.services.universe_rule import RULE_VERSION  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")


async def _run(write: bool, apply: bool = False) -> int:
    today = datetime.now(UTC).astimezone(_IST).date()
    async with AsyncSessionFactory() as db:
        inputs = await load_inputs(db)
        print(
            f"rule {RULE_VERSION}: EQUITY_L EQ={len(inputs.eq_listed)} · "
            f"kite EQ={len(inputs.kite_tradable)}"
        )

        d = await diff_against_live(db, inputs=inputs)
        print(
            f"\nagreement: {d.agree_active} active · {d.agree_inactive} inactive"
            f"\nWOULD ACTIVATE   {len(d.would_activate)}"
            f"\nWOULD DEACTIVATE {len(d.would_deactivate)}"
        )
        if d.would_activate:
            print("  + " + ", ".join(d.would_activate[:15])
                  + ("…" if len(d.would_activate) > 15 else ""))
        if d.would_deactivate:
            reasons: dict[str, int] = {}
            for _sym, reason in d.would_deactivate:
                reasons[reason] = reasons.get(reason, 0) + 1
            print("  - by reason: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))
            print("  - " + ", ".join(s for s, _ in d.would_deactivate[:15])
                  + ("…" if len(d.would_deactivate) > 15 else ""))

        if write or apply:
            n = await materialise(db, as_of=today, inputs=inputs)
            print(f"\nuniverse_snapshot {today}: {n} member(s) recorded")
        else:
            print("\n(read-only — pass --materialise to record the snapshot)")

        if apply:
            activated, deactivated = await apply_to_stocks(db, as_of=today)
            print(
                f"applied to stocks.is_active: +{activated} activated, "
                f"-{deactivated} deactivated"
            )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="evaluate the universe rule (shadow only)")
    p.add_argument("--materialise", action="store_true", help="record today's snapshot")
    p.add_argument("--diff", action="store_true", help="report the diff only (default)")
    p.add_argument(
        "--apply",
        action="store_true",
        help="materialise AND write stocks.is_active (the only path that may)",
    )
    args = p.parse_args()
    return asyncio.run(_run(write=args.materialise, apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
