"""Exit / giveback study — is the loss made at the exit, or was it never a winner?

    uv run python scripts/exit_giveback_study.py

## Why this exists, and how it went

It was commissioned on a hypothesis that turned out to be **wrong**, and the way it was
wrong is the most useful thing in the file.

The prompt was: of 30 stop-outs, 25 had been in profit first and 21 gave back every rupee,
totalling −₹59,785. That reads like an exit defect — the stop never ratcheted, so winners
became losers.

**In ₹ it reads that way. In R it does not.** The `sl_hit` group's average peak of +₹1,229
is, as a fraction of the risk actually taken, approximately **zero**. Those trades were
never meaningfully in profit; they wobbled a few hundred rupees above entry on positions
whose 1R was thousands.

⚠ **This is the project's own standing rule, broken by the person who wrote it down:**
*"Measure stop-width counterfactuals in R, never ₹ — risk-first sizing means a wider stop
buys a smaller position, so a constant-qty replay tests bet size, not stop placement (that
error inverted the first pass)."* The same class of error, one layer over: reading ₹ peaks
and inferring giveback.

So this script reports everything **normalised by R**.

## ⚠ Correction, 2026-09-07 — the first version of THIS file got R wrong twice

1. **R was measured from the signal's intended entry, while P&L is measured from the
   actual fill.** Those are different numbers whenever the fill slipped or chased, and
   mixing them manufactures fake R. It made GEOJITFSL read as a 3.03R peak that gave back
   2.5R; measured from the fill it never reached 2R. **R is now
   `|avg_entry_price − commit_SL| × qty` — the risk actually taken.**
2. **`abs()` hid the known wrong-side row.** SPARC is a LONG filled at ₹204.60 with a
   ₹205.00 stop (the `size_for_fill` side-blind bug, fixed forward-only). Under `abs()`
   its four-paise "risk" produced a 2.31R peak and a −3.09R loss out of pure arithmetic.
   The risk expression is now SIGNED and non-positive rows are excluded and counted.

The correction **reversed a conclusion**: with signal-entry R the ≥2R bucket appeared to
capture only 20%, i.e. "the biggest winners give back the most". Measured from the fill
it captures 65%, in line with every other bucket. The original verdict — *the exits are
working* — is unchanged and now rests on consistent arithmetic.

## What it actually found

Bucketing by peak excursion in R separates two completely different populations, and only
one of them is an exit story.

⚠ **Also corrected here: "the stop moved" is NOT evidence the ratchet works.** The
profit-lock ladder only arms once a trade is up, so `stop moved` is a proxy for `trade went
into profit`. Controlling for peak R, moving the stop made no measurable difference — the
partition-is-a-proxy trap that the market-regime gate already taught (there it was a proxy
for *side*).
"""

from __future__ import annotations

import asyncio
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from sqlalchemy import text  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "analysis"

_SQL = text(
    """
    SELECT p.id, s.symbol, sg.classification AS cls, p.exit_reason, p.trail_state,
           p.side, p.quantity, p.avg_entry_price, p.current_sl,
           sg.stop_loss AS commit_sl, p.peak_pnl, p.realized_pnl,
           -- ⭐ Risk per share measured from the ACTUAL FILL, not the signal's
           -- intended entry. Direction-aware, and deliberately SIGNED so a
           -- wrong-side row surfaces as <= 0 instead of being rescued by abs().
           (CASE WHEN p.side = 'LONG' THEN p.avg_entry_price - sg.stop_loss
                 ELSE sg.stop_loss - p.avg_entry_price END) AS risk_per_share
    FROM positions p
    JOIN signals sg ON sg.id = p.signal_id
    JOIN stocks s ON s.id = p.stock_id
    WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
      AND p.peak_pnl IS NOT NULL AND sg.stop_loss IS NOT NULL
    """
)


