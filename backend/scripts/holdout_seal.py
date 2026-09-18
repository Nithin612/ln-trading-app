"""Queue items 11 and 11b — seal the two holdout blocks, and verify a seal later.

⭐ **What a seal is FOR.** The holdouts exist so that, if the scorer ever earns a real
out-of-sample test, the test is credible. Credibility needs two things this script
provides and nothing else in the repo does:

1. **Proof the block did not change between sealing and opening.** Not "we promise we
   didn't look" — a digest that fails if a single price moved, a row was added, or a
   corporate action was retro-adjusted.
2. **A written whitelist of what may be computed WHILE SEALED.** Row counts, session
   counts and integrity digests carry no information about returns, so computing them
   costs nothing. Anything touching the direction or magnitude of a price does, and is
   forbidden. Without the list written down, "I only checked the data was fine" becomes
   an unfalsifiable claim after the fact.

⛔⛔ **THE DEFECT THIS SCRIPT FOUND WHILE BEING WRITTEN: the block sizes were quoted as
`313 + 617 + 797 = 1,727`, and the test block is now 798.** The holdouts are CLOSED
date intervals and are immutable; the test block is OPEN-ENDED and gains a row every
session. **`797` was never a property of the design — it was a timestamp**, and item 5's
pre-registration inherits that. ⇒ every block here is pinned by its DATE RANGE, which is
the immutable thing, and the session count is recorded as an OUTPUT measured `as_of` a
date. A later item-5 run reporting 798 or 810 sessions is not scope drift; a later run
reporting a different *holdout* digest is.

⚠ **What this does NOT do.** It does not prevent reading the holdout — nothing can, the
rows are in the same database. It makes reading it *detectable only if the reader also
writes*, which is the honest limit of a seal over data you own. Its real value is against
the failure that actually happens here: a block being silently re-ingested, back-filled or
CA-adjusted between the decision to hold it out and the day it is opened, so that the
"out-of-sample" test runs on data that moved in the meantime.

Usage
-----
    uv run python scripts/holdout_seal.py --write     # create/refresh the seal file
    uv run python scripts/holdout_seal.py             # verify current DB against it
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

SEAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "analysis" / "holdout-seals.json"

#: ⭐ Pinned by DATE RANGE, never by session count — see the module docstring. `open_ended`
#: marks the block that keeps growing, so a changed count there is expected and a changed
#: count in a holdout is an alarm.
BLOCKS: tuple[dict[str, Any], ...] = (
    {
        "name": "holdout-2",
        "lo": date(2019, 10, 1),
        "hi": date(2020, 12, 31),
        "open_ended": False,
        "why": (
            "The only crash regime in the archive (COVID). Decided in §12.7, dropped by "
            "§12.12, restored as queue item 11b. ⚠ `liquid_as_of` cannot be applied "
            "INSIDE it — there is no prior 180-day ranking window at the archive's start."
        ),
    },
    {
        "name": "holdout-1",
        "lo": date(2021, 1, 1),
        "hi": date(2023, 7, 2),
        "open_ended": False,
        "why": (
            "Recovered by the 2026-09-17 back-fill and seen by no study or reviewer. "
            "Contains the 2022 zero-drift regime (−0.1%/yr, 42.7% down-days) that every "
            "prior verdict was missing. Opens ONCE, after item 5, and only on item 19's "
            "≥0.0499 branch."
        ),
    },
    {
        "name": "test",
        "lo": date(2023, 7, 3),
        "hi": date(2099, 1, 1),
        "open_ended": True,
        "why": (
            "The working block — item 5's E2 re-run lives here. NOT a holdout and not "
            "sealed against change; recorded only so the three provably partition the "
            "archive with nothing unaccounted for."
        ),
    },
)

#: ⭐ THE WHITELIST. Computable while sealed because none of it is a function of the
#: direction or magnitude of a return. Anything not on this list requires opening.
WHITELIST = (
    "count of sessions in the block",
    "count of bars in the block",
    "count of distinct stocks in the block",
    "first and last session date",
    "the per-session and per-block integrity digests below",
)

FORBIDDEN = (
    "any return, excess return, IC, hit rate, drawdown or P&L computed on these rows",
    "any model fit, threshold choice, factor selection or hyper-parameter tuned on them",
    "any 'quick look' at a chart of them — the eye is a model with unrecorded parameters",
)


async def _digest(db: Any, lo: date, hi: date) -> dict[str, Any]:
    """Per-session digests, then one digest over those.

    ⚠ Hashed IN POSTGRES rather than streaming ~1.5M rows into Python: same guarantee,
    a fraction of the time. ⚠ `ORDER BY` inside `string_agg` is load-bearing — without it
    the aggregate order is unspecified and the digest would differ run to run, which would
    make the seal fire constantly and then be ignored, which is worse than no seal.
    """
    rows = (
        await db.execute(
            text(
                "SELECT time::date AS d, count(*) AS bars, count(DISTINCT stock_id) AS names, "
                "       md5(string_agg(stock_id::text || ':' || open::text || ':' || high::text "
                "                      || ':' || low::text || ':' || close::text || ':' "
                "                      || volume::text, ',' ORDER BY stock_id)) AS sig "
                "FROM ohlcv_1d WHERE time::date BETWEEN :lo AND :hi "
                "GROUP BY time::date ORDER BY time::date"
            ),
            {"lo": lo, "hi": hi},
        )
    ).all()
    if not rows:
        raise SystemExit(f"no rows between {lo} and {hi} — refusing to seal an empty block")

    import hashlib

    block_sig = hashlib.md5(  # noqa: S324  (integrity, not security)
        ",".join(f"{r.d.isoformat()}:{r.sig}" for r in rows).encode()
    ).hexdigest()
    return {
        "sessions": len(rows),
        "bars": sum(int(r.bars) for r in rows),
        "distinct_stocks_max_session": max(int(r.names) for r in rows),
        "first_session": rows[0].d.isoformat(),
        "last_session": rows[-1].d.isoformat(),
        "block_digest": block_sig,
        "session_digests": {r.d.isoformat(): r.sig for r in rows},
    }


async def build() -> dict[str, Any]:
    async with AsyncSessionFactory() as db:
        total = (
            await db.execute(text("SELECT count(DISTINCT time::date) FROM ohlcv_1d"))
        ).scalar_one()
        out: dict[str, Any] = {
            "sealed_at": datetime.now(tz=UTC).isoformat(),
            "archive_sessions_at_seal": int(total),
            "whitelist": list(WHITELIST),
            "forbidden": list(FORBIDDEN),
            "blocks": {},
        }
        covered = 0
        for b in BLOCKS:
            d = await _digest(db, b["lo"], b["hi"])
            covered += d["sessions"]
            out["blocks"][b["name"]] = {
                "lo": b["lo"].isoformat(),
                "hi": b["hi"].isoformat(),
                "open_ended": b["open_ended"],
                "why": b["why"],
                **d,
            }
        out["partitions_exactly"] = covered == int(total)
        out["covered_sessions"] = covered
    return out


def _compare(old: dict[str, Any], new: dict[str, Any]) -> int:
    """Returns a process exit code: 0 clean, 1 drift in a sealed block."""
    bad = 0
    for name, o in old["blocks"].items():
        n = new["blocks"].get(name)
        if n is None:
            print(f"  {name:<11} ⛔ MISSING from the current database")
            bad += 1
            continue
        if o["open_ended"]:
            grew = n["sessions"] - o["sessions"]
            print(
                f"  {name:<11} open-ended · {o['sessions']} → {n['sessions']} sessions "
                f"({grew:+d}) — expected, not sealed"
            )
            continue
        if n["block_digest"] == o["block_digest"]:
            print(f"  {name:<11} ✅ INTACT · {n['sessions']} sessions · {n['bars']:,} bars")
            continue
        bad += 1
        print(f"  {name:<11} ⛔⛔ DIGEST CHANGED — this block is no longer the sealed one")
        moved = [
            d
            for d, sig in n["session_digests"].items()
            if o["session_digests"].get(d) != sig
        ]
        added = set(n["session_digests"]) - set(o["session_digests"])
        removed = set(o["session_digests"]) - set(n["session_digests"])
        print(
            f"               sessions changed {len(moved)} · added {len(added)} · "
            f"removed {len(removed)}"
        )
        for d in sorted(moved)[:5]:
            print(f"               changed: {d}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="create or refresh the seal file")
    args = ap.parse_args()

    new = asyncio.run(build())

    if args.write and SEAL_PATH.exists():
        old = json.loads(SEAL_PATH.read_text())
        print("A seal already exists — verifying before overwriting:\n")
        if _compare(old, new) > 0:
            raise SystemExit(
                "\n⛔ REFUSING TO OVERWRITE: a sealed block changed. Re-sealing now would "
                "erase the evidence of exactly the event the seal exists to catch. "
                "Investigate the drift, then delete the file by hand if the new state is "
                "genuinely the intended one."
            )
        print()

    if args.write:
        SEAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEAL_PATH.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
        print(f"sealed → {SEAL_PATH}")
        for name, b in new["blocks"].items():
            print(
                f"  {name:<11}{b['lo']} → {b['last_session']}  {b['sessions']:>4} sessions  "
                f"{b['bars']:>10,} bars  {b['block_digest'][:12]}"
                f"{'  (open-ended)' if b['open_ended'] else ''}"
            )
        print(
            f"  partition: {new['covered_sessions']} of {new['archive_sessions_at_seal']} "
            f"{'✅ exact' if new['partitions_exactly'] else '⛔ UNACCOUNTED SESSIONS'}"
        )
        return

    if not SEAL_PATH.exists():
        raise SystemExit(f"no seal at {SEAL_PATH} — run with --write first")
    old = json.loads(SEAL_PATH.read_text())
    print(f"seal written {old['sealed_at']}\n")
    bad = _compare(old, new)
    print()
    raise SystemExit(bad and 1 or 0)


if __name__ == "__main__":
    main()
