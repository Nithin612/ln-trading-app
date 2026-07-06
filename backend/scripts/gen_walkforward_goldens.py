"""Generate / refresh the walk-forward goldens (§8 drift gate).

DRY-RUN BY DEFAULT — prints what would change and the Δ-table per profile.
`--write` persists goldens under backend/tests/goldens/walkforward/; any
metric move beyond max(5% relative, 0.05 absolute) against the committed
golden REFUSES to write without `--i-have-approval` (SIGNAL_ENGINE.md §8:
spec-affecting changes need explicit user sign-off + regression evidence).

Each golden pins: the profile config + config_hash (drift guard), the
tradecore version, run bounds (since / eval_start / eval_end), capital &
risk, the RESOLVED symbol list (universe drift can never silently move a
golden), per-symbol row counts, the exclusion manifest, per-fold and
aggregate metrics, and a sha256 digest of the canonical trade list.

Usage:
  uv run python scripts/gen_walkforward_goldens.py                # dry-run, all active
  uv run python scripts/gen_walkforward_goldens.py --profile dc1  # dry-run, one profile
  uv run python scripts/gen_walkforward_goldens.py --write        # persist (tolerance-gated)
  uv run python scripts/gen_walkforward_goldens.py --write --i-have-approval
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

# Runnable from any cwd: backend/ (the `app` package root) onto sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest.walkforward import (  # noqa: E402
    WalkForwardSpec,
    build_golden,
    compare_against_existing,
    run_walkforward,
)
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.profile import StrategyProfile  # noqa: E402
from sqlalchemy import select  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "goldens" / "walkforward"

# Pinned run bounds. eval_start deviates from the handoff's suggested
# 2024-07-01: the dev corpus starts 2023-07-03, and 2024-07-01 has only
# ~245 prior sessions — the 300-bar window canon demands ≥300 completed
# bars before eval_start (2024-10-01 has ~309). 7 quarterly folds.
DEFAULT_SINCE = date(2023, 7, 3)
DEFAULT_EVAL_START = date(2024, 10, 1)
DEFAULT_EVAL_END = date(2026, 6, 30)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="persist goldens (default: dry-run)")
    ap.add_argument(
        "--i-have-approval",
        action="store_true",
        help="override the §8 refusal on >5%% metric moves (requires user sign-off)",
    )
    ap.add_argument("--profile", action="append", help="limit to profile key (repeatable)")
    ap.add_argument("--since", type=date.fromisoformat, default=DEFAULT_SINCE)
    ap.add_argument("--eval-start", type=date.fromisoformat, default=DEFAULT_EVAL_START)
    ap.add_argument("--eval-end", type=date.fromisoformat, default=DEFAULT_EVAL_END)
    ap.add_argument("--capital", default="500000")
    ap.add_argument("--risk-pct", default="2")
    args = ap.parse_args()

    spec = WalkForwardSpec(
        since=args.since,
        eval_start=args.eval_start,
        eval_end=args.eval_end,
        capital=Decimal(args.capital),
        risk_pct=Decimal(args.risk_pct),
    )

    async with AsyncSessionFactory() as db:
        q = select(StrategyProfile).where(StrategyProfile.status == "active")
        if args.profile:
            q = q.where(StrategyProfile.key.in_(args.profile))
        profiles = sorted((await db.execute(q)).scalars().all(), key=lambda p: p.key)
        if not profiles:
            print("no ACTIVE profiles matched — nothing to do")
            return 1

        refused: list[str] = []
        written: list[str] = []
        for profile in profiles:
            t0 = time.perf_counter()
            report = await run_walkforward(db, profile, spec)
            wall = time.perf_counter() - t0
            golden = build_golden(profile, spec, report)
            path = GOLDEN_DIR / f"{profile.key}.json"

            agg = report.aggregate
            print(
                f"\n── {profile.key} v{profile.version} "
                f"[{report.tp_rule[0]} {report.tp_rule[1]}"
                f"{' ≈approx' if report.tp_approximated else ''}] — {wall:.1f}s"
            )
            print(
                f"  universe {len(report.symbols)} ran / {len(report.exclusions)} excluded · "
                f"trades {agg.total_trades} (pre-gate {report.pre_filter_trade_count}) · "
                f"win {agg.win_rate_pct:.1f}% · totPnL {agg.total_pnl_pct:+.1f}% · "
                f"sharpe {agg.sharpe:+.2f} · maxDD {agg.max_drawdown_pct:.1f}%"
            )

            if path.exists():
                old = json.loads(path.read_text())
                changed, needs_approval, table = compare_against_existing(old, golden)
                print(table)
                if not changed:
                    continue
                if needs_approval and not args.i_have_approval:
                    refused.append(profile.key)
                    print(
                        "  ✗ REFUSED: metric move beyond max(5%, 0.05) — "
                        "rerun with --i-have-approval after user sign-off (§8)"
                    )
                    continue
            else:
                print("  NEW golden (no committed baseline)")

            if args.write:
                GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
                written.append(profile.key)
                shown = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
                print(f"  ✓ wrote {shown}")
            else:
                print("  (dry-run — pass --write to persist)")

        print(f"\nwritten: {written or '—'}   refused: {refused or '—'}")
        return 2 if refused else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
