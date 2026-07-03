"""Portfolio API — Phase 11.

Endpoints:
  POST   /portfolio/cas/upload            Upload CAS PDF; parse + store
  GET    /portfolio/cas/batches           List import batches (summary)
  GET    /portfolio/cas/batches/{id}      Batch detail with holdings
  DELETE /portfolio/cas/batches/{id}      Delete batch + its holdings

  POST   /portfolio/assets                Create manual asset
  GET    /portfolio/assets                List manual assets
  PUT    /portfolio/assets/{id}           Update manual asset
  DELETE /portfolio/assets/{id}           Delete manual asset

  GET    /portfolio/net-worth             Consolidated net-worth summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.portfolio import ManualAsset, MfImportBatch
from app.models.user import User
from app.schemas.portfolio import (
    ManualAssetCreate,
    ManualAssetOut,
    ManualAssetUpdate,
    MfImportBatchDetail,
    MfImportBatchOut,
    NetWorthOut,
)
from app.services.portfolio_service import (
    get_batch_with_holdings,
    get_net_worth,
    import_cas_pdf,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB


# ── CAS upload ─────────────────────────────────────────────────────────────────

@router.post(
    "/cas/upload",
    response_model=MfImportBatchOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CAMS CAS PDF",
)
async def upload_cas(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MfImportBatchOut:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds 20 MB limit",
        )

    filename = file.filename or "cas_upload.pdf"
    batch = await import_cas_pdf(db, current_user.id, pdf_bytes, filename)
    return MfImportBatchOut.model_validate(batch)


@router.get(
    "/cas/batches",
    response_model=list[MfImportBatchOut],
    summary="List CAS import batches",
)
async def list_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MfImportBatchOut]:
    result = await db.execute(
        select(MfImportBatch)
        .where(MfImportBatch.user_id == current_user.id)
        .order_by(MfImportBatch.created_at.desc())
    )
    batches = result.scalars().all()
    return [MfImportBatchOut.model_validate(b) for b in batches]


@router.get(
    "/cas/batches/{batch_id}",
    response_model=MfImportBatchDetail,
    summary="Get batch with holdings",
)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MfImportBatchDetail:
    batch = await get_batch_with_holdings(db, batch_id, current_user.id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return MfImportBatchDetail.model_validate(batch)


@router.delete(
    "/cas/batches/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete import batch",
)
async def delete_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(MfImportBatch).where(
            MfImportBatch.id == batch_id, MfImportBatch.user_id == current_user.id
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    await db.delete(batch)
    await db.commit()


# ── Manual assets ──────────────────────────────────────────────────────────────

@router.post(
    "/assets",
    response_model=ManualAssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create manual asset",
)
async def create_asset(
    payload: ManualAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ManualAssetOut:
    asset = ManualAsset(user_id=current_user.id, **payload.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return ManualAssetOut.model_validate(asset)


@router.get(
    "/assets",
    response_model=list[ManualAssetOut],
    summary="List manual assets",
)
async def list_assets(
    asset_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ManualAssetOut]:
    q = select(ManualAsset).where(ManualAsset.user_id == current_user.id)
    if asset_type:
        q = q.where(ManualAsset.asset_type == asset_type)
    q = q.order_by(ManualAsset.created_at.desc())
    result = await db.execute(q)
    return [ManualAssetOut.model_validate(a) for a in result.scalars().all()]


@router.put(
    "/assets/{asset_id}",
    response_model=ManualAssetOut,
    summary="Update manual asset",
)
async def update_asset(
    asset_id: str,
    payload: ManualAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ManualAssetOut:
    result = await db.execute(
        select(ManualAsset).where(
            ManualAsset.id == asset_id, ManualAsset.user_id == current_user.id
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)

    await db.commit()
    await db.refresh(asset)
    return ManualAssetOut.model_validate(asset)


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete manual asset",
)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(ManualAsset).where(
            ManualAsset.id == asset_id, ManualAsset.user_id == current_user.id
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    await db.delete(asset)
    await db.commit()


# ── Net worth ──────────────────────────────────────────────────────────────────

@router.get(
    "/net-worth",
    response_model=NetWorthOut,
    summary="Consolidated net-worth across equity + MF + manual assets",
)
async def net_worth(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetWorthOut:
    return await get_net_worth(db, current_user.id)
