"""Sector/index relative-strength shadow measurement — MCE slice 3.

The forward-evidence half of the sector-RS overlay (`app/signals/sector_rs.py` +
`app/services/benchmark.py`), mirroring `regime_gate_shadow` / `entry_quality_shadow`:
it runs the overlay over the LIVE tradeable signal cohort and reports what it WOULD
suppress, with a flip-readiness banner. Read-only; never suppresses anything.

It RECOMPUTES the RS verdict per signal (benchmark closes aligned to the signal's own
`created_at`, no look-ahead) rather than reading a stamp, so evidence accrues over the
whole cohort even while the gate is `off`/`shadow` — but only once `index_ohlcv_1d` has
the benchmark history (until then signals land in the `no benchmark data` bucket). The
per-entry table is the MCE's standing requirement to SHOW each entry's sector/index RS,
so we never trade blind to sector leadership.

Partition (among the cohort): **blocked** = would-suppress (excess below threshold for
the side), **passed** = assessable and eligible, **no benchmark data** = not assessable
(no/short aligned series). Flip readiness compares blocked vs passed and speaks to the
behaviour-changing shadow→active flip (which also needs §8 + sign-off).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.services.benchmark import load_rs_context
from app.services.signal_outcomes import OUTCOME_EPOCH
from app.signals import sector_rs

# Same n=20 rank floor the other shadows use before advising a flip.
FORWARD_EVIDENCE_TARGET_N = 20

# Cap the per-entry detail table so a long cohort stays readable.
_DETAIL_MAX = 50


@dataclass
class Bucket:
    n: int = 0
    resolved: int = 0  # traded AND closed (a realized P&L exists)
    net: Decimal = field(default_factory=lambda: Decimal("0"))
    wins: int = 0

    def add(self, realized: Decimal | None) -> None:
        self.n += 1
        if realized is not None:
            self.resolved += 1
            self.net += realized
            if realized > 0:
                self.wins += 1

    @property
    def avg(self) -> Decimal | None:
        return (self.net / self.resolved) if self.resolved else None

    @property
    def win_pct(self) -> int | None:
        return round(100 * self.wins / self.resolved) if self.resolved else None


@dataclass(frozen=True)
class SignalRs:
    """One committed signal's RS reading (for the per-entry context table)."""

    created_at: datetime
    symbol: str
    side: str
    benchmark: str | None
    excess_pct: Decimal | None
    blocked: bool
    realized: Decimal | None


@dataclass(frozen=True)
class SectorRsShadow:
    since: datetime
    n_signals: int
    blocked: Bucket  # would-suppress (assessable, excess below threshold)
    passed: Bucket  # assessable, eligible
    no_data: Bucket  # not assessable (no/short benchmark series)
    detail: list[SignalRs] = field(default_factory=list)


async def _realized_by_signal(db: AsyncSession, signal_ids: list[str]) -> dict[str, Decimal]:
    """Σ realized P&L of each signal's CLOSED paper positions (reopen-safe), one query."""
    out: dict[str, Decimal] = {}
    if not signal_ids:
        return out
    for sig_id, realized, closed_at in (
        await db.execute(
            select(Position.signal_id, Position.realized_pnl, Position.closed_at).where(
                Position.signal_id.in_(signal_ids), Position.mode == "paper"
            )
        )
    ).all():
        if closed_at is not None and sig_id is not None:
            out[sig_id] = out.get(sig_id, Decimal("0")) + realized
    return out


async def _symbols(db: AsyncSession, stock_ids: list[int]) -> dict[int, str]:
    if not stock_ids:
        return {}
    rows = (await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids)))).all()
    return {sid: sym for sid, sym in rows}


async def compute_sector_rs_shadow(
    db: AsyncSession, *, since: datetime = OUTCOME_EPOCH
) -> SectorRsShadow:
    """Recompute the RS overlay over the tradeable signal cohort (is_shadow FALSE) since
    `since`, partitioned by would-block / eligible / no-benchmark-data, with outcomes."""
    sigs = (
        await db.execute(
            select(Signal).where(Signal.is_shadow.is_(False), Signal.created_at >= since)
        )
    ).scalars().all()
    realized = await _realized_by_signal(db, [s.id for s in sigs])
    symbols = await _symbols(db, [s.stock_id for s in sigs])

    lookback = settings.sector_rs_lookback
    min_excess = Decimal(str(settings.sector_rs_min_excess_pct))
    blocked, passed, no_data = Bucket(), Bucket(), Bucket()
    detail: list[SignalRs] = []

    for s in sigs:
        ctx = await load_rs_context(db, s.stock_id, lookback=lookback, as_of=s.created_at)
        v = sector_rs.evaluate(
            stock_closes=ctx.stock_closes if ctx else [],
            benchmark_closes=ctx.benchmark_closes if ctx else None,
            side=s.direction,
            lookback=lookback,
            min_excess_pct=min_excess,
            benchmark_label=ctx.benchmark_symbol if ctx else None,
        )
        r = realized.get(s.id)
        # excess is None ⇒ not assessable (no/short benchmark series) — fails open live,
        # so it belongs in its own bucket, NOT counted as an eligible "passed".
        if v.excess_pct is None:
            no_data.add(r)
        elif v.blocked:
            blocked.add(r)
        else:
            passed.add(r)
        if v.excess_pct is not None:
            detail.append(
                SignalRs(
                    created_at=s.created_at,
                    symbol=symbols.get(s.stock_id, str(s.stock_id)),
                    side=v.side,
                    benchmark=v.benchmark_label,
                    excess_pct=v.excess_pct,
                    blocked=v.blocked,
                    realized=r,
                )
            )

    detail.sort(key=lambda d: d.created_at, reverse=True)
    return SectorRsShadow(
        since=since,
        n_signals=len(sigs),
        blocked=blocked,
        passed=passed,
        no_data=no_data,
        detail=detail,
    )


