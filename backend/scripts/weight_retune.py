#!/usr/bin/env python
"""Weight-retune experiment (Phase 6 slice 6.4). Coordinate sweep over the six
confluence weight-groups (each ×0.5 / ×1.5) on the parity-clean Nifty50 daily
corpus, scored on the §8 metrics + per-fold consistency. Read-only; group
multipliers apply inside the frozen scorer (engine untouched); nothing is promoted.

Writes docs/analysis/weight-retune-<date>.md.

Usage:  cd backend && uv run python scripts/weight_retune.py [FOLDS]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import weight_retune as wr  # noqa: E402
from app.services.corpus_attribution import corpus_rows  # noqa: E402
from app.services.gate_walkforward import DEFAULT_FOLDS, gate_metrics  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("weight_retune")


async def main(k: int) -> None:
    configs = wr.sweep_configs()
    async with AsyncSessionFactory() as db:
        # Baseline first — its trading days define the shared fold boundaries.
        base_rows = await corpus_rows(db, min_confidence=70)
        if not base_rows:
            log.warning("no corpus rows — build tradecore + backfill Nifty50 daily bars")
            return
        cuts = wr.fold_bounds(base_rows, k)
        base_fold_exp = [gate_metrics(f).mean_exp_r for f in wr.bucket_by_bounds(base_rows, cuts)]
        baseline = wr.evaluate("baseline", {}, base_rows, cuts, base_fold_exp)

        results: list[wr.ConfigResult] = []
        for label, mult in configs:
            if not mult:
                continue  # baseline already done
            rows = await corpus_rows(db, min_confidence=70, weight_multipliers=mult)
            results.append(wr.evaluate(label, mult, rows, cuts, base_fold_exp))

    # Rank by total-R then expectancy (descending).
    results.sort(key=lambda c: (c.metrics.total_r, c.metrics.mean_exp_r or -1e9), reverse=True)
    report = wr.RetuneReport(folds=len(cuts) + 1, baseline=baseline, configs=results)

    print(f"corpus: {baseline.metrics.trades} baseline trades, {report.folds} folds\n")
    print(f"{'config':<22}{'trades':>8}{'expR':>9}{'total-R':>9}{'folds+':>8}")
    b = baseline.metrics
    print(f"{'baseline':<22}{b.trades:>8}{(b.mean_exp_r or 0):>+9.3f}{b.total_r:>+9.1f}{'—':>8}")
    for c in results:
        m = c.metrics
        er = f"{m.mean_exp_r:+.3f}" if m.mean_exp_r is not None else "—"
        print(f"{c.label:<22}{m.trades:>8}{er:>9}{m.total_r:>+9.1f}"
              f"{f'{c.folds_beating_baseline}/{c.folds_compared}':>8}")

    day = datetime.now(tz=UTC).date()
    out = Path(__file__).resolve().parents[2] / "docs" / "analysis" / f"weight-retune-{day}.md"
    out.write_text(wr.render_markdown(report, day=day))
    log.warning("wrote %s", out)


if __name__ == "__main__":
    folds = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FOLDS
    asyncio.run(main(folds))
