"""Outcome analytics API (Phase 6 — per-style hit-rate / expectancy).

GET /analytics/outcomes — aggregates the tick-level signal_outcomes (slice 3.6)
by trading style. Read-only and cohorted at OUTCOME_EPOCH; empty until live
outcomes accrue, then feeds the Phase-6 outcome dashboards. Pure observability —
never touches scoring, sizing, gating, or backtests.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.strategy import StrategyRun
from app.models.user import User
from app.schemas.profile import PROFILE_STYLES
from app.services import benchmark_curve as bc_service
from app.services import gate_cohort as cohort_service
from app.services.signal_outcomes import OUTCOME_EPOCH

router = APIRouter(prefix="/analytics", tags=["analytics"])


class OutcomeStyleStats(BaseModel):
    style: str
    total: int          # cohorted outcomes for this style
    entered: int        # entry zone was touched
    wins: int           # tp_first
    losses: int         # sl_first
    no_entry: int       # expired_untouched
    timed_out: int      # expired_open (entered, neither SL nor TP)
    pending: int        # open + entry_touched (not yet resolved)
    sample: int         # resolved = wins + losses + no_entry + timed_out
    hit_rate: float | None        # wins / (wins + losses)
    entry_rate: float | None      # entered / total
    avg_return_pct: float | None  # mean signals.outcome_pnl_pct (expectancy per signal)


class OutcomeAnalyticsResponse(BaseModel):
    epoch: datetime
    total_outcomes: int
    styles: list[OutcomeStyleStats]


# Fixed tables, bind-parameterized value — no dynamic identifiers.
_AGG_SQL = text("""
    SELECT p.style AS style,
           count(*) AS total,
           count(*) FILTER (WHERE o.entry_touched_at IS NOT NULL) AS entered,
           count(*) FILTER (WHERE o.status = 'tp_first') AS wins,
           count(*) FILTER (WHERE o.status = 'sl_first') AS losses,
           count(*) FILTER (WHERE o.status = 'expired_untouched') AS no_entry,
           count(*) FILTER (WHERE o.status = 'expired_open') AS timed_out,
           count(*) FILTER (WHERE o.status IN ('open', 'entry_touched')) AS pending,
           avg(s.outcome_pnl_pct) FILTER (WHERE s.outcome_pnl_pct IS NOT NULL) AS avg_return
    FROM signal_outcomes o
    JOIN signals s ON s.id = o.signal_id
    JOIN strategy_profiles p ON p.id = s.profile_id
    WHERE s.created_at >= :epoch
      -- Shadow suggestions come from profiles that have NOT earned activation
      -- (the intraday trio is negative risk-adjusted on walk-forward). Their
      -- outcomes are recorded on purpose, but mixing them into the headline
      -- hit-rate/expectancy would corrupt the very evidence the shadow layer
      -- exists to produce — and would silently drag the intraday style's
      -- numbers toward a strategy nobody is trading.
      AND s.is_shadow IS FALSE
    GROUP BY p.style