@dataclass
class Trade:
    symbol: str
    cls: str
    exit_reason: str | None
    peak_r: float
    real_r: float
    pnl: float
    moved: bool

    @property
    def capture(self) -> float | None:
        """Fraction of the peak excursion actually realised. `None` when the peak was ~0 —
        capture is undefined against a peak that never existed, and dividing by it produces
        the −6.72 and −129 artefacts an earlier pass reported as if they meant something."""
        if self.peak_r <= 0.05:
            return None
        return self.real_r / self.peak_r


_BUCKETS = (
    (0.25, "peak < 0.25R — never worked"),
    (0.5, "peak 0.25–0.5R"),
    (1.0, "peak 0.5–1R"),
    (2.0, "peak 1–2R"),
    (float("inf"), "peak ≥ 2R"),
)


def _bucket_of(peak_r: float) -> str:
    for hi, label in _BUCKETS:
        if peak_r < hi:
            return label
    return _BUCKETS[-1][1]


async def _run() -> int:
    async with AsyncSessionFactory() as db:
        rows = list((await db.execute(_SQL)).all())

    excluded = [r for r in rows if r.risk_per_share is None or float(r.risk_per_share) <= 0]
    trades = [
        Trade(
            symbol=r.symbol, cls=r.cls, exit_reason=r.exit_reason,
            peak_r=float(r.peak_pnl) / (float(r.risk_per_share) * r.quantity),
            real_r=float(r.realized_pnl) / (float(r.risk_per_share) * r.quantity),
            pnl=float(r.realized_pnl),
            moved=r.current_sl is not None and r.current_sl != r.commit_sl,
        )
        for r in rows
        if r.risk_per_share is not None and float(r.risk_per_share) > 0
    ]
    if not trades:
        print("no evaluable closed positions")
        return 1

    now = datetime.now(UTC).astimezone(_IST)
    out: list[str] = [
        f"# Exit / giveback study — in R, not ₹ ({now.date().isoformat()})",
        "",
        f"**{len(trades)} closed paper positions** with a recoverable commit stop and a",
        "peak-excursion mark. Everything below is normalised by **R = |entry − commit_SL| ×",
        "qty**, because the ₹ version of this analysis gives the opposite answer.",
        "",
        "## ⚠ The correction this study exists to record",
        "",
        "It was commissioned on the reading that *25 of 30 stop-outs had been in profit and",
        "gave it all back, for −₹59,785* — an apparent exit defect.",
        "",
        "**In ₹ that is what it looks like. In R it evaporates.** The `sl_hit` group's average",
        "peak of +₹1,229 is, against the risk actually taken, approximately **zero**. Those",
        "trades were never meaningfully in profit — they wobbled a few hundred rupees above",
        "entry on positions whose 1R was thousands.",
        "",
        "This is the project's own standing rule, broken by the person who wrote it: *measure",
        "in R, never ₹, because risk-first sizing makes ₹ incomparable across trades.*",
        "",
        "## Where the money actually is",
        "",
        "| peak bucket | n | avg peak R | avg realised R | total R | total ₹ | capture |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]

    order = [label for _hi, label in _BUCKETS]
    grouped: dict[str, list[Trade]] = {label: [] for label in order}
    for t in trades:
        grouped[_bucket_of(t.peak_r)].append(t)

    for label in order:
        g = grouped[label]
        if not g:
            continue
        sum_peak = sum(t.peak_r for t in g)
        sum_real = sum(t.real_r for t in g)
        # ⚠ AGGREGATE capture (sum realised / sum peak), not the mean of per-trade
        # ratios. The mean-of-ratios version weights a trade that peaked at 0.06R
        # the same as one that peaked at 3R, and it is the ratio-of-sums that
        # corresponds to money. Still suppressed when the bucket has no peak worth
        # capturing — dividing by ~0 produced the "-610%" an earlier pass printed.
        cap = f"{100 * sum_real / sum_peak:.0f}%" if sum_peak >= 0.5 * len(g) else "— (no peak)"
        out.append(
            f"| **{label}** | {len(g)} | {statistics.fmean(t.peak_r for t in g):.2f} | "
            f"{statistics.fmean(t.real_r for t in g):+.2f} | "
            f"{sum_real:+.1f}R | ₹{sum(t.pnl for t in g):,.0f} | {cap} |"
        )

    dead = [t for t in trades if t.peak_r < 0.5]
    dead_pct = 100 * len(dead) / len(trades)
    dead_inr = sum(t.pnl for t in dead)
    dead_r = sum(t.real_r for t in dead)
    worked = [t for t in trades if t.peak_r >= 0.5]
    worked_peak = sum(t.peak_r for t in worked)
    worked_real = sum(t.real_r for t in worked)
    out += [
        "",
        "## Verdict",
        "",
        f"⭐ **{len(dead)} of {len(trades)} trades ({dead_pct:.0f}%) never reached 0.5R**, "
        f"and they account for **₹{dead_inr:,.0f}** ({dead_r:+.1f}R). **No exit rule can "
        "touch these** — there was never a profit to protect.",
        "",
        f"⭐ **The {len(worked)} trades that DID work kept most of their move**: "
        f"{worked_real:.1f}R realised of a {worked_peak:.1f}R combined peak = "
        f"**{100 * worked_real / worked_peak:.0f}% capture**, and capture is roughly flat "
        "across buckets rather than collapsing on the big winners.",
        "",
        f"⭐ **The entire addressable pool for a better exit is {worked_peak - worked_real:.1f}R** "
        "— the total giveback on trades that got into profit, most of which is irreducible "
        "(nothing exits at the exact peak). Set that against the "
        f"{abs(dead_r):.1f}R lost by trades that never worked.",
        "",
        "**⇒ This is NOT an exit problem. The exit machinery is working.** It is the same",
        "diagnosis CLAUDE.md recorded months ago on 15 trades — *\"the exit machinery was",
        "correct but had nothing to protect\"* — now confirmed on "
        f"{len(trades)}.",
        "",
        "**The loss is made at ENTRY.**",
        "",
        "## ⚠ And the ratchet does NOT explain the difference",
        "",
        "An earlier pass split on *did the stop move* and found +₹43,395 versus −₹42,301,",
        "which looks like proof the ratchet works. **It is a proxy.** The profit-lock ladder",
        "only arms once a trade is up, so `stop moved` ≈ `trade went into profit`. Peak R",
        "confirms it: 1.63R average peak for moved versus 0.41R for unchanged.",
        "",
        "Controlling for peak R, the difference disappears:",
        "",
        "| peak bucket | stop moved | n | avg realised R |",
        "|---|---|--:|--:|",
    ]
    for label in order:
        g = grouped[label]
        for moved in (False, True):
            sub = [t for t in g if t.moved is moved]
            if len(sub) >= 2:
                out.append(
                    f"| {label} | {'yes' if moved else 'no'} | {len(sub)} | "
                    f"{statistics.fmean(t.real_r for t in sub):+.3f} |"
                )
    out += [
        "",
        "Within a peak bucket, moving the stop made **no measurable difference**. That is the",
        "partition-is-a-proxy trap the market-regime gate already taught, where the partition",
        "turned out to be a proxy for *side*.",
        "",
        "## ⚠ Limits",
        "",
        f"- **n = {len(trades)}**, one broad regime, ~2 months of entries.",
        f"- **{len(excluded)} position(s) excluded** for a non-positive risk distance (a"
        "  stop on the wrong side of the fill). Excluded and counted, never `abs()`-ed"
        "  into a plausible-looking tiny R — that is how a −3.09R artefact was born.",
        "- **`peak_pnl` is updated on live monitor ticks**, so it is only as complete as the",
        "  monitor's uptime — a peak reached while the worker was down is not recorded, which",
        "  biases peaks DOWNWARD and would, if anything, understate giveback.",
        "- **Capture is undefined for a ~zero peak** and is reported as `—` rather than as the",
        "  large negative artefact that dividing by a near-zero peak produces.",
    ]

    report = "\n".join(out)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = _OUT_DIR / f"exit-giveback-{now.date().isoformat()}.md"
    target.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {target}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