def rs_flip_ready(r: SectorRsShadow) -> tuple[bool, str]:
    """Is there forward evidence to flip the sector-RS gate ACTIVE? Bar (all): ≥ N
    resolved would-block trades, that set net-losing, AND worse than the eligible set.
    Advice for the human sign-off — never flips anything."""
    b, p = r.blocked, r.passed
    if b.resolved < FORWARD_EVIDENCE_TARGET_N:
        return False, (
            f"{b.resolved}/{FORWARD_EVIDENCE_TARGET_N} resolved would-block trades — keep accruing"
        )
    if b.avg is None or b.avg >= 0:
        return False, f"would-block set is not net-negative ({b.avg}) — do NOT flip"
    if p.avg is not None and b.avg >= p.avg:
        return False, f"would-block ({b.avg}) not worse than eligible ({p.avg}) — do NOT flip"
    return True, (
        f"would-block net-negative ({b.avg}), worse than eligible ({p.avg}) — READY for sign-off"
    )


def readiness_line(r: SectorRsShadow) -> str:
    ready, reason = rs_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    return f"[sector-RS forward evidence] {tag} — {reason}"


def _row(name: str, b: Bucket) -> str:
    avg = f"₹{b.avg:,.0f}" if b.avg is not None else "—"
    win = f"{b.win_pct}%" if b.win_pct is not None else "—"
    net = f"₹{b.net:,.0f}" if b.resolved else "—"
    return f"| {name} | {b.n} | {b.resolved} | {net} | {avg} | {win} |"


def _detail_row(d: SignalRs) -> str:
    ex = f"{d.excess_pct:+.2f}%" if d.excess_pct is not None else "—"
    outcome = f"₹{d.realized:,.0f}" if d.realized is not None else "open/none"
    flag = "🚫 would-block" if d.blocked else "✅ eligible"
    return (
        f"| {d.created_at.date()} | {d.symbol} | {d.side} | {d.benchmark or '—'} "
        f"| {ex} | {flag} | {outcome} |"
    )


def render_markdown(r: SectorRsShadow, *, day: date) -> str:
    mode = settings.sector_rs_gate_mode
    out = [
        f"# Sector/index relative-strength shadow (live signals) — {day}",
        "",
        f"_Read-only. The sector-RS overlay recomputed over the tradeable signal cohort since "
        f"{r.since.date()} ({r.n_signals} signals), benchmark closes aligned to each signal's "
        f"decision time (no look-ahead). Gate mode: **{mode}**. A signal is 'would-block' when it "
        "UNDER-performs its benchmark index (a short: out-performs) by more than "
        f"`sector_rs_min_excess_pct` ({settings.sector_rs_min_excess_pct}%) over "
        f"{settings.sector_rs_lookback} sessions. 'no benchmark data' = index history not deep "
        "enough yet (fails open live). A would-block set net-negative AND worse than the eligible "
        "set is the evidence to flip the gate active._",
        "",
        "| set | signals | resolved | net ₹ | avg ₹ | win% |",
        "|---|--:|--:|--:|--:|--:|",
        _row("would-BLOCK (RS against the side)", r.blocked),
        _row("eligible (RS in favour of the side)", r.passed),
        _row("no benchmark data (fails open)", r.no_data),
        "",
    ]
    ready, reason = rs_flip_ready(r)
    tag = "✅ READY" if ready else "⏳ NOT READY"
    out += [
        f"**sector-RS flip readiness:** {tag} — {reason}. Flipping the gate active is "
        "behaviour-changing → needs forward evidence + a §8-on-≥2y regression + explicit user "
        "sign-off (reversible via `sector_rs_gate_mode=shadow`).",
        "",
    ]
    if r.detail:
        shown = r.detail[:_DETAIL_MAX]
        out += [
            "## Per-entry context (each committed signal's sector/index RS)",
            "",
            "| date | stock | side | benchmark | excess vs bench | RS verdict | outcome |",
            "|---|---|---|---|--:|---|--:|",
            *[_detail_row(d) for d in shown],
            "",
        ]
        if len(r.detail) > _DETAIL_MAX:
            out.append(f"_… {len(r.detail) - _DETAIL_MAX} more assessable signals not shown._")
            out.append("")
    else:
        out += ["_No signals had benchmark history yet — index OHLC still backfilling._", ""]
    return "\n".join(out) + "\n"
