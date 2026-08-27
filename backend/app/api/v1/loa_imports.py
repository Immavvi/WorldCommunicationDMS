from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.loa_import_repository import RailwayLoaImportRepository
from app.schemas.loa_imports import (
    LoaImportApproval,
    LoaImportResponse,
    LoaImportReview,
    RailwayCustomerMapping,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.loa_import_service import RailwayLoaImportService

router = APIRouter(prefix="/railway-loa-imports", tags=["railway-loa-imports"])
ImportManager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)) -> RailwayLoaImportService:
    return RailwayLoaImportService(RailwayLoaImportRepository(session), get_settings())


@router.post("", response_model=LoaImportResponse, status_code=status.HTTP_201_CREATED)
async def upload_railway_loa(
    file: UploadFile = File(...),
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.upload(file, user.id))


@router.get("", response_model=list[LoaImportResponse])
async def list_railway_loa_imports(
    _: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> list[LoaImportResponse]:
    return [LoaImportResponse.model_validate(item) for item in await service.list()]


@router.get("/{import_id}", response_model=LoaImportResponse)
async def get_railway_loa_import(
    import_id: UUID,
    _: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.get(import_id))


@router.patch("/{import_id}", response_model=LoaImportResponse)
async def review_railway_loa_import(
    import_id: UUID,
    payload: LoaImportReview,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.review(import_id, payload, user.id))


@router.post("/{import_id}/retry", response_model=LoaImportResponse)
async def retry_railway_loa_extraction(
    import_id: UUID,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.retry(import_id, user.id))


@router.post("/{import_id}/resolve-masters", response_model=LoaImportResponse)
async def resolve_railway_loa_masters(
    import_id: UUID,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.resolve_masters(import_id, user.id))


@router.post("/{import_id}/customer-mapping", response_model=LoaImportResponse)
async def map_railway_customer(
    import_id: UUID,
    payload: RailwayCustomerMapping,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(
        await service.map_customer(import_id, payload.customer_party_id, user.id)
    )


@router.post("/{import_id}/approve", response_model=LoaImportResponse)
async def approve_railway_loa_import(
    import_id: UUID,
    payload: LoaImportApproval,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.approve(import_id, payload, user.id))


@router.post("/{import_id}/cancel", response_model=LoaImportResponse)
async def cancel_railway_loa_import(
    import_id: UUID,
    user: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> LoaImportResponse:
    return LoaImportResponse.model_validate(await service.cancel(import_id, user.id))


@router.get("/{import_id}/original")
async def view_original_railway_loa(
    import_id: UUID,
    _: User = ImportManager,
    service: RailwayLoaImportService = Depends(get_service),
) -> FileResponse:
    record = await service.get(import_id)
    disposition = "inline" if record.extension == "pdf" else "attachment"
    return FileResponse(
        service.file_path(record),
        media_type=record.mime_type,
        filename=record.original_filename,
        content_disposition_type=disposition,
    )
