from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.contract_repository import ContractRepository
from app.repositories.dispatch_repository import DispatchRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.dispatch import (
    AcknowledgementCreate,
    ChallanAction,
    ChallanCreate,
    ChallanLineCreate,
    ChallanResponse,
    DispatchAvailability,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.contract_service import ContractService
from app.services.dispatch_service import DispatchService

router = APIRouter(tags=["dispatch"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)) -> DispatchService:
    dispatch_repository = DispatchRepository(session)
    procurement_repository = ProcurementRepository(session)
    return DispatchService(
        dispatch_repository,
        procurement_repository,
        ContractService(ContractRepository(session)),
    )


@router.get("/supply-challans", response_model=list[ChallanResponse])
async def list_challans(_: User = Manager, service: DispatchService = Depends(get_service)):
    return await service.repository.list_challans()


@router.post(
    "/supply-challans",
    response_model=ChallanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_challan(
    payload: ChallanCreate,
    user: User = Manager,
    service: DispatchService = Depends(get_service),
):
    return await service.create(payload, user.id)


@router.get("/supply-challans/{challan_id}", response_model=ChallanResponse)
async def get_challan(
    challan_id: UUID, _: User = Manager, service: DispatchService = Depends(get_service)
):
    record = await service.repository.get_challan(challan_id)
    if record is None:
        raise AppError(404, "challan_not_found", "Supply Challan does not exist.")
    return record


@router.post("/supply-challans/{challan_id}/actions", response_model=ChallanResponse)
async def challan_action(
    challan_id: UUID,
    payload: ChallanAction,
    user: User = Manager,
    service: DispatchService = Depends(get_service),
):
    is_super_admin = any(role.name == SUPER_ADMIN_ROLE for role in user.roles)
    return await service.transition(
        challan_id, payload.action, payload.reason, user.id, is_super_admin
    )


@router.put("/supply-challans/{challan_id}/lines/{line_id}", response_model=ChallanResponse)
async def update_challan_line(
    challan_id: UUID,
    line_id: UUID,
    payload: ChallanLineCreate,
    user: User = Manager,
    service: DispatchService = Depends(get_service),
):
    return await service.update_line(challan_id, line_id, payload, user.id)


@router.post("/supply-challans/{challan_id}/acknowledgement", response_model=ChallanResponse)
async def acknowledge_challan(
    challan_id: UUID,
    payload: AcknowledgementCreate,
    user: User = Manager,
    service: DispatchService = Depends(get_service),
):
    return await service.acknowledge(challan_id, payload, user.id)


@router.get("/dispatch-availability", response_model=list[DispatchAvailability])
async def dispatch_availability(
    project_id: UUID | None = Query(default=None),
    _: User = Manager,
    service: DispatchService = Depends(get_service),
):
    return await service.availability(project_id)
