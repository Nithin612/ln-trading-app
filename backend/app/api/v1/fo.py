"""F&O analytics endpoints — Phase 4 slice 4.1 (read-only).

  GET /fo/chain       — option chain (CE/PE legs) for an underlying + expiry,
                        optionally with per-leg IV + Greeks (?greeks=true)
  GET /fo/analytics   — PCR, max pain, futures basis, India VIX regime
  GET /fo/vix-regime  — India VIX volatility regime standalone

Computed from the Phase-0 recorders. The options MATH (implied vol, Greeks) is
never implemented here — it is Rust (`tradecore`, slice 4.2); this layer only
assembles inputs and shapes results.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.fo import (
    BasisOut,
    ChainLegOut,
    ChainOut,
    ExitPlanOut,
    ExpiriesOut,
    ExpiryOut,
    FoAnalyticsOut,
    IvRankOut,
    OptionLegOut,
    PcrOut,
    SuggestionOut,
    SuggestionsOut,
    UnderlyingsOut,
    VixRegimeOut,
)
from app.services import fo_analytics as fa
from app.services import fo_suggestions as fs

router = APIRouter(prefix="/fo", tags=["f&o"])

_SOURCE = "^(eod|intraday)$"


def _pcr_out(pcr: fa.PutCallRatio) -> PcrOut:
    return PcrOut(
        pcr_oi=pcr.pcr_oi,
        pcr_volume=pcr.pcr_volume,
        total_ce_oi=pcr.total_ce_oi,
        total_pe_oi=pcr.total_pe_oi,
    )


def _basis_out(b: fa.Basis | None) -> BasisOut | None:
    if b is None:
        return None
    return BasisOut(
        fut_close=b.fut_close,
        underlying_close=b.underlying_close,
        basis=b.basis,
        basis_pct=b.basis_pct,
    )


def _vix_out(v: fa.VixRegime | None) -> VixRegimeOut | None:
    if v is None:
        return None
    return VixRegimeOut(current=v.current, percentile=v.percentile, band=v.band, sample=v.sample)


@router.get("/underlyings", response_model=UnderlyingsOut)
async def get_underlyings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> UnderlyingsOut:
    """Underlyings the chain/analytics endpoints can actually serve — so the UI
    offers what has been recorded rather than hardcoding a symbol list."""
    day, symbols = await fa.available_underlyings(db)
    return UnderlyingsOut(as_of=day, symbols=symbols)


@router.get("/expiries", response_model=ExpiriesOut)
async def get_expiries(
    symbol: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ExpiriesOut:
    """Expiries still open on the latest recorded day (nearest first). Empty is
    a valid answer — nothing recorded for that underlying."""
    sym = symbol.upper()
    day, expiries = await fa.available_expiries(db, sym)
    return ExpiriesOut(
        symbol=sym,
        as_of=day,
        expiries=[ExpiryOut(expiry=e, dte=(e - day).days) for e in expiries] if day else [],
    )


@router.get("/chain", response_model=ChainOut)
async def get_chain(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: date = Query(...),
    source: str = Query("eod", pattern=_SOURCE),
    strikes: int = Query(0, ge=0, le=50, description="±N strikes around ATM; 0 = all"),
    greeks: bool = Query(False, description="also invert each quote to IV + Greeks (Black-76)"),
    rate: float = Query(0.065, ge=0.0, le=0.5, description="risk-free proxy (cont. comp.)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ChainOut:
    sym = symbol.upper()
    rows = await fa.load_chain(db, sym, expiry, source=source)
    # The chain's own trading day drives BOTH the spot lookup and the Greeks,
    # so the ladder is internally consistent.
    as_of_day = await fa.chain_day(db, sym, expiry, source=source)

    # Spot: prefer this expiry's own futures row, else any contract recorded
    # that day. Weekly expiries have no future, and without a spot there is no
    # ATM strike — which would silently turn "±N strikes" into the whole chain.
    spot = await fa.latest_spot(db, sym, expiry)
    if spot is None and as_of_day is not None:
        spot = await fa.spot_on_day(db, sym, as_of_day)
    atm = fa.atm_strike(rows, spot) if spot is not None else None
    if strikes > 0 and spot is not None:
        rows = fa.near_atm(rows, spot, strikes)

    # Greeks are opt-in: two batched tradecore calls per side. They need a
    # forward for THIS expiry and a positive time-to-expiry. Any missing piece
    # leaves every Greek None rather than pricing against a guessed input.
    priced: dict[tuple[Decimal, str], fa.LegGreeks] = {}
    fut_price: Decimal | None = None
    forward_source: str | None = None
    dte: int | None = None
    if greeks and rows and as_of_day is not None and (expiry - as_of_day).days > 0:
        days = (expiry - as_of_day).days
        fwd = await fa.forward_for_expiry(db, sym, expiry, on_day=as_of_day)
        if fwd is not None:
            fut_price = fwd.price
            forward_source = fwd.source
            dte = days
            priced = fa.price_chain_greeks(
                rows, fwd=float(fwd.price), t=days / 365.0, rate=rate
            )

    legs: list[ChainLegOut] = []
    for r in sorted(rows, key=lambda r: (r.strike, r.option_type)):
        g = priced.get((r.strike, r.option_type))
        legs.append(
            ChainLegOut(
                strike=r.strike,
                option_type=r.option_type,
                oi=r.oi,
                volume=r.volume,
                ltp=r.ltp,
                iv=g.iv if g else None,
                delta=g.delta if g else None,
                gamma=g.gamma if g else None,
                vega=g.vega if g else None,
                theta=g.theta if g else None,
            )
        )
    return ChainOut(
        symbol=sym,
        expiry=expiry,
        source=source,
        spot=spot,
        atm_strike=atm,
        legs=legs,
        as_of=as_of_day,
        fut_price=fut_price,
        forward_source=forward_source,
        dte=dte,
    )


@router.get("/analytics", response_model=FoAnalyticsOut)
async def get_analytics(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: date = Query(...),
    source: str = Query("eod", pattern=_SOURCE),
    vix_lookback: int = Query(252, ge=2, le=2000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FoAnalyticsOut:
    sym = symbol.upper()
    rows = await fa.load_chain(db, sym, expiry, source=source)
    spot = await fa.latest_spot(db, sym, expiry)
    basis = await fa.futures_basis(db, sym, expiry)
    vix = await fa.vix_regime(db, lookback=vix_lookback)
    return FoAnalyticsOut(
        symbol=sym,
        expiry=expiry,
        source=source,
        spot=spot,
        atm_strike=fa.atm_strike(rows, spot) if spot is not None else None,
        pcr=_pcr_out(fa.put_call_ratio(rows)),
        max_pain=fa.max_pain(rows),
        basis=_basis_out(basis),
        vix=_vix_out(vix),
    )


def _suggestion_out(c: fs.SpreadCandidate) -> SuggestionOut:
    return SuggestionOut(
        structure=c.structure,
        legs=[
            OptionLegOut(action=leg.action, option_type=leg.option_type, strike=leg.strike,
                         premium=leg.premium)
            for leg in c.legs
        ],
        net_credit=c.net_credit,
        max_profit=c.max_profit,
        max_loss=c.max_loss,
        width=c.width,
        breakevens=list(c.breakevens),
        pop=c.pop,
        expectancy=c.expectancy,
        margin_est=c.margin_est,
        return_on_margin=c.return_on_margin,
        short_delta=c.short_delta,
        dte=c.dte,
        expiry=c.expiry,
        exit_plan=ExitPlanOut(
            take_profit_credit=c.exit_plan.take_profit_credit,
            stop_loss_amount=c.exit_plan.stop_loss_amount,
            time_stop_dte=c.exit_plan.time_stop_dte,
        ),
        rationale=c.rationale,
    )


@router.get("/suggestions", response_model=SuggestionsOut)
async def get_suggestions(
    symbol: str = Query(..., min_length=1, max_length=32),
    rate: float = Query(0.065, ge=0.0, le=0.5),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SuggestionsOut:
    """DRAFT (slice 4.3 strawman) — defined-risk option-selling candidates. An
    empty list is a valid answer (nothing clears the gates). Rules are
    conservative placeholders pending calibration; not a recommendation yet."""
    sym = symbol.upper()
    candidates = await fs.suggest_option_sells(db, sym, rate=rate)
    return SuggestionsOut(symbol=sym, candidates=[_suggestion_out(c) for c in candidates])


@router.get("/iv-rank", response_model=IvRankOut)
async def get_iv_rank(
    symbol: str = Query(..., min_length=1, max_length=32),
    rate: float = Query(0.065, ge=0.0, le=0.5, description="risk-free proxy (cont. comp.)"),
    lookback: int = Query(252, ge=2, le=2000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IvRankOut:
    sym = symbol.upper()
    r = await fa.iv_rank(db, sym, rate=rate, lookback=lookback)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="insufficient option history to compute IV rank",
        )
    return IvRankOut(
        symbol=sym,
        as_of=r.as_of,
        current_iv=r.current_iv,
        rank=r.rank,
        percentile=r.percentile,
        min_iv=r.min_iv,
        max_iv=r.max_iv,
        sample=r.sample,
    )


@router.get("/vix-regime", response_model=VixRegimeOut)
async def get_vix_regime(
    lookback: int = Query(252, ge=2, le=2000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VixRegimeOut:
    regime = await fa.vix_regime(db, lookback=lookback)
    if regime is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no India VIX history recorded"
        )
    return VixRegimeOut(
        current=regime.current,
        percentile=regime.percentile,
        band=regime.band,
        sample=regime.sample,
    )