""")


@router.get("/outcomes", response_model=OutcomeAnalyticsResponse)
async def outcome_analytics(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> OutcomeAnalyticsResponse:
    """Per-style outcome summary. Every style is returned (zeros when it has no
    cohorted outcomes yet) so the dashboard renders a stable grid."""
    rows = (await db.execute(_AGG_SQL, {"epoch": OUTCOME_EPOCH})).mappings().all()
    by_style = {r["style"]: r for r in rows}

    styles: list[OutcomeStyleStats] = []
    total_outcomes = 0
    for style in PROFILE_STYLES:
        r = by_style.get(style)
        if r is None:
            styles.append(
                OutcomeStyleStats(
                    style=style, total=0, entered=0, wins=0, losses=0, no_entry=0,
                    timed_out=0, pending=0, sample=0, hit_rate=None, entry_rate=None,
                    avg_return_pct=None,
                )
            )
            continue
        total = int(r["total"])
        entered = int(r["entered"])
        wins = int(r["wins"])
        losses = int(r["losses"])
        no_entry = int(r["no_entry"])
        timed_out = int(r["timed_out"])
        decided = wins + losses
        sample = decided + no_entry + timed_out
        total_outcomes += total
        styles.append(
            OutcomeStyleStats(
                style=style,
                total=total,
                entered=entered,
                wins=wins,
                losses=losses,
                no_entry=no_entry,
                timed_out=timed_out,
                pending=int(r["pending"]),
                sample=sample,
                hit_rate=(wins / decided) if decided else None,
                entry_rate=(entered / total) if total else None,
                avg_return_pct=(float(r["avg_return"]) if r["avg_return"] is not None else None),
            )
        )
    return OutcomeAnalyticsResponse(
        epoch=OUTCOME_EPOCH, total_outcomes=total_outcomes, styles=styles
    )


# --------------------------------------------------------------------------- #
# U1 (data layer) — the gate / hypothesis register as an API                  #
# --------------------------------------------------------------------------- #
# The register (H4) is the failed-hypothesis archive + the U4 trial counter that gives the
# deflation bar its N. Today it is readable only inside the daily-report markdown. This exposes
# it as data so the registry PAGE (U1: current status · U6: rejected/reverted candidates kept
# visible · U4: observed-vs-assumed trials) can render it. Read-only, no DB — the register is
# static, curated Python data. Money-path untouched.


class GateHypothesisOut(BaseModel):
    key: str
    name: str
    status: str  # active | shadow | reverted | decided_no | research
    prediction: str
    bar: str
    stands_at: str
    verdict: str
    counts_as_trial: bool
    review_due: str | None
    #: U20 — whether a would-block cohort (the /cohort/{key} drill-down) exists for this gate.
    has_cohort: bool


class GateRegisterResponse(BaseModel):
    as_of: str
    #: OBSERVED multiple-testing trials — a LOWER BOUND on N (variants not yet counted), so
    #: `observed < assumed` does NOT license calling the bar conservative (see gate_register).
    trials_attempted: int
    assumed_trials: int  # DEFAULT_TRIALS used in the deflation
    counts: dict[str, int]  # status → count
    due_for_review: list[str]  # keys still carrying a review trigger (constraint #8)
    hypotheses: list[GateHypothesisOut]


@router.get("/gate-register", response_model=GateRegisterResponse)
async def gate_register_view(
    _user: Annotated[User, Depends(get_current_user)],
) -> GateRegisterResponse:
    """The gate/hypothesis register as data (U1). Every partition we have searched, decided or
    shipped — including the reverted and decided-no ones, kept visible on purpose (U6), because
    a register that quietly drops its failures is the selection bias the deflation corrects."""
    from app.services import gate_register as gr
    from app.services.deflated_sharpe import DEFAULT_TRIALS

    counts = {s.value: len(gr.by_status(s)) for s in gr.Status}
    return GateRegisterResponse(
        as_of=gr.AS_OF,
        trials_attempted=gr.trials_attempted(),
        assumed_trials=DEFAULT_TRIALS,
        counts=counts,
        due_for_review=[h.key for h in gr.due_for_review()],
        hypotheses=[
            GateHypothesisOut(
                key=h.key,
                name=h.name,
                status=h.status.value,
                prediction=h.prediction,
                bar=h.bar,
                stands_at=h.stands_at,
                verdict=h.verdict,
                counts_as_trial=h.counts_as_trial,
                review_due=h.review_due,
                has_cohort=h.key in cohort_service.REGISTER_KEY_TO_GATE,
            )
            for h in gr.REGISTER
        ],
    )


# --------------------------------------------------------------------------- #
# U11 — the NIFTY buy-and-hold benchmark as a series on a backtest equity curve #
# --------------------------------------------------------------------------- #
# H2/U2: a benchmark in its own section gets skipped; one on the same curve cannot be. The equity
# curve is per-trade and the engine is FROZEN (no dates), so the benchmark is aligned to each
# trade's exit date (see app/services/benchmark_curve). Read-only; fails CLOSED to available=False
# rather than substituting a nearby date. Empty until index_ohlcv_1d is populated.


class BenchmarkCurveResponse(BaseModel):
    run_id: int
    symbol: str
    available: bool
    #: Why the benchmark could not be built (index absent, no bar before the window start, …).
    reason: str | None
    #: Benchmark equity indexed to 100 at the window start, PARALLEL to the run's `equity_curve`.
    #: Empty when `available` is False.
    points: list[float]
    benchmark_return_pct: float | None
    strategy_return_pct: float | None


@router.get("/benchmark-curve", response_model=BenchmarkCurveResponse)
async def benchmark_curve_view(
    run_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> BenchmarkCurveResponse:
    """NIFTY buy-and-hold aligned to a backtest run's equity curve (U11). 404 if the run is unknown;
    otherwise a series (or an honest `available=False` + reason when it can't be made)."""
    run = await db.get(StrategyRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    bc = await bc_service.compute_benchmark_curve(
        db, equity_curve=run.equity_curve, trades_json=run.trades_json
    )
    return BenchmarkCurveResponse(
        run_id=run_id,
        symbol=bc.symbol,
        available=bc.available,
        reason=bc.reason,
        points=bc.points,
        benchmark_return_pct=bc.benchmark_return_pct,
        strategy_return_pct=bc.strategy_return_pct,
    )


# --------------------------------------------------------------------------- #
# U20 — the would-block cohort of a gate, as chartable trades                   #
# --------------------------------------------------------------------------- #
# Statistics say WHETHER a gate separates winners from losers; a contact sheet says WHAT. The
# cohort reuses the order path's own verdict (eligibility.preview, one gate active) — no parallel
# predicate (W2). Read-only; empty when signals are absent (the current dev DB). See gate_cohort.


class CohortBar(BaseModel):
    t: str  # ISO date
    o: float
    h: float
    low: float
    c: float


class CohortTradeOut(BaseModel):
    signal_id: str
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    confidence_pct: int
    reason: str
    outcome_status: str | None
    realized_pnl_pct: float | None
    realized_r: float | None
    entry_date: str
    bars: list[CohortBar]


class GateCohortResponse(BaseModel):
    gate_key: str            # the gate_register key requested
    gate: str                # the eligibility gate slug ("" when unsupported)
    gate_status: str | None  # the register status (reverted / shadow / …), if the key is known
    supported: bool
    reason: str | None
    scanned: int
    cohort_count: int
    cohort_realized_r: float | None
    cohort_realized_pnl_pct: float | None
    trades: list[CohortTradeOut]


@router.get("/cohort/{gate_key}", response_model=GateCohortResponse)
async def gate_cohort_view(
    gate_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
) -> GateCohortResponse:
    """The trades a gate WOULD block, each with levels, outcome, and an OHLC window (U20). Supported
    for the signal-only gates (regime · diversity · R:R); others return supported=False."""
    from app.services import gate_register as gr

    hyp = gr.get(gate_key)
    gate_status = hyp.status.value if hyp is not None else None
    slug = cohort_service.REGISTER_KEY_TO_GATE.get(gate_key)
    if slug is None:
        return GateCohortResponse(
            gate_key=gate_key, gate="", gate_status=gate_status, supported=False,
            reason=(
                "no signal-only would-block cohort for this gate "
                "(needs live state, or unknown key)"
            ),
            scanned=0, cohort_count=0, cohort_realized_r=None, cohort_realized_pnl_pct=None,
            trades=[],
        )

    cohort = await cohort_service.compute_gate_cohort(
        db, gate=slug, limit=limit,
        rr_min=Decimal(str(settings.rr_min)),
        min_scoring_factors=settings.entry_min_scoring_factors,
        max_dominant_share=Decimal(str(settings.entry_max_dominant_factor_share)),
        min_sl_atr_mult=Decimal(str(settings.entry_min_sl_atr_mult)),
    )
    return GateCohortResponse(
        gate_key=gate_key, gate=slug, gate_status=gate_status,
        supported=cohort.supported, reason=cohort.reason,
        scanned=cohort.scanned, cohort_count=cohort.cohort_count,
        cohort_realized_r=cohort.cohort_realized_r,
        cohort_realized_pnl_pct=cohort.cohort_realized_pnl_pct,
        trades=[
            CohortTradeOut(
                signal_id=t.signal_id, symbol=t.symbol, direction=t.direction,
                entry=t.entry, stop_loss=t.stop_loss, take_profit=t.take_profit,
                confidence_pct=t.confidence_pct, reason=t.reason,
                outcome_status=t.outcome_status, realized_pnl_pct=t.realized_pnl_pct,
                realized_r=t.realized_r, entry_date=t.entry_date,
                bars=[CohortBar(t=b.t, o=b.o, h=b.h, low=b.low, c=b.c) for b in t.bars],
            )
            for t in cohort.trades
        ],
    )
