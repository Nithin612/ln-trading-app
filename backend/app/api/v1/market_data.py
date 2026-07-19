"""
Phase 4 market-data endpoints:
  GET  /stocks/{stock_id}/ohlcv              — OHLCV bars for candlestick chart
  GET  /market/fii-dii                       — FII/DII daily flows
  GET  /market/bulk-block-deals              — bulk/block deals list
  GET  /market/provisional/{style}           — provisional leaderboard snapshot
  POST /market/ingest/bhavcopy               — admin: trigger bhavcopy ingestion
  POST /market/ingest/fii-dii                — admin: pull FII/DII from NSE
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.provisional import ALL_PROVISIONAL_STYLES, LEADERBOARD_KEY
from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.market_data import (
    BackfillRequest,
    BulkBlockDealRead,
    BulkBlockDealsResponse,
    FiiDiiResponse,
    FiiDiiRow,
    IngestionResult,
    OhlcvBar,
    OhlcvResponse,
    ProvisionalLeaderboardOut,
)
from app.services.bhavcopy_service import ingest_bhavcopy_date
from app.services.fii_dii_service import fetch_fii_dii_data, upsert_fii_dii

log = logging.getLogger(__name__)

router = APIRouter(tags=["market-data"])

_MAX_BARS = 1500  # ~6 years of daily bars


# ── OHLCV ─────────────────────────────────────────────────────────────────────

@router.get("/stocks/{stock_id}/ohlcv", response_model=OhlcvResponse)
async def get_ohlcv(
    stock_id: int,
    from_date: date | None = Query(None, description="Start date inclusive (default: 1yr ago)"),
    to_date: date | None = Query(None, description="End date inclusive (default: today)"),
    limit: int = Query(365, ge=1, le=_MAX_BARS),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OhlcvResponse:
    if to_date is None:
        to_date = date.today()
    if from_date is None:
        from_date = to_date - timedelta(days=365)

    from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=UTC)
    to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=UTC)

    rows = await db.execute(
        text(
            "SELECT time, open, high, low, close, volume "
            "FROM ohlcv_1d "
            "WHERE stock_id = :sid AND time >= :from_t AND time <= :to_t "
            "ORDER BY time ASC "
            "LIMIT :lim"
        ),
        {"sid": stock_id, "from_t": from_dt, "to_t": to_dt, "lim": limit},
    )

    bars = [
        OhlcvBar(
            time=row.time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    ]

    return OhlcvResponse(stock_id=stock_id, timeframe="1d", bars=bars)


# ── FII / DII ─────────────────────────────────────────────────────────────────

@router.get("/market/fii-dii", response_model=FiiDiiResponse)
async def get_fii_dii(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    investor_type: str | None = Query(None, pattern="^(FII|DII)$"),
    segment: str | None = Query(None, pattern="^(cash|futures|options)$"),
    limit: int = Query(90, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FiiDiiResponse:
    if to_date is None:
        to_date = date.today()
    if from_date is None:
        from_date = to_date - timedelta(days=90)

    filters = ["trade_date >= :from_d", "trade_date <= :to_d"]
    params: dict[str, object] = {"from_d": from_date, "to_d": to_date, "lim": limit}

    if investor_type:
        filters.append("investor_type = :itype")
        params["itype"] = investor_type
    if segment:
        filters.append("segment = :seg")
        params["seg"] = segment

    where = " AND ".join(filters)
    result = await db.execute(
        text(
            f"SELECT trade_date, investor_type, segment, buy_value_cr, sell_value_cr "
            f"FROM fii_dii_daily WHERE {where} "
            f"ORDER BY trade_date DESC, investor_type, segment "
            f"LIMIT :lim"
        ),
        params,
    )

    rows = [
        FiiDiiRow(
            trade_date=row.trade_date,
            investor_type=row.investor_type,
            segment=row.segment,
            buy_value_cr=row.buy_value_cr,
            sell_value_cr=row.sell_value_cr,
            net_value_cr=row.buy_value_cr - row.sell_value_cr,
        )
        for row in result
    ]

    return FiiDiiResponse(rows=rows, total=len(rows))


# ── Bulk / Block deals ────────────────────────────────────────────────────────

@router.get("/market/bulk-block-deals", response_model=BulkBlockDealsResponse)
async def get_bulk_block_deals(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    stock_id: int | None = Query(None),
    deal_type: str | None = Query(None, pattern="^(bulk|block)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BulkBlockDealsResponse:
    if to_date is None:
        to_date = date.today()
    if from_date is None:
        from_date = to_date - timedelta(days=30)

    filters = ["d.trade_date >= :from_d", "d.trade_date <= :to_d"]
    params: dict[str, object] = {"from_d": from_date, "to_d": to_date, "lim": limit}

    if stock_id:
        filters.append("d.stock_id = :sid")
        params["sid"] = stock_id
    if deal_type:
        filters.append("d.deal_type = :dt")
        params["dt"] = deal_type

    where = " AND ".join(filters)
    result = await db.execute(
        text(
            f"SELECT d.id, d.trade_date, d.stock_id, s.symbol, "
            f"  d.deal_type, d.client_name, d.transaction, "
            f"  d.quantity, d.price, d.source, "
            f"  ROUND(d.quantity * d.price / 10000000, 2) AS value_cr "
            f"FROM bulk_block_deals d "
            f"JOIN stocks s ON s.id = d.stock_id "
            f"WHERE {where} "
            f"ORDER BY d.trade_date DESC "
            f"LIMIT :lim"
        ),
        params,
    )

    items = [
        BulkBlockDealRead(
            id=row.id,
            trade_date=row.trade_date,
            stock_id=row.stock_id,
            symbol=row.symbol,
            deal_type=row.deal_type,
            client_name=row.client_name,
            transaction=row.transaction,
            quantity=row.quantity,
            price=row.price,
            value_cr=row.value_cr,
            source=row.source,
        )
        for row in result
    ]

    return BulkBlockDealsResponse(items=items, total=len(items))


# ── Provisional leaderboards (3.5-deferred) ───────────────────────────────────

@router.get("/market/provisional/{style}", response_model=ProvisionalLeaderboardOut)
async def get_provisional_leaderboard(
    style: str,
    _: User = Depends(get_current_user),
) -> ProvisionalLeaderboardOut:
    """Latest provisional leaderboard snapshot for one style — the
    reconciliation path for the at-most-once WS fan-out (late joiners,
    reconnects). Every style publishes every cycle: empty rows with a
    fresh as_of = genuinely nothing passes the gate; a MISSING key
    (as_of null here) = worker down / outside session. Both are empty
    states, never errors."""
    if style not in ALL_PROVISIONAL_STYLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown style; known: {', '.join(ALL_PROVISIONAL_STYLES)}",
        )
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = await r.get(LEADERBOARD_KEY.format(style=style))
    finally:
        await r.aclose()
    if raw is None:
        return ProvisionalLeaderboardOut(style=style)
    try:
        return ProvisionalLeaderboardOut(**json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        log.exception("provisional leaderboard key unparsable (style=%s)", style)
        return ProvisionalLeaderboardOut(style=style)


# ── Admin ingestion triggers ──────────────────────────────────────────────────

@router.post(
    "/market/ingest/bhavcopy",
    response_model=IngestionResult,
    status_code=status.HTTP_200_OK,
)
async def trigger_bhavcopy(
    trade_date: date | None = Query(None, description="Date to ingest; defaults to today"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> IngestionResult:
    target = trade_date or date.today()
    return await ingest_bhavcopy_date(db, target)


@router.post(
    "/market/ingest/bhavcopy/backfill",
    response_model=list[IngestionResult],
    status_code=status.HTTP_200_OK,
)
async def trigger_bhavcopy_backfill(
    req: BackfillRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[IngestionResult]:
    if req.from_date > req.to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be before to_date",
        )
    max_days = 365 * 6
    if (req.to_date - req.from_date).days > max_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Backfill range exceeds {max_days} days",
        )

    results: list[IngestionResult] = []
    current = req.from_date
    while current <= req.to_date:
        if current.weekday() < 5:  # skip weekends
            result = await ingest_bhavcopy_date(db, current)
            results.append(result)
        current += timedelta(days=1)

    return results


@router.post(
    "/market/ingest/fii-dii",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def trigger_fii_dii(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, object]:
    records = await fetch_fii_dii_data()
    inserted, skipped = await upsert_fii_dii(db, records)
    return {"status": "ok", "inserted": inserted, "skipped": skipped}
