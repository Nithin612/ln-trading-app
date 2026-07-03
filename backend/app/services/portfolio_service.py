"""Portfolio service — Phase 11.

Provides:
  - import_cas_pdf: parse + persist CAS upload
  - get_net_worth: aggregate equity + MF + manual assets
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import ManualAsset, MfHolding, MfImportBatch
from app.models.trading import Position
from app.schemas.portfolio import (
    AssetBreakdownItem,
    EquitySummary,
    ManualSummary,
    MfSummary,
    NetWorthOut,
)
from app.services.cas_parser import CASHolding, parse_cas_pdf


# ── CAS import ─────────────────────────────────────────────────────────────────

async def import_cas_pdf(
    db: AsyncSession,
    user_id: int,
    pdf_bytes: bytes,
    source_filename: str,
) -> MfImportBatch:
    """Parse PDF, persist batch + holdings, return the batch."""
    header, holdings = parse_cas_pdf(pdf_bytes)

    total_value = Decimal("0")
    for h in holdings:
        try:
            total_value += Decimal(h.current_value)
        except Exception:
            pass

    batch = MfImportBatch(
        user_id=user_id,
        statement_date=header.statement_date,
        investor_name=header.investor_name,
        pan=header.pan,
        source_filename=source_filename,
        total_holdings=len(holdings),
        total_value=total_value,
    )
    db.add(batch)
    await db.flush()  # get batch.id

    for h in holdings:
        try:
            nav_val = Decimal(h.nav)
            units_val = Decimal(h.units)
            value_val = Decimal(h.current_value)
        except Exception:
            continue

        holding = MfHolding(
            batch_id=batch.id,
            user_id=user_id,
            amc_name=h.amc_name,
            scheme_name=h.scheme_name,
            folio_number=h.folio_number,
            isin=h.isin,
            units=units_val,
            nav=nav_val,
            current_value=value_val,
            as_of_date=h.as_of_date,
        )
        db.add(holding)

    await db.commit()
    await db.refresh(batch)
    return batch


async def get_batch_with_holdings(
    db: AsyncSession, batch_id: str, user_id: int
) -> MfImportBatch | None:
    result = await db.execute(
        select(MfImportBatch)
        .options(selectinload(MfImportBatch.holdings))
        .where(MfImportBatch.id == batch_id, MfImportBatch.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── Net-worth aggregation ──────────────────────────────────────────────────────

async def get_net_worth(db: AsyncSession, user_id: int) -> NetWorthOut:
    equity = await _equity_summary(db, user_id)
    mf = await _mf_summary(db, user_id)
    manual = await _manual_summary(db, user_id)

    total = equity.current_value + mf.current_value + manual.current_value

    return NetWorthOut(
        equity=equity,
        mutual_funds=mf,
        manual_assets=manual,
        total_net_worth=total,
        as_of=datetime.now(tz=UTC),
    )


async def _equity_summary(db: AsyncSession, user_id: int) -> EquitySummary:
    """Sum open positions: unrealized P&L, cost basis, current value."""
    result = await db.execute(
        select(
            func.count(Position.id).label("cnt"),
            func.coalesce(func.sum(Position.avg_entry_price * Position.quantity), 0).label("cost"),
            func.coalesce(func.sum(Position.unrealized_pnl), 0).label("upnl"),
        ).where(Position.user_id == user_id, Position.closed_at.is_(None))
    )
    row = result.one()
    cost = Decimal(str(row.cost))
    upnl = Decimal(str(row.upnl))
    return EquitySummary(
        current_value=cost + upnl,
        cost_basis=cost,
        unrealized_pnl=upnl,
        position_count=row.cnt,
    )


async def _mf_summary(db: AsyncSession, user_id: int) -> MfSummary:
    """Latest batch's total value + count, or zeros if no import."""
    batch_result = await db.execute(
        select(MfImportBatch)
        .where(MfImportBatch.user_id == user_id)
        .order_by(MfImportBatch.created_at.desc())
        .limit(1)
    )
    latest = batch_result.scalar_one_or_none()
    if not latest:
        return MfSummary(current_value=Decimal("0"), holding_count=0, last_imported=None)

    return MfSummary(
        current_value=latest.total_value,
        holding_count=latest.total_holdings,
        last_imported=latest.created_at,
    )


async def _manual_summary(db: AsyncSession, user_id: int) -> ManualSummary:
    result = await db.execute(
        select(
            ManualAsset.asset_type,
            func.count(ManualAsset.id).label("cnt"),
            func.coalesce(func.sum(ManualAsset.current_value), 0).label("total"),
        )
        .where(ManualAsset.user_id == user_id)
        .group_by(ManualAsset.asset_type)
    )
    rows = result.all()

    _TYPE_LABELS = {
        "gold": "Gold",
        "fd": "Fixed Deposits",
        "ppf": "PPF",
        "nps": "NPS",
        "bonds": "Bonds",
        "real_estate": "Real Estate",
        "other": "Other",
    }

    breakdown: list[AssetBreakdownItem] = []
    grand_total = Decimal("0")
    total_count = 0
    for row in rows:
        val = Decimal(str(row.total))
        grand_total += val
        total_count += row.cnt
        breakdown.append(
            AssetBreakdownItem(
                asset_type=row.asset_type,
                label=_TYPE_LABELS.get(row.asset_type, row.asset_type.title()),
                total_value=val,
                count=row.cnt,
            )
        )

    # Sort by value descending
    breakdown.sort(key=lambda x: x.total_value, reverse=True)

    return ManualSummary(
        current_value=grand_total,
        count=total_count,
        breakdown=breakdown,
    )
