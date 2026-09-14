"""Signal endpoints — Phase 5/6 (offline signal engine + event guard).

GET  /signals/active          — list active signals, sortable by confidence
GET  /signals/{id}            — full detail including factor breakdown
POST /signals/generate        — (admin) trigger generation for a stock
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.paper_broker import get_live_ltp, get_live_ltps, simulate_fill
from app.core.config import settings
from app.core.deps import get_current_user as get_current_active_user
from app.core.deps import get_db, require_admin
from app.core.ratios import MAX_RR, safe_ratio
from app.models.signal import Signal, SignalOutcome
from app.models.stock import Stock
from app.models.user import User
from app.schemas.signal import (
    ConfidenceBreakdownOut,
    FactorAbstentionOut,
    FactorContributionOut,
    FunnelOut,
    SignalListResponse,
    SignalOut,
    SignalOutcomeOut,
)
from app.services.funnel import load_funnel
from app.signals import confidence_explain, eligibility
from app.signals.event_guard import is_signal_suppressed
from app.trading.atr import atr_timeframe_for, latest_atr
from app.trading.regime import CHOPPY_ER, er_by_stock

log = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


class GenerateRequest(BaseModel):
    stock_id: int
    timeframe: str = "1d"
    capital: Decimal = Decimal("500000")
    # risk_pct is a WHOLE percent (2.0 = 2%) — compute_quantity divides by
    # 100 itself. The old 0.02 default undersized every manual signal 100×;
    # the floor rejects fractional-style values loudly instead of sizing
    # them silently wrong.
    risk_pct: Decimal = Field(
        default=Decimal("2.0"), ge=Decimal("0.1"), le=Decimal("10")
    )


async def _enrich(signal: Signal, db: AsyncSession) -> SignalOut:
    """Attach stock symbol to a signal."""
    stock = await db.get(Stock, signal.stock_id)
    out = SignalOut.model_validate(signal)
    out.symbol = stock.symbol if stock else ""
    return out


def _confidence_breakdown(factor_scores: object) -> ConfidenceBreakdownOut | None:
    """Map the read-only confluence reconstruction (U10/U15/U17) to its response schema.

    Detail endpoint only. Fail-open: a malformed `factor_scores` yields None (the card is
    omitted), never a 500 — matching this path's fail-open philosophy."""
    b = confidence_explain.explain(factor_scores)
    if b is None:
        return None
    return ConfidenceBreakdownOut(
        numerator=b.numerator,
        denominator=b.denominator,
        normalized=b.normalized,
        confidence_pct=b.confidence_pct,
        direction=b.direction,
        scoring=[
            FactorContributionOut(
                name=c.name, weight=c.weight, score=c.score,
                contribution=c.contribution, explanation=c.explanation,
            )
            for c in b.scoring
        ],
        abstained=[
            FactorAbstentionOut(name=a.name, weight=a.weight, explanation=a.explanation)
            for a in b.abstained
        ],
    )


def _apply_eligibility(
    out: SignalOut,
    signal: Signal,
    atr: Decimal | None,
    market_price: Decimal | None = None,
    *,
    allow_offmarket: bool = True,
) -> bool:
    """Stamp the order-eligibility preview onto a response row.

    Single code path for BOTH the list and the detail endpoint: AlertBell reads
    `GET /signals/{id}`, and that is exactly where the user was clicking Buy and
    collecting 409 toasts, so a preview on the list alone would have fixed half the
    problem. `atr=None` (the list) leaves the sl_atr check unassessed; the detail
    endpoint loads a real ATR because one signal can afford one query.

    Returns True when an ACTIVE gate could NOT be assessed (also logged at WARNING), so a
    caller can summarise once per page instead of once per row."""
    # The broker checks its POST-SLIPPAGE fill, so the preview must too: comparing a raw
    # LTP disagreed with the order path in both directions inside a half-spread/half-tick
    # band (quant-verifier, 2026-09-02). `simulate_fill` with depth=None is pure, so this
    # is safe on a list path.
    fill = (
        simulate_fill(market_price, "BUY" if signal.direction != "SELL" else "SELL").fill
        if market_price is not None
        else None
    )
    verdict = eligibility.preview(
        signal,
        modes=eligibility.gate_modes(),
        atr=atr,
        market_price=market_price,
        fill_price=fill,
        allow_offmarket=allow_offmarket,
        max_chase_r=Decimal(str(settings.chase_max_r)),
        rr_min=Decimal(str(settings.rr_min)),
        min_scoring_factors=settings.entry_min_scoring_factors,
        max_dominant_share=Decimal(str(settings.entry_max_dominant_factor_share)),
        min_sl_atr_mult=Decimal(str(settings.entry_min_sl_atr_mult)),
    )
    out.blocked = verdict.blocked
    out.blocked_by = verdict.gate
    out.block_reason = verdict.reason
    out.unassessed = list(verdict.unassessed)
    if verdict.unassessed:
        # An ACTIVE gate this preview could not judge: the row is reported as eligible
        # while the order path may still reject it — precisely the drift this module
        # exists to prevent. Make it LOUD instead of leaving the tripwire only in the
        # test suite (the 6.8.6 principle: the silent failure mode IS the bug).
        log.warning(
            "eligibility preview incomplete for signal %s: ACTIVE gate(s) %s not assessed "
            "on this path — extend app/signals/eligibility (see its module docstring)",
            signal.id,
            ", ".join(verdict.unassessed),
        )
    return bool(verdict.unassessed)


