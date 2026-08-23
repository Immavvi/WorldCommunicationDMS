from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.master_data_repository import MasterDataRepository
from app.schemas.master_data import (
    MasterDataListResponse,
    MasterDataResponse,
    MasterDataWrite,
    TermsVersionCreate,
    TermsVersionResponse,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.master_data_service import MasterDataService

router = APIRouter(prefix="/master-data", tags=["master-data"])
MasterManager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))
FINANCIAL_RESOURCES = {"bank-accounts", "gst-registrations", "tax-rate-sets"}


def ensure_write_access(resource: str, current_user: User) -> None:
    if resource in FINANCIAL_RESOURCES and not any(
        role.name == SUPER_ADMIN_ROLE for role in current_user.roles
    ):
        from app.core.errors import AppError

        raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")


def get_service(session: AsyncSession = Depends(get_db_session)) -> MasterDataService:
    return MasterDataService(MasterDataRepository(session))


@router.post(
    "/terms-condition-sets/{terms_set_id}/versions",
    response_model=TermsVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_terms_version(
    terms_set_id: UUID,
    payload: TermsVersionCreate,
    current_user: User = MasterManager,
    service: MasterDataService = Depends(get_service),
) -> TermsVersionResponse:
    version = await service.create_terms_version(
        terms_set_id, payload.content, payload.effective_from, current_user.id
    )
    return TermsVersionResponse.model_validate(version)


@router.get("/{resource}", response_model=MasterDataListResponse)
async def list_master_data(
    resource: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    active: bool | None = None,
    _: User = MasterManager,
    service: MasterDataService = Depends(get_service),
) -> MasterDataListResponse:
    items, total = await service.list(resource, offset, limit, active)
    return MasterDataListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/{resource}", response_model=MasterDataResponse, status_code=status.HTTP_201_CREATED)
async def create_master_data(
    resource: str,
    payload: MasterDataWrite,
    current_user: User = MasterManager,
    service: MasterDataService = Depends(get_service),
) -> MasterDataResponse:
    ensure_write_access(resource, current_user)
    return await service.create(resource, payload, current_user.id)


@router.patch("/{resource}/{record_id}", response_model=MasterDataResponse)
async def update_master_data(
    resource: str,
    record_id: UUID,
    payload: MasterDataWrite,
    current_user: User = MasterManager,
    service: MasterDataService = Depends(get_service),
) -> MasterDataResponse:
    ensure_write_access(resource, current_user)
    return await service.update(resource, record_id, payload, current_user.id)


@router.patch("/{resource}/{record_id}/active", response_model=MasterDataResponse)
async def set_master_data_active(
    resource: str,
    record_id: UUID,
    active: bool,
    current_user: User = MasterManager,
    service: MasterDataService = Depends(get_service),
) -> MasterDataResponse:
    ensure_write_access(resource, current_user)
    return await service.set_active(resource, record_id, active, current_user.id)
