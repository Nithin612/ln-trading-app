"""U20 — the would-block cohort for a gate, as chartable trades.

For a chosen gate this returns the committed signals that gate WOULD block, each with its levels,
realized outcome, and a small daily OHLC window around entry — so a human can SEE the set the gate
suppresses. Statistics say WHETHER a gate separates winners from losers; a contact sheet says WHAT.
The regime gate was refuted numerically at −8R; a picture of the trades it blocked might have
surfaced the "proxy for side" problem sooner.

The would-block predicate is NOT re-derived here (working rule W2): it reuses the order path's
single source of truth — `app/signals/eligibility.preview` with the target gate forced ACTIVE and
every other moded gate OFF — so the cohort is exactly the set the order path would 409 on that gate.

Scope: the gates `preview` can judge from a signal alone (no ATR, no live Redis/index state) —
`regime_gate`, `entry_diversity_gate`, `rr_gate`. The others (sl_atr needs an ATR; chase/circuit/
liquidity/market_regime/sector_rs need live state) return `supported=False` with a reason rather
than a fabricated cohort.

Read-only: never writes, never suppresses. Empty when signals/outcomes are absent (the current dev
DB after the 09-07 wipe) — the endpoint returns an empty cohort, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import OhlcvDaily
from app.models.signal import Signal, SignalOutcome
from app.models.stock import Stock
from app.signals import eligibility, restrictions

#: gate_register key (what a registry row carries) → eligibility gate slug, for the supported gates.
#: A register key absent here (chase, liquidity, sl_atr, momentum_retune, …) has no signal-only
#: cohort — the endpoint returns supported=False for it, never a fabricated set. This is the SINGLE
#: owner of the supported set: `SUPPORTED_GATES` and the register's `has_cohort` both derive from
#: it, so they cannot disagree (quant-verifier, 2026-09-09).
REGISTER_KEY_TO_GATE: dict[str, str] = {
    "regime_adx": restrictions.GATE_REGIME,
    "entry_diversity": restrictions.GATE_DIVERSITY,
    "rr_min": restrictions.GATE_RR,
}

#: Gates judgable from the signal alone (see the module docstring), DERIVED from the map above.
SUPPORTED_GATES: frozenset[str] = frozenset(REGISTER_KEY_TO_GATE.values())

#: Diversity is moded by `entry_diversity_gate` but checked under the COMBINED `entry_quality`
#: badge, so `preview` returns GATE_ENTRY_QUALITY when it blocks. Map the moded slug we isolate on
#: → the slug preview actually returns, so the cohort match is correct (regime/rr return their own).
_RETURNED_GATE: dict[str, str] = {restrictions.GATE_DIVERSITY: restrictions.GATE_ENTRY_QUALITY}

_SCAN_LIMIT = 500      # most-recent committed signals to evaluate
_LOOKBACK_DAYS = 45    # calendar days of run-up in each trade's OHLC window
_LOOKAHEAD_DAYS = 20    # calendar days after entry (to show the outcome)


@dataclass(frozen=True)
class Bar:
    t: str  # ISO date
    o: float
    h: float
    low: float
    c: float


@dataclass(frozen=True)
class CohortTrade:
    signal_id: str
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    confidence_pct: int
    reason: str                    # the order path's verbatim rejection detail
    outcome_status: str | None     # SignalOutcome ladder, if recorded
    realized_pnl_pct: float | None
    realized_r: float | None       # pnl% ÷ risk% (risk% = |entry−SL|/entry·100)
    entry_date: str                # ISO date of the signal
    bars: list[Bar]                # daily OHLC around entry (chronological)


@dataclass(frozen=True)
class GateCohort:
    gate: str
    supported: bool
    reason: str | None             # why unsupported (None when supported)
    scanned: int                   # signals evaluated (all loaded, up to _SCAN_LIMIT)
    cohort_count: int              # total blocked among `scanned` (may exceed len(trades))
    cohort_realized_r: float | None    # Σ realized_r over resolved trades
    cohort_realized_pnl_pct: float | None
    trades: list[CohortTrade] = field(default_factory=list)


def _modes_isolating(gate: str) -> dict[str, str]:
    """Every moded gate OFF except `gate` ACTIVE — so `preview` blocks on this gate alone."""
    return {g: ("active" if g == gate else "off") for g in restrictions.MODED_GATES}


def _realized_r(pnl_pct: Decimal | None, entry: Decimal, stop: Decimal) -> float | None:
    if pnl_pct is None or entry <= 0:
        return None
    risk_pct = abs(entry - stop) / entry * Decimal(100)
    if risk_pct == 0:
        return None
    return round(float(pnl_pct / risk_pct), 3)


async def compute_gate_cohort(
    db: AsyncSession,
    *,
    gate: str,
    limit: int,
    rr_min: Decimal,
    min_scoring_factors: int,
    max_dominant_share: Decimal,
    min_sl_atr_mult: Decimal,
) -> GateCohort:
    """The would-block cohort for `gate` (see the module docstring). Fails soft: an unsupported
    gate returns `supported=False` + a reason; absent data returns an empty cohort."""
    if gate not in SUPPORTED_GATES:
        return GateCohort(
            gate=gate, supported=False,
            reason=(
                "cohort not available for this gate (needs an ATR or live state "
                "the preview cannot supply)"
            ),
            scanned=0, cohort_count=0, cohort_realized_r=None, cohort_realized_pnl_pct=None,
        )

    modes = _modes_isolating(gate)
    expected_gate = _RETURNED_GATE.get(gate, gate)
    sigs = list(
        (
            await db.execute(
                select(Signal).order_by(Signal.created_at.desc()).limit(_SCAN_LIMIT)
            )
        ).scalars()
    )

    blocked: list[tuple[Signal, str]] = []
    for s in sigs:
        v = eligibility.preview(
            s, modes=modes, atr=None, market_price=None, fill_price=None, allow_offmarket=True,
            rr_min=rr_min, min_scoring_factors=min_scoring_factors,
            max_dominant_share=max_dominant_share, min_sl_atr_mult=min_sl_atr_mult,
        )
        if v.blocked and v.gate == expected_gate:
            blocked.append((s, v.reason or ""))

    # EVERY loaded signal is evaluated (no early break), so `scanned` = the true evaluated
    # denominator and `cohort_count / scanned` is an honest block rate (quant-verifier A24). Only
    # the OHLC-heavy trade PAYLOAD is bounded to `limit`; the aggregates run over the full set.
    r_vals = [
        r
        for s, _ in blocked
        if (
            r := _realized_r(
                s.outcome_pnl_pct, Decimal(str(s.entry_price)), Decimal(str(s.stop_loss))
            )
        )
        is not None
    ]
    pnl_vals = [float(s.outcome_pnl_pct) for s, _ in blocked if s.outcome_pnl_pct is not None]
    trades = await _attach(db, blocked[:limit])
    return GateCohort(
        gate=gate, supported=True, reason=None,
        scanned=len(sigs), cohort_count=len(blocked),
        cohort_realized_r=round(sum(r_vals), 3) if r_vals else None,
        cohort_realized_pnl_pct=round(sum(pnl_vals), 3) if pnl_vals else None,
        trades=trades,
    )


async def _attach(db: AsyncSession, blocked: list[tuple[Signal, str]]) -> list[CohortTrade]:
    """Attach symbol, outcome, and an OHLC window to each blocked signal. Batched: one stock query,
    one outcome query, one OHLC query over the whole cohort's date span."""
    if not blocked:
        return []
    stock_ids = {s.stock_id for s, _ in blocked}
    sig_ids = [s.id for s, _ in blocked]

    symbol_rows = (
        await db.execute(select(Stock.id, Stock.symbol).where(Stock.id.in_(stock_ids)))
    ).all()
    symbols: dict[int, str] = {int(r.id): str(r.symbol) for r in symbol_rows}
    outcomes = {
        o.signal_id: o
        for o in (
            await db.execute(select(SignalOutcome).where(SignalOutcome.signal_id.in_(sig_ids)))
        ).scalars()
    }

    lo = min(s.created_at for s, _ in blocked) - timedelta(days=_LOOKBACK_DAYS)
    hi = max(s.created_at for s, _ in blocked) + timedelta(days=_LOOKAHEAD_DAYS)
    ohlc_rows = (
        await db.execute(
            select(OhlcvDaily.stock_id, OhlcvDaily.time, OhlcvDaily.open,
                   OhlcvDaily.high, OhlcvDaily.low, OhlcvDaily.close)
            .where(OhlcvDaily.stock_id.in_(stock_ids), OhlcvDaily.time >= lo, OhlcvDaily.time <= hi)
            .order_by(OhlcvDaily.time)
        )
    ).all()
    by_stock: dict[int, list[Any]] = {}
    for r in ohlc_rows:
        by_stock.setdefault(r.stock_id, []).append(r)

    trades: list[CohortTrade] = []
    for s, reason in blocked:
        entry = Decimal(str(s.entry_price))
        stop = Decimal(str(s.stop_loss))
        w_lo = s.created_at - timedelta(days=_LOOKBACK_DAYS)
        w_hi = s.created_at + timedelta(days=_LOOKAHEAD_DAYS)
        bars = [
            Bar(t=r.time.date().isoformat(), o=float(r.open), h=float(r.high),
                low=float(r.low), c=float(r.close))
            for r in by_stock.get(s.stock_id, [])
            if w_lo <= r.time <= w_hi
        ]
        o = outcomes.get(s.id)
        trades.append(
            CohortTrade(
                signal_id=s.id,
                symbol=symbols.get(s.stock_id, ""),
                direction=s.direction,
                entry=float(entry),
                stop_loss=float(stop),
                take_profit=float(s.take_profit),
                confidence_pct=s.confidence_pct,
                reason=reason,
                outcome_status=o.status if o else None,
                realized_pnl_pct=(
                    float(s.outcome_pnl_pct) if s.outcome_pnl_pct is not None else None
                ),
                realized_r=_realized_r(s.outcome_pnl_pct, entry, stop),
                entry_date=s.created_at.date().isoformat(),
                bars=bars,
            )
        )
    return trades
