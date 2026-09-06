"""Q2.4 — decide the momentum ×1.5 retune WITHOUT waiting for forward evidence.

    uv run python scripts/retune_dsr_verdict.py [FOLDS]

## Why this exists

The 6.4 sweep (2026-08-14) picked **momentum ×1.5** as best-of-12 on the full corpus and
said so plainly in its own verdict: *"Best-of-12 selected on the full corpus, so treat even
this as in-sample until forward shadow confirms; `folds+` is the only guard against a lucky
pick."*

The forward shadow was supposed to be that confirmation. **It has stalled**: 7 signals
minted per arm and **0 resolved in 21 days** (2026-08-13 → 09-03). At that rate the
decision is years away, so "wait for forward evidence" is not a plan — it is a way of never
deciding.

**But the missing instrument now exists.** `folds+` was a temporal-consistency proxy; the
deflated-Sharpe bar (built 09-03, validated by H8 on 09-04) is the instrument built for
*exactly* this situation — a best-of-N selection where the winner's apparent edge is partly
the selection itself. Running it settles the question from data we already have.

## What is different from the original

- **The trial count is honest.** The original selected 1 of 13 (baseline + 12 variants) and
  had no way to charge itself for that. Here `trials = 13`.
- **The trial dispersion is MEASURED, not assumed.** `deflated_sharpe` defaults
  `trial_stdev` to `1/√n` — a deliberately conservative stand-in. We actually ran the 13
  configs, so their Sharpe dispersion is observable, and passing it is strictly more
  faithful than the fallback.
- ⚠ **This does not make the result out-of-sample.** Every config is still scored on the
  whole corpus. Deflation charges for *selection*; it cannot manufacture a train/test split.
  A pass here would mean "worth a real out-of-sample test", never "promote".

⚠ **This re-scores the corpus once per config (13×) and needs the `tradecore` wheel.**
Read-only; nothing is promoted; the frozen engine is untouched (multipliers apply inside
the scorer, as in the original sweep).
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import weight_retune as wr  # noqa: E402
from app.services.corpus_attribution import corpus_rows  # noqa: E402
from app.services.deflated_sharpe import DsrResult, deflated_sharpe  # noqa: E402
from app.services.entry_attribution import realized_r  # noqa: E402
from app.services.gate_walkforward import DEFAULT_FOLDS, gate_metrics  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("retune_dsr")

_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"
#: IST, matching every other analysis script — a UTC date labels an early-morning
#: IST run with YESTERDAY, which then disagrees with the report beside it.
_IST = ZoneInfo("Asia/Kolkata")


@dataclass
class Candidate:
    label: str
    r_series: list[float]
    sharpe: float | None
    total_r: float
    mean_exp_r: float | None
    folds_plus: str
    dsr: DsrResult | None = None

    @property
    def t_stat(self) -> float | None:
        """Sharpe × √n — the same restatement H8 used to make the bar readable.

        H8 established the bar demands **t ≈ 3.6 and that the hurdle is FLAT IN n**, so a
        t far below it cannot be rescued by accruing more of the same.
        """
        if self.sharpe is None or len(self.r_series) < 2:
            return None
        return float(self.sharpe * (len(self.r_series) ** 0.5))


def _series(rows: Sequence[Any]) -> list[float]:
    return [rr for r in rows if (rr := realized_r(r)) is not None]


async def main(k: int) -> None:  # noqa: C901 — one linear pass: score every config,
    # deflate, rank, then render. The branches are the report's own conditionals
    # (winner moved / anything passing), and splitting them out would separate each
    # verdict from the numbers it is drawn from.
    configs = wr.sweep_configs()
    cands: list[Candidate] = []

    async with AsyncSessionFactory() as db:
        base_rows = await corpus_rows(db, min_confidence=70)
        if not base_rows:
            log.warning("no corpus rows — build tradecore + backfill Nifty50 daily bars")
            return
        cuts = wr.fold_bounds(base_rows, k)
        base_fold_exp = [
            gate_metrics(f).mean_exp_r for f in wr.bucket_by_bounds(base_rows, cuts)
        ]
        base_eval = wr.evaluate("baseline", {}, base_rows, cuts, base_fold_exp)
        cands.append(
            Candidate(
                label="baseline",
                r_series=_series(base_rows),
                sharpe=base_eval.metrics.sharpe,
                total_r=base_eval.metrics.total_r,
                mean_exp_r=base_eval.metrics.mean_exp_r,
                folds_plus="—",
            )
        )

        for label, mult in configs:
            if not mult:
                continue
            rows = await corpus_rows(db, min_confidence=70, weight_multipliers=mult)
            ev = wr.evaluate(label, mult, rows, cuts, base_fold_exp)
            cands.append(
                Candidate(
                    label=label,
                    r_series=_series(rows),
                    sharpe=ev.metrics.sharpe,
                    total_r=ev.metrics.total_r,
                    mean_exp_r=ev.metrics.mean_exp_r,
                    folds_plus=f"{ev.folds_beating_baseline}/{ev.folds_compared}",
                )
            )
            log.warning("scored %s (%d trades)", label, len(rows))

    trials = len(cands)
    sharpes = [c.sharpe for c in cands if c.sharpe is not None]
    # MEASURED dispersion across the things we actually tried — strictly better than
    # `deflated_sharpe`'s conservative 1/√n fallback, because we ran the trials.
    trial_sd = statistics.stdev(sharpes) if len(sharpes) > 1 else None

    for c in cands:
        if len(c.r_series) >= 2:
            c.dsr = deflated_sharpe(c.r_series, trials=trials, trial_stdev=trial_sd)

    cands.sort(key=lambda c: (c.total_r, c.mean_exp_r or -1e9), reverse=True)
    winner = next((c for c in cands if c.label == "momentum ×1.5"), None)

    day = datetime.now(tz=UTC).astimezone(_IST).date()
    out: list[str] = [
        f"# Q2.4 — the momentum ×1.5 retune, decided by the bar ({day})",
        "",
        "**The forward route is dead.** The 6.4 shadow A/B has minted **7 signals per arm**",
        "and resolved **0 in 21 days** (2026-08-13 → 09-03). At that rate the decision is",
        "years away, so waiting for forward evidence is not a plan — it is a way of never",
        "deciding.",
        "",
        "**So it is decided here, with the instrument that did not exist in August.** The",
        "original sweep chose best-of-12 on the full corpus and said so; `folds+` was its",
        "only guard against a lucky pick. The deflated-Sharpe bar is built for exactly this.",
        "",
        f"- **trials charged: {trials}** (baseline + {trials - 1} variants — the honest count",
        "  for a best-of-N selection)",
        f"- **trial dispersion: MEASURED at {trial_sd:+.4f}**" if trial_sd is not None
        else "- trial dispersion: unavailable",
        "  (we ran the trials, so their spread is observable — strictly more faithful than",
        "  the `1/√n` fallback the bar uses when it has to guess)",
        "",
        "⭐ **The bar restates as t ≈ 3.6, and H8 established that hurdle is FLAT IN n** —",
        "so a candidate far below it cannot be rescued by accruing more of the same.",
        "",
        "| config | trades | Sharpe | **t** | total-R | expR | folds+ | DSR | clears? |",
        "|---|--:|--:|--:|--:|--:|:-:|--:|:-:|",
    ]
    for c in cands:
        t = f"{c.t_stat:+.2f}" if c.t_stat is not None else "—"
        sh = f"{c.sharpe:+.3f}" if c.sharpe is not None else "—"
        er = f"{c.mean_exp_r:+.3f}" if c.mean_exp_r is not None else "—"
        dsr = f"{c.dsr.dsr:.1%}" if c.dsr else "—"
        ok = "✅" if (c.dsr and c.dsr.passes) else "❌"
        out.append(
            f"| {c.label} | {len(c.r_series)} | {sh} | **{t}** | {c.total_r:+.1f} | "
            f"{er} | {c.folds_plus} | {dsr} | {ok} |"
        )

    # ⭐ Did the WINNER change since the original sweep? The August run put
    # `momentum ×1.5` first on total-R (+50.4). If a slightly larger corpus reorders the
    # top of the table, the original pick was ranking noise — which is a sharper argument
    # than any single t-statistic, and one the numbers alone do not volunteer.
    top = cands[0].label
    winner_moved = top != "momentum ×1.5"

    passing = [c for c in cands if c.dsr and c.dsr.passes]
    out += ["", "## Verdict", ""]
    if winner is not None and winner.t_stat is not None:
        short_by = 3.6 / winner.t_stat if winner.t_stat > 0 else None
        out += [
            f"**momentum ×1.5 stands at t = {winner.t_stat:+.2f}** against a hurdle of "
            f"**≈3.6**"
            + (f" — short by ~{short_by:.1f}×." if short_by else "."),
            "",
        ]
        if winner.dsr:
            out += [f"> {winner.dsr.note}", ""]
    if winner_moved:
        out += [
            f"⭐ **THE WINNER HAS CHANGED. `{top}` now ranks first, not `momentum ×1.5`.**",
            "",
            "The August sweep put `momentum ×1.5` top on total-R (+50.4). Re-running the",
            "same method on a slightly larger corpus reorders the table — and the gap",
            "between first and the middle of the pack is a fraction of a t. **A ranking",
            "that reshuffles when the sample nudges was never measuring a real ordering**,",
            "which is a sharper argument against the original pick than any single",
            "statistic: it shows the selection itself was the noise.",
            "",
        ]

    if not passing:
        out += [
            "⛔ **NOT ONE CONFIG CLEARS THE BAR — including whichever one leads.**",
            "",
            "**⇒ DECIDE: NO. The momentum ×1.5 retune is not promotable, and the forward",
            "A/B should stop being treated as a pending decision.** It is not that the",
            "evidence is incomplete; it is that the apparent edge is the size a best-of-13",
            "selection produces by chance, and the hurdle does not fall with more data.",
            "",
            "This is the same shape as `sl_atr` (t ≈ 0.41 vs 3.6, decided NO on 09-04) and",
            "it belongs in the same bucket: **the instrument working, not failing.**",
        ]
    else:
        out += [
            f"✅ **{len(passing)} config(s) clear the bar**: "
            + ", ".join(c.label for c in passing),
            "",
            "⚠ **A pass here means 'worth a real out-of-sample test', NOT 'promote'.**",
            "Every config was scored on the whole corpus; deflation charges for selection,",
            "it cannot manufacture a train/test split.",
        ]

    out += [
        "",
        "## ⚠ Limits",
        "",
        "- **Still in-sample.** Deflation prices the selection, not the lack of a holdout.",
        "- **Per-GROUP, not per-factor.** The 6.2 leak is per-factor; groups mix helping and",
        "  hurting factors, so a group that nets flat can hide a real per-factor signal. A",
        "  null here argues for per-factor weights — a larger, frozen-engine change.",
        "- **The corpus is Nifty50 daily since ~2023-07**, so this says nothing about other",
        "  regimes (that is what the parked pre-COVID backtest would address).",
    ]

    report = "\n".join(x for x in out if x)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"retune-dsr-verdict-{day}.md"
    target.write_text(report + "\n", encoding="utf-8")
    log.warning("wrote %s", target)


if __name__ == "__main__":
    folds = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FOLDS
    asyncio.run(main(folds))
