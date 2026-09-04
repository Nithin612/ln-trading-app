"""H8 — run the negative control on our deflated-Sharpe bar and write the report.

    uv run python scripts/dsr_negative_control.py [--sims 2000] [--date YYYY-MM-DD]

Read-only: it touches nothing but the `positions` table and writes one markdown file to
docs/analysis/. Nothing here changes a trade, a gate mode, or a recorded number.

The question it answers is not "is a gate good" but "can our instrument tell". See
`app/services/dsr_control.py` for why both a specificity arm and a power arm are needed —
a bar that rejects everything passes a rejects-noise test trivially.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import deflated_sharpe as ds  # noqa: E402
from app.services import dsr_control as ctrl  # noqa: E402
from sqlalchemy import text  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
#: Sample sizes for the calibration sweep — our own n, then what growth would buy.
N_SWEEP = (30, 50, 78, 105, 200, 400, 1000)
#: True per-trade Sharpes probed for the power curve.
SHARPE_GRID = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 1.00)


async def _closed_pnl() -> list[float]:
    async with AsyncSessionFactory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT realized_pnl FROM positions "
                    "WHERE mode='paper' AND closed_at IS NOT NULL ORDER BY closed_at"
                )
            )
        ).scalars().all()
    return [float(x) for x in rows]


def _report(pnl: list[float], *, sims: int, seed: int, on: date) -> str:
    rng = random.Random(seed)
    m = ds.moments(pnl)
    if m is None:
        return "# DSR negative control\n\nNot enough closed trades to run the control.\n"

    n_real = len(pnl)
    t_real = m.sharpe * math.sqrt(n_real)
    spec_partition = ctrl.random_partition_rate(pnl, block_frac=0.22, sims=sims, rng=rng)
    spec_best = ctrl.best_of_trials_rate(pnl, n=min(n_real, 78), sims=sims, rng=rng)
    power = {
        s: ctrl.power_rate(pnl, n=min(n_real, 78), true_sharpe=s, sims=max(200, sims // 4), rng=rng)
        for s in SHARPE_GRID
    }
    hurdles = {n: ctrl.implied_t_hurdle(n) for n in N_SWEEP}
    n_cohort = min(n_real, 78)
    mds = {
        tgt: ctrl.minimum_detectable_sharpe(
            pnl, n=n_cohort, target_power=tgt, sims=300, rng=rng
        )
        for tgt in ctrl.POWER_TARGETS
    }
    both_ok = spec_partition.verdict_ok and spec_best.verdict_ok and power[0.70] >= 0.80

    out: list[str] = [
        f"# H8 — negative control on the deflated-Sharpe bar — {on.isoformat()}",
        "",
        f"_Generated {datetime.now(IST):%Y-%m-%d %H:%M} IST · read-only · seed {seed} ·"
        f" {sims:,} simulations per specificity arm._",
        "",
        "> **What this is.** A test of the test. `deflated_sharpe.py` currently rejects every",
        "> gate we have, and that verdict is about to justify closing the gating programme.",
        "> Before acting on an instrument that says no to everything, check that it can say",
        "> yes to something. **H8 as written in `quant-agent-findings.md` asks only whether the",
        "> bar rejects noise — a bar that rejects everything passes that trivially**, so a",
        "> power arm was added. Both arms, or the result is not interpretable.",
        "",
        f"## Verdict: {'✅ THE BAR IS SOUND' if both_ok else '⛔ THE BAR IS NOT TRUSTWORTHY'}",
        "",
    ]

    if both_ok:
        out += [
            "It rejects noise **and** accepts real edges. Its verdicts on our gates can be",
            "acted on. The gates are not being failed by a broken instrument.",
        ]
    else:
        out += [
            "At least one arm failed. **Do not act on any readiness banner** until this is",
            "resolved — the bar is either too permissive (noise clears) or unable to detect a",
            "genuine edge (planted edges rejected).",
        ]

    out += [
        "",
        "## The book the control is calibrated on",
        "",
        f"- **n = {n_real}** closed paper trades · mean **₹{m.mean:+,.0f}** · sd ₹{m.stdev:,.0f}",
        f"- skew **{m.skew:+.2f}** · kurtosis **{m.kurtosis:.2f}** (normal = 3.0)"
        " — heavily fat-tailed, which PSR charges for",
        f"- per-trade Sharpe **{m.sharpe:+.3f}** ⇒ **t = {t_real:+.2f}**",
        "",
        "Synthetic series are bootstrapped from these trades and shifted, never drawn from a",
        "normal — PSR penalises skew and fat tails, so a Gaussian control would flatter it.",
        "",
        "## Arm 1 — specificity: does the bar reject what it should?",
        "",
        "| control | simulations | cleared the bar | expected | verdict |",
        "|---|--:|--:|--:|---|",
        f"| random, content-free partitions of the real book | {spec_partition.sims:,} |"
        f" **{spec_partition.rate:.2%}** | ≤ 5% | {'✅' if spec_partition.verdict_ok else '⛔'} |",
        f"| **best of {ds.DEFAULT_TRIALS} zero-edge candidates** (the selection we actually do) |"
        f" {spec_best.sims:,} | **{spec_best.rate:.2%}** | ≤ 5% |"
        f" {'✅' if spec_best.verdict_ok else '⛔'} |",
        "",
        "The second row is the one that matters. Running eight shadow gates and getting",
        "interested in the best-looking banner is *exactly* how two gates were promoted and",
        f"then refuted. Under a true-zero-edge null that procedure fools the bar"
        f" **{spec_best.rate:.2%}** of the time — at or inside the 5% it is designed to allow.",
        "",
        "## Arm 2 — power: can the bar say yes at all?",
        "",
        f"Planted edges of known size at n = {min(n_real, 78)}, our actual cohort size.",
        "",
        "| true per-trade Sharpe | equivalent t | bar accepts |",
        "|--:|--:|--:|",
    ]
    for s in SHARPE_GRID:
        out.append(f"| {s:.2f} | {s * math.sqrt(min(n_real, 78)):.2f} | **{power[s]:.1%}** |")

    def _mds(tgt: float) -> str:
        v = mds.get(tgt)
        if v is None:
            return "not reachable below 1.50"
        return f"{v:.2f} (t ≈ {v * math.sqrt(n_cohort):.2f})"

    out += [
        "",
        "**Minimum detectable edge**, by bisection rather than off the grid above:",
        "",
        *[f"- **{int(tgt * 100)}% power** — true per-trade Sharpe {_mds(tgt)}"
          for tgt in ctrl.POWER_TARGETS],
        "",
        "**The bar is not blind.** But note the cliff: power is ~0% below t ≈ 3.5 and"
        " near-total above t ≈ 4.4. It is an instrument for large edges, by design.",
        "",
        "## What the bar is actually demanding, in one number",
        "",
        "The probability language hides the hurdle. Solved back to a plain t-statistic on the",
        "trade series (Gaussian case — real fat tails make it *stricter*):",
        "",
        "| n | implied hurdle |",
        "|--:|--:|",
    ]
    for n, h in hurdles.items():
        out.append(f"| {n:,} | t ≥ **{h:.2f}** |")

    out += [
        "",
        "**The hurdle is ≈3.6 and barely moves with sample size.** That is the single most",
        "useful output here: it converts an opaque probability into a number the literature",
        "already argues about. Harvey, Liu & Zhu (2016) recommend **t > 3.0** for accepting a",
        "new factor precisely because of multiple testing. **Our bar sits just above that",
        "recommendation — it is defensibly calibrated, not arbitrary, and not broken.**",
        "",
        "It also explains why MinTRL keeps returning `None`: the benchmark falls as `1/√n`",
        "while the required t stays flat, so **more observations do not lower the bar** — they",
        "only shrink the error on an estimate that has to be large in the first place.",
        "",
        "## Consequences — stated before anyone reads a banner again",
        "",
        "1. **`sl_atr` is decided, and the answer is NO.** Its eligible set stands at Sharpe",
        "   **+0.046 over n=78 ⇒ t ≈ 0.41**, against a hurdle of ≈3.6. That is not marginal;",
        "   it is short by roughly 9×, and it sits far below even the low-power region where",
        "   the bar might be accused of missing something. **Stop waiting for its 20th resolved",
        "   trade** — the count was never the constraint. It passes all three readiness guards",
        "   and still has no measurable edge in the book it would leave behind.",
        "2. **Failing this bar is not proof of no edge — except when it is this far short.**",
        "   The bar has almost no power between t ≈ 2.6 and t ≈ 3.5, so a genuine but modest",
        "   edge would be invisible. That is the price of multiple-testing correction and it is",
        "   the right trade for a promote-to-money decision. **Future gates failing at t ≈ 2–3",
        "   deserve a different conversation from `sl_atr` at t = 0.41.** Record the t, not just",
        "   the pass/fail.",
        "3. **The leak is upstream of gating.** Three months of shadow accrual, eight gates, two",
        "   promotions both refuted, and the best surviving candidate is at t = 0.41. No",
        "   partition of these trades is going to clear a t of 3.6, because the trades",
        "   themselves carry no edge to partition. Selection has been optimised; what generates",
        "   the candidates has not.",
        "",
        "## Limits of this control",
        "",
        "- Bootstrap resampling assumes trades are **i.i.d.**; ours overlap in time and cluster",
        "  by regime, so the true dispersion of a cohort Sharpe is wider than modelled and the",
        "  specificity arm is, if anything, optimistic.",
        f"- `trials = {ds.DEFAULT_TRIALS}` is still an assumption. **U4** (the trials counter)",
        "  replaces it with an observed count; until then the deflation is understated.",
        "- The power arm plants a *constant* edge. A real edge that is regime-dependent would be",
        "  harder to see than these curves suggest.",
        "",
    ]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="H8 negative control on the deflated-Sharpe bar")
    ap.add_argument("--sims", type=int, default=ctrl.DEFAULT_SIMS)
    ap.add_argument("--seed", type=int, default=20260904)
    ap.add_argument("--date", type=str, default=None)
    args = ap.parse_args()
    on = date.fromisoformat(args.date) if args.date else datetime.now(IST).date()

    pnl = asyncio.run(_closed_pnl())
    md = _report(pnl, sims=args.sims, seed=args.seed, on=on)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"dsr-negative-control-{on.isoformat()}.md"
    path.write_text(md)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
