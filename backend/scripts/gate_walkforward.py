#!/usr/bin/env python
"""Regime-gate §8 walk-forward (Phase 6). Promotes the gate experiment
(`scripts/gate_experiment.py`) into a §8-grade regression: the win-rate / Sharpe /
max-drawdown metrics §8 gates a merge on, the fixed rule's consistency across time
folds, and an anchored (learn-on-past, apply-forward) out-of-sample test that
defeats the circularity of scoring a corpus-mined rule on that same corpus.

Read-only over the parity-pinned Nifty50 daily backtest at gate-70; NO engine
change. Prints the aggregate §8 table and writes
docs/analysis/gate-walkforward-<date>.md.

Usage:  cd backend && uv run python scripts/gate_walkforward.py [FOLDS]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Runnable from any cwd: put backend/ (the `app` package root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import gate_walkforward as wf  # noqa: E402
from app.services.corpus_attribution import corpus_rows  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gate_walkforward")


async def main(k: int) -> None:
    async with AsyncSessionFactory() as db:
        rows = await corpus_rows(db, min_confidence=70)
    if not rows:
        log.warning("no corpus rows — build the tradecore wheel and backfill Nifty50 daily bars")
        return

    result = wf.run(rows, k)

    # console: the headline §8 table
    b, p = result.baseline, result.proposed
    print(f"corpus: {result.total} trades, {result.folds} folds\n")
    print(f"{'variant':<30}{'trades':>8}{'win%':>7}{'Sharpe':>9}{'maxDD':>8}{'total-R':>9}{'expR':>9}")
    for name, m in (("baseline (all regimes)", b), ("proposed (skip transitional)", p)):
        wr = f"{m.win_rate:.0%}" if m.win_rate is not None else "—"
        sh = f"{m.sharpe:+.3f}" if m.sharpe is not None else "—"
        dd = f"{m.max_dd_r:.1f}" if m.max_dd_r is not None else "—"
        er = f"{m.mean_exp_r:+.3f}" if m.mean_exp_r is not None else "—"
        print(f"{name:<30}{m.trades:>8}{wr:>7}{sh:>9}{dd:>8}{m.total_r:>+9.1f}{er:>9}")
    oos_wins = sum(1 for fc in result.consistency if fc.variant_wins)
    print(f"\nfixed-rule wins expectancy in {oos_wins}/{len(result.consistency)} folds")
    og, ob = result.oos.gated.mean_exp_r, result.oos.baseline.mean_exp_r
    if og is not None and ob is not None:
        print(f"OOS learned-gate expR {og:+.3f} vs baseline {ob:+.3f}")

    day = datetime.now(tz=UTC).date()
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"gate-walkforward-{day}.md"
    out.write_text(wf.render_markdown(result, day=day))
    log.warning("wrote %s", out)


if __name__ == "__main__":
    folds = int(sys.argv[1]) if len(sys.argv) > 1 else wf.DEFAULT_FOLDS
    asyncio.run(main(folds))
