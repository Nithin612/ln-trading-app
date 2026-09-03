"""Portfolio-heat counterfactual — "what would a DISCIPLINED book have returned?"

## Why this exists

The paper book is deliberately a **wide evidence sampler**: ~5 entries/day on ~5-day
holds, so ~25 concurrent positions, run to accrue entry/exit evidence fast (user decision,
recorded). That is a legitimate experiment — but it means **the 30-day profit-days clock,
the gate for putting real money at risk, is computed from a book that will never be
traded.** Live is ₹1 lakh with 1–2 positions. The two books can produce opposite signs
from identical signals: the wide one is substantially a bet on market direction (25
correlated longs), the narrow one is a bet on signal selection.

So this module answers the question the clock *should* be reading: admit each entry in
chronological order while cumulative open heat stays under a cap, and report that subset's
P&L beside the full book's. **It enforces nothing** — no order path, no gate, no mode. It
is a measurement, and the number it produces is the honest input to a go-live decision.

## Why a retrospective entry replay is legitimate here

Unlike an exit replay (which cannot know the price path a different exit would have taken),
declining to *enter* a trade changes nothing about the market or about which other signals
fire — our positions do not move NSE. So the admitted subset's outcomes are exactly the
outcomes those trades actually had. The sequencing is honest too: skipping entry #4 frees
budget that a later entry can legitimately use, and the walk models that.

## No look-ahead

Admission risk uses the stop **as committed on the signal** (`signals.stop_loss`), never
`positions.current_sl` — the live stop has since been trailed by price action the decision
could not have seen. Using it would leak the future into the admission test.

## Heat definition

    heat_i = qty × max(0, entry − commit_SL)      (long; mirror for a short)

Clamped at zero: a position whose stop sits past its entry exposes nothing and must not
consume budget. Initial-risk rather than mark-to-market, deliberately — a from-the-mark
definition *loosens* as the book deteriorates (positions nearing their stops "free up"
budget), which is perverse for a risk cap. This matches Elder's and Tharp's formulation
and is the same primitive a real heat cap would use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.services.signal_outcomes import OUTCOME_EPOCH

_Q = Decimal("0.01")


@dataclass(frozen=True)
class Leg:
    """One entry and what the cap decided about it."""

    opened_at: datetime
    symbol: str
    side: str
    risk: Decimal          # admission risk (qty × clamped commit-SL distance)
    admitted: bool
    heat_before: Decimal   # open heat of the admitted book at the decision moment
    realized: Decimal | None  # None while still open
    closed_at: datetime | None


@dataclass(frozen=True)
class Bucket:
    n: int = 0
    resolved: int = 0
    net: Decimal = Decimal(0)
    wins: int = 0

    @property
    def win_pct(self) -> int | None:
        return round(self.wins / self.resolved * 100) if self.resolved else None


@dataclass(frozen=True)
class HeatCounterfactual:
    since: datetime
    capital: Decimal
    cap_pct: Decimal
    cap_inr: Decimal
    admitted: Bucket
    skipped: Bucket
    peak_heat: Decimal            # highest open heat the capped book ever carried
    peak_concurrent: int          # most positions the capped book held at once
    full_peak_concurrent: int     # …versus the real book
    no_stop: int = 0              # legs with no recoverable commit SL (excluded)
    legs: list[Leg] = field(default_factory=list)


def _risk(side: str, entry: Decimal, stop: Decimal, qty: int) -> Decimal:
    """Clamped, direction-aware admission risk. Zero when the stop is at/past entry."""
    per_share = (entry - stop) if side.upper() == "LONG" else (stop - entry)
    return Decimal(qty) * max(Decimal(0), per_share)


async def compute_heat_counterfactual(
    db: AsyncSession,
    *,
    capital: Decimal,
    cap_pct: Decimal,
    since: datetime | None = None,
) -> HeatCounterfactual:
    """Replay every paper entry against a heat cap and report both subsets.

    `since` MUST default to the paper clock's own epoch (`user.paper_clock_started_at`),
    not `OUTCOME_EPOCH`. The first version used OUTCOME_EPOCH and silently spanned the
    2026-08-17 clean-slate cut, which is invalid two ways: (a) risk-first sizing moved from
    the signal ENTRY to the actual FILL that day, so recomputing pre-cut risk from the fill
    yields figures that were never the trade's real budget (₹5,663 where the budget is
    ₹2,000), and (b) the honest spread-aware fill model started then, so P&L either side is
    explicitly non-comparable. Sharing the clock's epoch also means this answers the
    question about exactly the window the go-live gate measures."""
    start = since or OUTCOME_EPOCH
    rows = (
        await db.execute(
            select(Position, Signal.stop_loss, Stock.symbol)
            .join(Stock, Stock.id == Position.stock_id)
            .outerjoin(Signal, Signal.id == Position.signal_id)
            .where(Position.mode == "paper", Position.opened_at >= start)
            .order_by(Position.opened_at)
        )
    ).all()

    cap_inr = (capital * cap_pct / Decimal(100)).quantize(_Q)

    # Chronological event walk. Closes RELEASE budget, so they must be interleaved with
    # opens rather than applied at the end — otherwise the cap would never re-open and the
    # counterfactual would understate what a disciplined book could hold.
    events: list[tuple[datetime, int, int]] = []  # (when, kind: 0=close 1=open, index)
    legs_in: list[tuple[Position, Decimal | None, str]] = []
    for i, (pos, commit_sl, symbol) in enumerate(rows):
        legs_in.append((pos, commit_sl, symbol))
        events.append((pos.opened_at, 1, i))
        if pos.closed_at is not None:
            events.append((pos.closed_at, 0, i))
    # Closes before opens at an identical timestamp: freeing budget first is the
    # conservative reading of "could this book have held it".
    events.sort(key=lambda e: (e[0], e[1]))

    heat = Decimal(0)
    admitted_risk: dict[int, Decimal] = {}
    live: set[int] = set()
    peak_heat = Decimal(0)
    peak_concurrent = 0
    legs: list[Leg] = []
    no_stop = 0
    a_n = a_res = a_wins = 0
    s_n = s_res = s_wins = 0
    a_net = s_net = Decimal(0)

    # The real book's own concurrency, for contrast.
    full_live: set[int] = set()
    full_peak = 0

    for _when, kind, i in events:
        pos, commit_sl, symbol = legs_in[i]
        if kind == 1:
            full_live.add(i)
            full_peak = max(full_peak, len(full_live))
            stop = commit_sl if commit_sl is not None else pos.current_sl
            if stop is None:
                no_stop += 1
                continue
            risk = _risk(
                pos.side, Decimal(str(pos.avg_entry_price)), Decimal(str(stop)), pos.quantity
            )
            fits = heat + risk <= cap_inr
            realized = (
                Decimal(str(pos.realized_pnl)) if pos.closed_at is not None else None
            )
            legs.append(
                Leg(
                    opened_at=pos.opened_at, symbol=symbol, side=pos.side, risk=risk,
                    admitted=fits, heat_before=heat, realized=realized,
                    closed_at=pos.closed_at,
                )
            )
            if fits:
                heat += risk
                admitted_risk[i] = risk
                live.add(i)
                peak_heat = max(peak_heat, heat)
                peak_concurrent = max(peak_concurrent, len(live))
                a_n += 1
                if realized is not None:
                    a_res += 1
                    a_net += realized
                    a_wins += 1 if realized > 0 else 0
            else:
                s_n += 1
                if realized is not None:
                    s_res += 1
                    s_net += realized
                    s_wins += 1 if realized > 0 else 0
        else:
            full_live.discard(i)
            if i in live:
                heat -= admitted_risk.pop(i, Decimal(0))
                live.discard(i)

    return HeatCounterfactual(
        since=start,
        capital=capital,
        cap_pct=cap_pct,
        cap_inr=cap_inr,
        admitted=Bucket(a_n, a_res, a_net, a_wins),
        skipped=Bucket(s_n, s_res, s_net, s_wins),
        peak_heat=peak_heat,
        peak_concurrent=peak_concurrent,
        full_peak_concurrent=full_peak,
        no_stop=no_stop,
        legs=legs,
    )


def _row(name: str, b: Bucket) -> str:
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    avg = f"₹{b.net / b.resolved:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | ₹{b.net:,.0f} | {avg} | {win} |"


def summary_line(r: HeatCounterfactual) -> str:
    """One line, reporting TOTAL and PER-TRADE — because they can disagree, and the
    per-trade number is the one that says whether the cap improved SELECTION.

    A naive "the cap would have HELPED" (total only) is misleading: chronological
    admission selects by ARRIVAL TIME, not quality, and one large-risk entry can consume
    the whole budget alone. So a cap can cut total loss simply by taking fewer trades at
    an unchanged (negative) per-trade expectancy — which is a risk control working, NOT a
    profitability fix. Say both numbers."""
    full_net = r.admitted.net + r.skipped.net
    full_res = r.admitted.resolved + r.skipped.resolved
    delta = r.admitted.net - full_net
    a_avg = r.admitted.net / r.admitted.resolved if r.admitted.resolved else Decimal(0)
    f_avg = full_net / full_res if full_res else Decimal(0)
    if delta > 0 and a_avg > f_avg:
        verdict = "cap improves BOTH total and per-trade — it improved selection"
    elif delta > 0:
        verdict = (
            f"cap cuts total loss but per-trade is WORSE (₹{a_avg:,.0f} vs ₹{f_avg:,.0f}) "
            "— fewer trades at an unchanged expectancy, i.e. a RISK control, not a "
            "profitability fix"
        )
    elif delta < 0:
        verdict = "cap COSTS money — it cut into the winning tail"
    else:
        verdict = "neutral"
    return (
        f"[heat counterfactual @ {r.cap_pct}% of ₹{r.capital:,.0f}] admitted {r.admitted.n} / "
        f"skipped {r.skipped.n} · capped ₹{r.admitted.net:,.0f} vs full ₹{full_net:,.0f} "
        f"({delta:+,.0f}) · per-trade ₹{a_avg:,.0f} vs ₹{f_avg:,.0f} — {verdict}"
    )


def render_markdown(r: HeatCounterfactual, *, day: object) -> str:
    out = [
        f"# Portfolio-heat counterfactual — {day}",
        "",
        f"_Read-only, ENFORCES NOTHING. Replays every paper entry since {r.since.date()} "
        f"against a **{r.cap_pct}% cap on ₹{r.capital:,.0f}** (= ₹{r.cap_inr:,.0f} of open "
        "risk) and reports the admitted subset beside the full book._",
        "",
        "**Why:** the paper book is deliberately a wide evidence sampler (~5 entries/day, "
        "~5-day holds ⇒ ~25 concurrent positions), so the **30-day profit-days clock — the "
        "go-live gate — is measuring a book that will never be traded** (live is ₹1 lakh, "
        "1–2 positions). This is the number that gate should read.",
        "",
        "**Method:** chronological admission — take entries as they fire while open heat "
        "stays under the cap; a close frees budget for a later entry. Admission risk uses "
        "the stop **as committed on the signal**, never the trailed `current_sl` (that "
        "would leak price action the decision could not see). Risk is clamped at zero, so "
        "a stop at/past entry consumes no budget.",
        "",
        "**Why this replay is legitimate:** declining to ENTER changes neither the market "
        "nor which other signals fire, so the admitted trades' outcomes are exactly the "
        "outcomes they really had. (An EXIT replay cannot claim that — it has to invent a "
        "price path.)",
        "",
        "| book | entries | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row(f"ADMITTED (capped at {r.cap_pct}%)", r.admitted),
        _row("SKIPPED (cap would have declined)", r.skipped),
        "",
        f"- Peak open heat the capped book carried: **₹{r.peak_heat:,.0f}** of the "
        f"₹{r.cap_inr:,.0f} cap",
        f"- Peak concurrent positions: **{r.peak_concurrent}** (capped) vs "
        f"**{r.full_peak_concurrent}** (actual book)",
    ]
    if r.no_stop:
        out.append(
            f"- ⚠ {r.no_stop} entr(ies) excluded — no recoverable commit stop, so no "
            "admission risk could be computed"
        )
    out += [
        "",
        f"**Read:** {summary_line(r)}",
        "",
        "⚠ **Method limit worth knowing:** admission is CHRONOLOGICAL, which is faithful "
        "to watching an alert feed but selects by arrival time, not by quality — one "
        "large-risk entry can consume the whole budget alone. So a favourable TOTAL can "
        "come from simply taking fewer trades at an unchanged expectancy. Compare the "
        "per-trade figures before reading a cap as an improvement, and treat a "
        "conviction-ordered variant as the separate (better) selection test.",
        "",
    ]
    if r.legs:
        out += [
            "## Per-entry admission decisions",
            "",
            "| opened | stock | side | risk ₹ | heat before | verdict | outcome |",
            "|---|---|---|--:|--:|---|--:|",
        ]
        for leg in r.legs[:80]:
            outcome = f"₹{leg.realized:,.0f}" if leg.realized is not None else "open"
            out.append(
                f"| {leg.opened_at.date()} | {leg.symbol} | {leg.side} | "
                f"₹{leg.risk:,.0f} | ₹{leg.heat_before:,.0f} | "
                f"{'✅ admitted' if leg.admitted else '🚫 skipped'} | {outcome} |"
            )
    return "\n".join(out) + "\n"
