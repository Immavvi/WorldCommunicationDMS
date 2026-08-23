from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.billing_repository import BillingRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.billing import BillablePosition, PiAction, PiCreate, PiLineCreate, PiResponse
from app.services.billing_service import BillingService
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE

router = APIRouter(tags=["proforma-invoices"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return BillingService(BillingRepository(session), ProcurementRepository(session))


@router.get("/proforma-invoices", response_model=list[PiResponse])
async def list_pis(_: User = Manager, service: BillingService = Depends(get_service)):
    return await service.repository.list_pis()


@router.post("/proforma-invoices", response_model=PiResponse, status_code=status.HTTP_201_CREATED)
async def create_pi(
    payload: PiCreate, user: User = Manager, service: BillingService = Depends(get_service)
):
    return await service.create(payload, user.id)


@router.get("/proforma-invoices/{pi_id}", response_model=PiResponse)
async def get_pi(pi_id: UUID, _: User = Manager, service: BillingService = Depends(get_service)):
    record = await service.repository.get_pi(pi_id)
    if record is None:
        raise AppError(404, "pi_not_found", "Proforma Invoice does not exist.")
    return record


@router.post("/proforma-invoices/{pi_id}/actions", response_model=PiResponse)
async def pi_action(
    pi_id: UUID,
    payload: PiAction,
    user: User = Manager,
    service: BillingService = Depends(get_service),
):
    is_super_admin = any(role.name == SUPER_ADMIN_ROLE for role in user.roles)
    return await service.transition(pi_id, payload.action, payload.reason, user.id, is_super_admin)


@router.put("/proforma-invoices/{pi_id}/lines/{line_id}", response_model=PiResponse)
async def update_pi_line(
    pi_id: UUID,
    line_id: UUID,
    payload: PiLineCreate,
    user: User = Manager,
    service: BillingService = Depends(get_service),
):
    return await service.update_line(pi_id, line_id, payload, user.id)


@router.get("/billable-position", response_model=list[BillablePosition])
async def billable_position(
    project_id: UUID | None = Query(default=None),
    _: User = Manager,
    service: BillingService = Depends(get_service),
):
    return await service.billable_position(project_id)
