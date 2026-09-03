"""Per-style suggestions API (Phase 2 slice 7).

GET /suggestions/{style} — active profile-tagged suggestions for one of the
four trading styles, with factor breakdown and setup evidence.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.paper_broker import get_live_ltps, simulate_fill
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.profile import StrategyProfile
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.user import User
from app.schemas.profile import PROFILE_STYLES
from app.signals import eligibility

log = logging.getLogger(__name__)

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionOut(BaseModel):
    id: str
    symbol: str
    direction: str
    classification: str
    timeframe: str
    entry_price: str
    stop_loss: str
    take_profit: str
    suggested_qty: int
    confidence_pct: int
    headline: str
    factor_scores: dict[str, Any]
    setup_trigger: dict[str, Any] | None
    volatility_reduced: bool | None
    profile_key: str
    profile_name: str
    profile_version: int
    style: str
    validity_until: datetime
    created_at: datetime
    # Order-eligibility preview — the FIFTH Buy surface. `StylePage` posts these ids
    # straight into the paper order path (`placeOrder({signal_id: s.id})`), so without
    # these fields a gate-blocked style suggestion still offered a guaranteed-409 click
    # (quant-verifier, 2026-09-02). Same contract as `SignalOut`.
    blocked: bool = False
    blocked_by: str | None = None
    block_reason: str | None = None
    unassessed: list[str] = []


class SuggestionListResponse(BaseModel):
    style: str
    total: int
    suggestions: list[SuggestionOut]


@router.get("/{style}", response_model=SuggestionListResponse)
async def list_suggestions(
    style: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    profile: str | None = Query(default=None, description="Filter to one profile key"),
    min_confidence: int = Query(default=70, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuggestionListResponse:
    if style not in PROFILE_STYLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown style {style!r} — one of {', '.join(PROFILE_STYLES)}",
        )

    now = datetime.now(tz=UTC)
    q = (
        select(Signal, StrategyProfile, Stock.symbol)
        .join(StrategyProfile, Signal.profile_id == StrategyProfile.id)
        .join(Stock, Stock.id == Signal.stock_id)
        .where(
            StrategyProfile.style == style,
            Signal.status == "active",
            Signal.validity_until > now,
            Signal.confidence_pct >= min_confidence,
        )
    )
    if profile:
        q = q.where(Signal.profile_key == profile)
    q = q.order_by(Signal.confidence_pct.desc(), Signal.created_at.desc())

    rows = (await db.execute(q)).all()
    total = len(rows)
    page = rows[offset : offset + limit]

    # One batched Redis MGET for the page (never `get_live_ltp` per row), then the same
    # eligibility preview the signals endpoints use — one source of truth, so this
    # surface cannot drift from the others.
    ltps = await get_live_ltps([sig.stock_id for sig, _p, _s in page])
    allow_offmarket = bool(user.allow_offmarket_entry)

    def _elig(sig: Signal) -> eligibility.EligibilityPreview:
        px = ltps.get(sig.stock_id)
        fill = (
            simulate_fill(px, "BUY" if sig.direction != "SELL" else "SELL").fill
            if px is not None
            else None
        )
        try:
            return eligibility.preview(
                sig,
                modes=eligibility.gate_modes(),
                atr=None,
                market_price=px,
                fill_price=fill,
                allow_offmarket=allow_offmarket,
                max_chase_r=Decimal(str(settings.chase_max_r)),
        rr_min=Decimal(str(settings.rr_min)),
                min_scoring_factors=settings.entry_min_scoring_factors,
                max_dominant_share=Decimal(str(settings.entry_max_dominant_factor_share)),
                min_sl_atr_mult=Decimal(str(settings.entry_min_sl_atr_mult)),
            )
        except Exception:  # noqa: BLE001 — a preview must never 500 the page
            log.exception("eligibility preview failed for signal %s; failing open", sig.id)
            return eligibility.CLEAR

    verdicts = {sig.id: _elig(sig) for sig, _p, _s in page}

    return SuggestionListResponse(
        style=style,
        total=total,
        suggestions=[
            SuggestionOut(
                blocked=verdicts[sig.id].blocked,
                blocked_by=verdicts[sig.id].gate,
                block_reason=verdicts[sig.id].reason,
                unassessed=list(verdicts[sig.id].unassessed),
                id=sig.id,
                symbol=symbol,
                direction=sig.direction,
                classification=sig.classification,
                timeframe=sig.timeframe,
                entry_price=str(sig.entry_price),
                stop_loss=str(sig.stop_loss),
                take_profit=str(sig.take_profit),
                suggested_qty=sig.suggested_qty,
                confidence_pct=sig.confidence_pct,
                headline=sig.headline,
                factor_scores=sig.factor_scores,
                setup_trigger=sig.setup_trigger,
                volatility_reduced=sig.volatility_reduced,
                profile_key=prof.key,
                profile_name=prof.name,
                profile_version=prof.version,
                style=prof.style,
                validity_until=sig.validity_until,
                created_at=sig.created_at,
            )
            for sig, prof, symbol in page
        ],
    )
