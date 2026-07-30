"""F&O analytics endpoints — Phase 4 slice 4.1 (read-only).

  GET /fo/chain       — option chain (CE/PE legs) for an underlying + expiry
  GET /fo/analytics   — PCR, max pain, futures basis, India VIX regime
  GET /fo/vix-regime  — India VIX volatility regime standalone

All arithmetic-only, computed from the Phase-0 recorders. Implied vol / Greeks
/ IV-rank (needing Black-Scholes) are NOT here — that is Rust, slice 4.2.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.fo import (
    BasisOut,
    ChainLegOut,
    ChainOut,
    FoAnalyticsOut,
    PcrOut,
    VixRegimeOut,
)
from app.services import fo_analytics as fa

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


@router.get("/chain", response_model=ChainOut)
async def get_chain(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: date = Query(...),
    source: str = Query("eod", pattern=_SOURCE),
    strikes: int = Query(0, ge=0, le=50, description="±N strikes around ATM; 0 = all"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ChainOut:
    sym = symbol.upper()
    rows = await fa.load_chain(db, sym, expiry, source=source)
    spot = await fa.latest_spot(db, sym, expiry)
    atm = fa.atm_strike(rows, spot) if spot is not None else None
    if strikes > 0 and spot is not None:
        rows = fa.near_atm(rows, spot, strikes)
    legs = [
        ChainLegOut(
            strike=r.strike, option_type=r.option_type, oi=r.oi, volume=r.volume, ltp=r.ltp
        )
        for r in sorted(rows, key=lambda r: (r.strike, r.option_type))
    ]
    return ChainOut(
        symbol=sym, expiry=expiry, source=source, spot=spot, atm_strike=atm, legs=legs
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