_NEAR_EXPIRY_FRAC = 0.8  # ≥80% of the validity window elapsed = stale / little runway


def _near_expiry(sig: Signal, now: datetime) -> bool:
    span = (sig.validity_until - sig.created_at).total_seconds()
    if span <= 0:
        return False
    return (now - sig.created_at).total_seconds() / span >= _NEAR_EXPIRY_FRAC


def _reward_risk(sig: Signal) -> float:
    """Planned reward:risk, as a DEDUP TIEBREAKER — so it must return a number, not
    the honest `None`. A zero-risk signal sorts last (0.0), and the ratio is clamped
    at MAX_RR (H6) so a near-zero stop cannot manufacture an `RR≈228` that outranks
    a genuine signal: the artifact ties at the cap and `created_at` decides."""
    # Decimal(str(...)) — robust whether the ORM attr is a Decimal (fresh load)
    # or a str (unrefreshed in-session), matching the project's money pattern.
    entry = Decimal(str(sig.entry_price))
    rr = safe_ratio(
        abs(Decimal(str(sig.take_profit)) - entry),
        abs(entry - Decimal(str(sig.stop_loss))),
        cap=MAX_RR,
    )
    return float(rr) if rr is not None else 0.0


async def _enrich_page(
    db: AsyncSession,
    page: list[tuple[Signal, int]],
    *,
    now: datetime,
    er_map: dict[int, float | None],
    ltps: dict[int, Decimal],
    choppy: Callable[[Signal], bool],
    allow_offmarket: bool,
) -> tuple[list[SignalOut], bool]:
    """Build the response rows for one page. Returns (rows, any_partially_assessed).

    Extracted from the endpoint to keep it under the complexity gate, and because the
    per-row work has one non-obvious rule worth isolating: the eligibility preview is
    contained per row. A single malformed `factor_scores` payload used to raise and take
    all 200 rows down with it (bug-hunter, 2026-09-02) — on a read path whose whole
    philosophy is fail-open, one bad row must degrade to "unknown", not a 500.
    """
    rows: list[SignalOut] = []
    incomplete = False
    for s, n in page:
        out = await _enrich(s, db)
        out.sources_count = n
        out.near_expiry = _near_expiry(s, now)
        out.days_valid_remaining = max(0.0, (s.validity_until - now).total_seconds() / 86_400)
        out.regime_er = er_map.get(s.stock_id)
        out.choppy = choppy(s)
        # No per-row I/O: the ATR is not loaded here (so an ACTIVE sl_atr gate is
        # reported unassessed rather than passed), and the live price came from one
        # batched MGET. The detail endpoint loads both for real.
        try:
            incomplete = (
                _apply_eligibility(
                    out, s, None, ltps.get(s.stock_id), allow_offmarket=allow_offmarket
                )
                or incomplete
            )
        except Exception:
            log.exception("eligibility preview failed for signal %s; failing open", s.id)
            incomplete = True
        rows.append(out)
    return rows, incomplete


