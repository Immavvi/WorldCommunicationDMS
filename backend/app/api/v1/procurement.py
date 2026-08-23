from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.contract_repository import ContractRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.procurement import (
    CommitmentResponse,
    PoLineCreate,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    RequirementCreate,
    RequirementResponse,
    RequirementUpdate,
    WorkflowAction,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.contract_service import ContractService
from app.services.procurement_service import ProcurementService

router = APIRouter(tags=["procurement"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)) -> ProcurementService:
    return ProcurementService(
        ProcurementRepository(session), ContractService(ContractRepository(session))
    )


@router.get("/procurement-requirements", response_model=list[RequirementResponse])
async def list_requirements(_: User = Manager, service: ProcurementService = Depends(get_service)):
    return await service.repository.list_requirements()


@router.post(
    "/procurement-requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    payload: RequirementCreate,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    return await service.create_requirement(payload, user.id)


@router.get("/procurement-requirements/{record_id}", response_model=RequirementResponse)
async def get_requirement(
    record_id: UUID, _: User = Manager, service: ProcurementService = Depends(get_service)
):
    record = await service.repository.get_requirement(record_id)
    if record is None:
        raise AppError(404, "requirement_not_found", "Procurement requirement does not exist.")
    return record


@router.patch("/procurement-requirements/{record_id}", response_model=RequirementResponse)
async def update_requirement(
    record_id: UUID,
    payload: RequirementUpdate,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    return await service.update_requirement(record_id, payload, user.id)


@router.post("/procurement-requirements/{record_id}/actions", response_model=RequirementResponse)
async def requirement_action(
    record_id: UUID,
    payload: WorkflowAction,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    return await service.transition_requirement(record_id, payload.action, payload.reason, user.id)


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    _: User = Manager, service: ProcurementService = Depends(get_service)
):
    return await service.repository.list_pos()


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    return await service.create_po(payload, user.id)


@router.get("/purchase-orders/{record_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    record_id: UUID, _: User = Manager, service: ProcurementService = Depends(get_service)
):
    record = await service.repository.get_po(record_id)
    if record is None:
        raise AppError(404, "purchase_order_not_found", "Purchase order does not exist.")
    return record


@router.put("/purchase-orders/{record_id}/lines/{line_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order_line(
    record_id: UUID,
    line_id: UUID,
    payload: PoLineCreate,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    return await service.update_po_line(record_id, line_id, payload, user.id)


@router.post("/purchase-orders/{record_id}/actions", response_model=PurchaseOrderResponse)
async def purchase_order_action(
    record_id: UUID,
    payload: WorkflowAction,
    user: User = Manager,
    service: ProcurementService = Depends(get_service),
):
    is_super_admin = any(role.name == SUPER_ADMIN_ROLE for role in user.roles)
    return await service.transition_po(
        record_id, payload.action, payload.reason, user.id, is_super_admin
    )


@router.get("/loas/{loa_id}/procurement-commitments", response_model=list[CommitmentResponse])
async def contract_commitments(
    loa_id: UUID, _: User = Manager, service: ProcurementService = Depends(get_service)
):
    return await service.commitments(loa_id)
