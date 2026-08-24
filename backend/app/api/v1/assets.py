from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.assets import (
    AssetAction,
    AssetInstallation,
    AssetRegistrationCreate,
    AssetRegistrationPosition,
    AssetResponse,
    ChallanAssetAssign,
    ReplacementCreate,
    WarrantyUpdate,
)
from app.services.asset_service import AssetService
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE

router = APIRouter(tags=["assets"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return AssetService(AssetRepository(session), ProcurementRepository(session))


@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(
    search: str | None = Query(default=None),
    asset_status: str | None = Query(default=None, alias="status"),
    product_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    warranty_from: date | None = Query(default=None),
    warranty_to: date | None = Query(default=None),
    _: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.repository.list(
        search=search,
        status=asset_status,
        product_id=product_id,
        project_id=project_id,
        warranty_from=warranty_from,
        warranty_to=warranty_to,
    )


@router.get("/assets/registration-position", response_model=list[AssetRegistrationPosition])
async def registration_positions(_: User = Manager, service: AssetService = Depends(get_service)):
    return await service.positions()


@router.post(
    "/assets/register", response_model=list[AssetResponse], status_code=status.HTTP_201_CREATED
)
async def register_assets(
    payload: AssetRegistrationCreate,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.register(payload, user.id)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID, _: User = Manager, service: AssetService = Depends(get_service)
):
    asset = await service.repository.get(asset_id)
    if not asset:
        raise AppError(404, "asset_not_found", "Asset does not exist.")
    return asset


@router.post("/assets/{asset_id}/actions", response_model=AssetResponse)
async def asset_action(
    asset_id: UUID,
    payload: AssetAction,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.action(
        asset_id,
        payload,
        user.id,
        any(role.name == SUPER_ADMIN_ROLE for role in user.roles),
    )


@router.post("/assets/{asset_id}/installation", response_model=AssetResponse)
async def install_asset(
    asset_id: UUID,
    payload: AssetInstallation,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.install(asset_id, payload, user.id)


@router.put("/assets/{asset_id}/warranty", response_model=AssetResponse)
async def update_warranty(
    asset_id: UUID,
    payload: WarrantyUpdate,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.warranty(asset_id, payload, user.id)


@router.post("/assets/{asset_id}/replacement", response_model=AssetResponse)
async def replace_asset(
    asset_id: UUID,
    payload: ReplacementCreate,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.replace(
        asset_id,
        payload,
        user.id,
        any(role.name == SUPER_ADMIN_ROLE for role in user.roles),
    )


@router.post("/supply-challan-lines/{line_id}/assets", response_model=list[AssetResponse])
async def assign_challan_assets(
    line_id: UUID,
    payload: ChallanAssetAssign,
    user: User = Manager,
    service: AssetService = Depends(get_service),
):
    return await service.assign_challan(line_id, payload, user.id)
