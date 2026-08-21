"""Signal-age-at-entry diagnostic — how STALE were the signals when we actually traded them.

A positional signal is valid 30 trading days and stays ``active`` (so it keeps surfacing in the
dashboard / Live Signals feed) the WHOLE time — a signal generated on day 0 can therefore be picked
up on day 25, deep into its decay, looking as fresh in the list as a one-day-old one. This report
measures, per resolved paper trade, how far into the signal's validity window we ENTERED (percent
elapsed) and the P&L by that bucket, to prove/quantify the stale-entry leak the user flagged
(trades taken ~day 25 of a 30-day signal). Read-only; never gates anything.

The headline metric is **percent-of-validity-elapsed at entry** — ``(opened_at − created_at) /
(validity_until − created_at)`` — because it is unit-agnostic (both endpoints are known on the
signal) and comparable across classifications, unlike raw calendar days.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.services.signal_outcomes import OUTCOME_EPOCH

# pct-of-validity-elapsed bands; "> 100%" = entered after the signal's validity lapsed.
_BANDS: list[tuple[str, float, float]] = [
    ("0–20% (fresh)", 0.0, 20.0),
    ("20–40%", 20.0, 40.0),
    ("40–60%", 40.0, 60.0),
    ("60–80%", 60.0, 80.0),
    ("80–100% (stale)", 80.0, 100.0),
]
_DETAIL_MAX = 50
_STALE_CUT = 80.0
_FRESH_CUT = 40.0


@dataclass
class Bucket:
    n: int = 0
    net: Decimal = field(default_factory=lambda: Decimal("0"))
    wins: int = 0

    def add(self, realized: Decimal) -> None:
        self.n += 1
        self.net += realized
        if realized > 0:
            self.wins += 1

    @property
    def avg(self) -> Decimal | None:
        return (self.net / self.n) if self.n else None

    @property
    def win_pct(self) -> int | None:
        return round(100 * self.wins / self.n) if self.n else None


@dataclass(frozen=True)
class TradeAge:
    traded_on: date
    symbol: str
    classification: str
    age_days: int  # calendar days from signal commit to entry
    pct_elapsed: float  # of the validity window
    realized: Decimal


@dataclass(frozen=True)
class SignalAgeReport:
    since: datetime
    n_trades: int
    bands: list[tuple[str, Bucket]]
    after_expiry: Bucket
    median_pct: float | None
    median_age_days: float | None
    detail: list[TradeAge] = field(default_factory=list)


def _band_label(pct: float) -> str | None:
    """The band a pct-elapsed falls in, or None for the >100% (after-expiry) overflow."""
    for label, lo, hi in _BANDS:
        # inclusive of the upper edge so exactly-100% lands in the stale band, not overflow.
        if lo <= pct <= hi:
            return label
    return None


async def compute_signal_age(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> SignalAgeReport:
    """For each resolved paper trade (closed position with a signal) OPENED since `since`,
    how far into the signal's validity window we entered, bucketed, with P&L. Cohort is keyed on
    the trade, not the signal's commit date, so a stale entry on an old signal is included."""
    positions = (
        await db.execute(
            select(
                Position.signal_id, Position.realized_pnl, Position.opened_at, Position.closed_at
            ).where(
                Position.mode == "paper",
                Position.closed_at.is_not(None),
                # Bound on the TRADE date, not signal commit — see below.
                Position.opened_at >= since,
            )
        )
    ).all()
    sig_ids = [p.signal_id for p in positions if p.signal_id is not None]
    # NO signal-commit floor: this report is keyed on the TRADE we took, so a stale entry on an
    # OLD signal (committed weeks earlier, entered near expiry — the very archetype this measures)
    # MUST be included. Filtering signals by `created_at >= OUTCOME_EPOCH` would silently drop it
    # (quant-verifier HIGH). `since` bounds the trade date (opened_at) above — a clean-sizer-era
    # floor, NOT the outcome-observation epoch's meaning.
    signals = (
        await db.execute(select(Signal).where(Signal.id.in_(sig_ids)))
    ).scalars().all()
    by_id = {s.id: s for s in signals}
    symbols = {
        sid: sym
        for sid, sym in (
            await db.execute(
                select(Stock.id, Stock.symbol).where(
                    Stock.id.in_([s.stock_id for s in signals])
                )
            )
        ).all()
    }

    bands = {label: Bucket() for label, _, _ in _BANDS}
    after_expiry = Bucket()
    detail: list[TradeAge] = []
    pcts: list[float] = []
    ages: list[int] = []

    for p in positions:
        s = by_id.get(p.signal_id) if p.signal_id else None
        if s is None:
            continue
        span = (s.validity_until - s.created_at).total_seconds()
        elapsed = (p.opened_at - s.created_at).total_seconds()
        if span <= 0 or elapsed < 0:
            continue  # degenerate window or a pre-commit fill — not assessable
        pct = elapsed / span * 100.0
        age_days = int(elapsed // 86_400)
        label = _band_label(pct)
        (bands[label] if label is not None else after_expiry).add(p.realized_pnl)
        pcts.append(pct)
        ages.append(age_days)
        detail.append(
            TradeAge(
                traded_on=p.opened_at.date(),
                symbol=symbols.get(s.stock_id, str(s.stock_id)),
                classification=s.classification,
                age_days=age_days,
                pct_elapsed=pct,
                realized=p.realized_pnl,
            )
        )

    detail.sort(key=lambda d: d.pct_elapsed, reverse=True)
    return SignalAgeReport(
        since=since,
        n_trades=len(detail),
        bands=[(label, bands[label]) for label, _, _ in _BANDS],
        after_expiry=after_expiry,
        median_pct=statistics.median(pcts) if pcts else None,
        median_age_days=statistics.median(ages) if ages else None,
        detail=detail,
    )


def _late_early(r: SignalAgeReport) -> tuple[Bucket, Bucket]:
    """Aggregate late (>80% elapsed, incl. after-expiry) vs early (≤40%) for the headline."""
    late, early = Bucket(), Bucket()
    for d in r.detail:
        if d.pct_elapsed > _STALE_CUT:
            late.n += 1
            late.net += d.realized
            late.wins += 1 if d.realized > 0 else 0
        elif d.pct_elapsed <= _FRESH_CUT:
            early.n += 1
            early.net += d.realized
            early.wins += 1 if d.realized > 0 else 0
    return late, early


def summary_line(r: SignalAgeReport) -> str:
    if not r.n_trades:
        return "[signal age at entry] no resolved paper trades with an assessable signal window yet"
    late, early = _late_early(r)
    return (
        f"[signal age at entry] median entry at {r.median_pct:.0f}% of validity "
        f"({r.median_age_days:.0f}d old); stale >80% n={late.n} net=₹{late.net:,.0f} "
        f"vs fresh ≤40% n={early.n} net=₹{early.net:,.0f}"
    )


def _row(label: str, b: Bucket) -> str:
    if not b.n:
        return f"| {label} | 0 | — | — | — |"
    return f"| {label} | {b.n} | ₹{b.net:,.0f} | ₹{b.avg:,.0f} | {b.win_pct}% |"


def render_markdown(r: SignalAgeReport, *, day: date) -> str:
    out = [
        f"# Signal age at entry — {day}",
        "",
        f"_Read-only. For every resolved paper trade since {r.since.date()} ({r.n_trades} trades), "
        "how far into the signal's validity window we ENTERED. A positional signal stays `active` "
        "for 30 trading days and keeps surfacing the whole time, so a stale signal is one click "
        "away and looks as fresh in the list as a new one — this quantifies whether we are "
        "entering late and what it costs. `%elapsed = (entry − commit) / (validity − commit)`; "
        "100% = at expiry._",
        "",
    ]
    if not r.n_trades:
        out += ["_No resolved paper trades with an assessable signal window yet._", ""]
        return "\n".join(out) + "\n"

    out += [
        f"**Median entry: {r.median_pct:.0f}% of validity elapsed ({r.median_age_days:.0f} "
        "calendar days after the signal was generated).**",
        "",
        "| entry timing (% of validity elapsed) | trades | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|",
        *[_row(label, b) for label, b in r.bands],
        _row("> 100% (after expiry)", r.after_expiry),
        "",
    ]
    late, early = _late_early(r)
    if late.n and early.n and early.avg is not None and late.avg is not None:
        verdict = (
            "STALE ENTRIES ARE WORSE"
            if late.avg < early.avg
            else "no stale-entry penalty visible yet"
        )
        out += [
            f"**Headline: {verdict}.** Fresh (≤40% elapsed): {early.n} trades, avg "
            f"₹{early.avg:,.0f}, win {early.win_pct}%. Stale (>80%): {late.n} trades, avg "
            f"₹{late.avg:,.0f}, win {late.win_pct}%.",
            "",
        ]
    out += [
        "_Why late entries happen: a committed signal is `active` (and shown) until its validity "
        "lapses, and the dedup overlay keeps the OLDEST source of a (stock, direction) — so a "
        "long-lived positional signal re-surfaces for weeks. The AlertBell / Live-Signals "
        "`best by <date>` + `⚠ stale` flags mark the decayed ones at the point of decision._",
        "",
    ]
    if r.detail:
        shown = r.detail[:_DETAIL_MAX]
        out += [
            "## Per-trade (most-elapsed first)",
            "",
            "| traded | stock | class | signal age | %elapsed | outcome |",
            "|---|---|---|--:|--:|--:|",
            *[
                f"| {d.traded_on} | {d.symbol} | {d.classification} | {d.age_days}d | "
                f"{d.pct_elapsed:.0f}% | ₹{d.realized:,.0f} |"
                for d in shown
            ],
            "",
        ]
        if len(r.detail) > _DETAIL_MAX:
            out.append(f"_… {len(r.detail) - _DETAIL_MAX} more not shown._")
            out.append("")
    return "\n".join(out) + "\n"