@router.get("/active", response_model=SignalListResponse)
async def list_active_signals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    direction: str | None = Query(default=None, description="BUY | SELL"),
    classification: str | None = Query(default=None),
    min_confidence: int = Query(default=70, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SignalListResponse:
    """Active signals — presentation overlay applied (engine unchanged): the
    base engine and named profiles can each emit a signal for the same stock;
    they are DEDUPED to one row per (stock, direction) and ranked by confidence.

    ⭐ **Nothing is hidden.** Until B1 (2026-09-11) this endpoint dropped near-expiry and
    choppy-regime signals by default — two undeclared eligibility rules the ORDER path did
    not apply, so a hidden signal would have been accepted by `place_order`. The choppy
    half was measured at **t = −0.00, p = 0.999** on 185 trades while hiding **67%** of the
    list, so both were removed rather than declared. Both states still ride on every row
    (`near_expiry`, `choppy`, `regime_er`) for the UI to flag and sort on.

    Each row also carries an ORDER-ELIGIBILITY PREVIEW (`blocked`/`blocked_by`/
    `block_reason`): what the ACTIVE eligibility gates would do to it at order time.
    Before 2026-09-02 this endpoint ran none of those gates, so a suppressed signal
    rendered with a Buy button guaranteed to 409 (41 of 204 rows that day). Blocked
    rows are still RETURNED, flagged — never silently hidden, so what the gates are
    doing stays visible. See app/signals/eligibility."""
    now = datetime.now(tz=UTC)
    q = (
        select(Signal)
        .where(Signal.status == "active", Signal.validity_until > now)
        .where(Signal.confidence_pct >= min_confidence)
    )
    if direction:
        q = q.where(Signal.direction == direction.upper())
    if classification:
        q = q.where(Signal.classification == classification.lower())

    all_sigs = (await db.execute(q)).scalars().all()

    # Dedup by (stock, direction, classification): the base engine and named
    # profiles emit near-identical signals for the same setup. Keep the best
    # representative; remember how many collapsed so the UI can badge it. Keying
    # on classification too means a legitimate swing + scalp on one stock is NOT
    # merged (different trade types, different horizons).
    groups: dict[tuple[int, str, str], list[Signal]] = {}
    for s in all_sigs:
        groups.setdefault((s.stock_id, s.direction, s.classification), []).append(s)
    reps: list[tuple[Signal, int]] = []
    for grp in groups.values():
        best = max(grp, key=lambda s: (s.confidence_pct, _reward_risk(s), s.created_at))
        reps.append((best, len(grp)))

    # Regime ER per stock (current daily tape) — choppy = below the threshold.
    er_map = await er_by_stock(db, [s.stock_id for s, _ in reps], now)

    def _choppy(s: Signal) -> bool:
        er = er_map.get(s.stock_id)
        return er is not None and er < CHOPPY_ER

    # ⛔ B1 (2026-09-11): the near-expiry and choppy filters USED to run here, both
    # defaulting ON, and they were removed rather than declared.
    #
    # They were two undeclared eligibility rules: absent from `restrictions.py` — the
    # registry whose docstring calls itself the single source of truth for tradability —
    # absent from the order path, and absent from the research corpus. A signal they hid
    # would have been ACCEPTED by `place_order`. That is display/order drift in the
    # OPPOSITE direction from the one fixed on 2026-09-02 (display too permissive, 41 of
    # 204 rows showing a Buy button that could only 409); this one was display too
    # RESTRICTIVE, and it silently narrowed the offered set along two axes nobody had
    # accounted for in any estimand.
    #
    # ⭐ And the choppy half was MEASURED before it was removed, which is why this is a
    # deletion and not a declaration: on 185 resolved trades, splitting at the deployed
    # ER < 0.30 threshold gives a contrast of −0.0001R, **t = −0.00, p = 0.999** — as close
    # to a perfect null as this programme has produced — while hiding **67%** of the
    # offered set. On the clean tradeable cell its sign is wrong (the HIDDEN cohort reads
    # +0.18R better, not significant). It was selecting nothing and costing two-thirds of
    # the list.
    #
    # ⚠ NOTHING IS LOST BY REMOVING THEM. `near_expiry` and `choppy` are still computed
    # and still ride on every row (`_enrich_page`), so the UI can flag, sort and style on
    # both. That is this project's standing law — **flag, never hide** — the same one that
    # keeps eligibility-blocked rows listed with a disabled Buy instead of dropping them.
    reps.sort(key=lambda t: (t[0].confidence_pct, t[0].created_at), reverse=True)
    total = len(reps)
    page = reps[offset : offset + limit]

    # One Redis MGET for the whole page — `get_live_ltp` opens a connection per call, so
    # it must never be used in this loop (bug-hunter, 2026-09-02). Absent price ⇒ the
    # through-stop check is reported unassessed, not silently passed.
    ltps = await get_live_ltps([s.stock_id for s, _ in page])

    enriched, incomplete = await _enrich_page(
        db,
        page,
        now=now,
        er_map=er_map,
        ltps=ltps,
        choppy=_choppy,
        allow_offmarket=bool(user.allow_offmarket_entry),
    )
    if incomplete:
        log.warning(
            "signals/active returned %d row(s) whose ACTIVE-gate eligibility is only "
            "PARTIALLY assessed — the list may offer a Buy the order path will reject",
            len(enriched),
        )
    return SignalListResponse(total=total, signals=enriched)


@router.get("/funnel", response_model=FunnelOut)
async def signal_funnel(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> FunnelOut:
    """V1 — the scope a scan covered: known → in universe → priced today → live signals.

    ⭐ Exists so an empty state can say what it LOOKED AT. An empty state has no stock in
    context and therefore cannot name a per-stock cause; stating the scope is the honest
    alternative to "nothing meets the confluence gate right now".

    ⭐⭐ And it doubles as a breadth detector: `priced_today` against `breadth_median`
    surfaces a coverage collapse, which the 6.8.6 feed alarm cannot see because it
    asserts RECENCY. The defect that caused the universe rebuild would have shown here.

    ⚠ Declared BEFORE `/{signal_id}`: FastAPI matches in declaration order, so a dynamic
    segment declared first would swallow `/funnel` as a signal id.
    """
    f = await load_funnel(db)
    return FunnelOut(
        known=f.known,
        in_universe=f.in_universe,
        priced_today=f.priced_today,
        signals_live=f.signals_live,
        session=f.session,
        breadth_median=f.breadth_median,
        breadth_shortfall_pct=f.breadth_shortfall_pct,
        assessed_available=f.assessed_available,
    )


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(
    signal_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> SignalOut:
    signal = await db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    out = await _enrich(signal, db)
    # U10/U15/U17 — reconstruct the confluence arithmetic for the detail card (detail only).
    # Set BEFORE the non-active early return so a superseded/expired signal still explains itself.
    out.confidence_breakdown = _confidence_breakdown(signal.factor_scores)
    # One signal, so one ATR query is affordable — this path's preview covers every
    # gate the preview module can judge, sl_atr included. AlertBell reads this endpoint.
    atr = await latest_atr(
        db,
        signal.stock_id,
        timeframe=atr_timeframe_for(signal.classification),
        before=signal.created_at,
    )
    # Unlike the list, this endpoint can serve a NON-ACTIVE signal, and the order path
    # rejects those outright — so preview it with the order path's own sentence
    # (quant-verifier, 2026-09-02). AlertBell reads this endpoint.
    if signal.status != "active":
        out.blocked = True
        out.blocked_by = "status"
        out.block_reason = f"Signal is {signal.status}, not active"
        return out
    try:
        _apply_eligibility(
            out,
            signal,
            atr,
            await get_live_ltp(signal.stock_id),
            allow_offmarket=bool(user.allow_offmarket_entry),
        )
    except Exception:  # noqa: BLE001 — a PREVIEW must never 500 a detail read either
        log.exception("eligibility preview failed for signal %s; failing open", signal.id)
    return out


@router.get("/{signal_id}/outcome", response_model=SignalOutcomeOut)
async def get_signal_outcome(
    signal_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> SignalOutcomeOut:
    """Tick-level outcome record (slice 3.6): first entry/SL/TP touches
    inside validity + the status ladder. 404 while no alert has touched
    the signal AND it hasn't expired (the row is written lazily)."""
    outcome = await db.get(SignalOutcome, signal_id)
    if not outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outcome recorded yet for this signal",
        )
    return SignalOutcomeOut.model_validate(outcome)


@router.post("/generate", response_model=SignalOut, status_code=status.HTTP_201_CREATED)
async def generate_signal(
    req: GenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SignalOut:
    """Admin-only: run the signal engine for one stock, respecting the event guard."""
    stock = await db.get(Stock, req.stock_id)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    guard = await is_signal_suppressed(db, req.stock_id)
    if guard.suppressed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Signal suppressed by event guard: {guard.reason}",
        )

    from zoneinfo import ZoneInfo

    from app.services.fii_dii_service import (
        get_market_flow_5d,
        get_stock_block_deal_net_cr,
    )
    from app.services.signal_service import generate_signal_for_stock

    as_of = datetime.now(tz=UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
    fii_net_5d, dii_net_5d = await get_market_flow_5d(db, as_of)
    block_net_cr = await get_stock_block_deal_net_cr(db, req.stock_id, as_of)

    signal = await generate_signal_for_stock(
        db=db,
        stock=stock,
        capital=req.capital,
        risk_pct=req.risk_pct,
        timeframe=req.timeframe,
        fii_net_5d=fii_net_5d,
        dii_net_5d=dii_net_5d,
        stock_block_deal_net_cr=block_net_cr,
    )
    if signal is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confidence below threshold or insufficient data",
        )

    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return await _enrich(signal, db)
