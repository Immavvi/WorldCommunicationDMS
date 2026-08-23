from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.invoicing_repository import InvoicingRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.invoicing import (
    InvoiceablePosition,
    InvoiceAction,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceResponse,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.invoicing_service import InvoicingService

router = APIRouter(tags=["tax-invoices"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return InvoicingService(InvoicingRepository(session), ProcurementRepository(session))


@router.get("/tax-invoices", response_model=list[InvoiceResponse])
async def list_invoices(_: User = Manager, service: InvoicingService = Depends(get_service)):
    return await service.repository.list_invoices()


@router.post("/tax-invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate, user: User = Manager, service: InvoicingService = Depends(get_service)
):
    return await service.create(payload, user.id)


@router.get("/tax-invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID, _: User = Manager, service: InvoicingService = Depends(get_service)
):
    record = await service.repository.get_invoice(invoice_id)
    if record is None:
        raise AppError(404, "invoice_not_found", "Tax Invoice does not exist.")
    return record


@router.put("/tax-invoices/{invoice_id}/lines/{line_id}", response_model=InvoiceResponse)
async def update_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    payload: InvoiceLineCreate,
    user: User = Manager,
    service: InvoicingService = Depends(get_service),
):
    return await service.update_line(invoice_id, line_id, payload, user.id)


@router.post("/tax-invoices/{invoice_id}/actions", response_model=InvoiceResponse)
async def invoice_action(
    invoice_id: UUID,
    payload: InvoiceAction,
    user: User = Manager,
    service: InvoicingService = Depends(get_service),
):
    is_super_admin = any(role.name == SUPER_ADMIN_ROLE for role in user.roles)
    return await service.transition(
        invoice_id, payload.action, payload.reason, user.id, is_super_admin
    )


@router.get("/invoiceable-position", response_model=list[InvoiceablePosition])
async def invoiceable_position(
    project_id: UUID | None = Query(default=None),
    _: User = Manager,
    service: InvoicingService = Depends(get_service),
):
    return await service.invoiceable_position(project_id)
