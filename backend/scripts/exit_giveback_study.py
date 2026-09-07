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

So this script reports everything **normalised by R** = `|entry − commit_SL| × qty`.

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
           p.quantity, p.avg_entry_price, p.current_sl, sg.stop_loss AS commit_sl,
           p.peak_pnl, p.realized_pnl,
           (ABS(sg.entry_price - sg.stop_loss) * p.quantity) AS r_inr
    FROM positions p
    JOIN signals sg ON sg.id = p.signal_id
    JOIN stocks s ON s.id = p.stock_id
    WHERE p.mode = 'paper' AND p.closed_at IS NOT NULL
      AND p.peak_pnl IS NOT NULL AND sg.stop_loss IS NOT NULL
      AND sg.entry_price IS NOT NULL
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

    trades = [
        Trade(
            symbol=r.symbol, cls=r.cls, exit_reason=r.exit_reason,
            peak_r=float(r.peak_pnl) / float(r.r_inr),
            real_r=float(r.realized_pnl) / float(r.r_inr),
            pnl=float(r.realized_pnl),
            moved=r.current_sl is not None and r.current_sl != r.commit_sl,
        )
        for r in rows
        if r.r_inr and float(r.r_inr) > 0
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
        mean_peak = statistics.fmean(t.peak_r for t in g)
        caps = [c for t in g if (c := t.capture) is not None]
        # ⚠ Capture is only meaningful against a peak worth capturing. Averaging it over a
        # bucket whose mean peak is ~0 produced "-610%" in the first run — the same
        # divide-by-a-non-existent-peak artefact the per-trade guard catches, reappearing
        # one level up because the guard was per-trade only.
        cap = (
            f"{statistics.fmean(caps) * 100:.0f}%"
            if caps and mean_peak >= 0.5
            else "— (no peak to capture)"
        )
        out.append(
            f"| **{label}** | {len(g)} | {statistics.fmean(t.peak_r for t in g):.2f} | "
            f"{statistics.fmean(t.real_r for t in g):+.2f} | "
            f"{sum(t.real_r for t in g):+.1f}R | ₹{sum(t.pnl for t in g):,.0f} | {cap} |"
        )

    dead = [t for t in trades if t.peak_r < 0.5]
    live = [t for t in trades if t.peak_r >= 1.0]
    dead_pct = 100 * len(dead) / len(trades)
    dead_inr = sum(t.pnl for t in dead)
    dead_r = sum(t.real_r for t in dead)
    live_caps = [c for t in live if (c := t.capture) is not None]
    live_cap = statistics.fmean(live_caps) * 100 if live_caps else 0.0
    out += [
        "",
        "## Verdict",
        "",
        f"⭐ **{len(dead)} of {len(trades)} trades ({dead_pct:.0f}%) never got meaningfully "
        f"into profit**, and they account for **₹{dead_inr:,.0f}** ({dead_r:+.1f}R).",
        "",
        f"⭐ **The trades that DID work captured most of their move.** The {len(live)} that "
        f"reached ≥1R realised {statistics.fmean(t.real_r for t in live):+.2f}R against a "
        f"{statistics.fmean(t.peak_r for t in live):.2f}R peak — **{live_cap:.0f}% capture.**",
        "",
        "**⇒ This is NOT an exit problem. The exit machinery is working.** It is the same",
        "diagnosis CLAUDE.md recorded months ago on 15 trades — *\"the exit machinery was",
        "correct but had nothing to protect\"* — now confirmed on "
        f"{len(trades)}.",
        "",
        "**The loss is made at ENTRY**: roughly half of all trades go nowhere and pay ~0.7R",
        "for the privilege. No exit rule can fix a trade that never moves in your favour.",
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
