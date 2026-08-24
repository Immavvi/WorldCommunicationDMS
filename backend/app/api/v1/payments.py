from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.payment_repository import PaymentRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.payments import (
    AllocationCreate,
    EligibleInvoice,
    InvoicePaymentHistory,
    PaymentAction,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    ReceivablePosition,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.payment_service import PaymentService

router = APIRouter(tags=["payments"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return PaymentService(PaymentRepository(session), ProcurementRepository(session))


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    customer_id: UUID | None = Query(default=None),
    payment_status: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Manager,
    service: PaymentService = Depends(get_service),
):
    payments = await service.repository.list(
        customer_id=customer_id, status=payment_status, offset=offset, limit=limit
    )
    return [await service.response(payment.id) for payment in payments]


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    user: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.create(payload, user.id)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID, _: User = Manager, service: PaymentService = Depends(get_service)
):
    return await service.response(payment_id)


@router.patch("/payments/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: UUID,
    payload: PaymentUpdate,
    user: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.update(payment_id, payload, user.id)


@router.post("/payments/{payment_id}/allocations", response_model=PaymentResponse)
async def allocate_payment(
    payment_id: UUID,
    payload: AllocationCreate,
    user: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.allocate(payment_id, payload, user.id)


@router.delete("/payments/{payment_id}/allocations/{allocation_id}", response_model=PaymentResponse)
async def remove_allocation(
    payment_id: UUID,
    allocation_id: UUID,
    user: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.remove_allocation(payment_id, allocation_id, user.id)


@router.get("/payments/{payment_id}/eligible-invoices", response_model=list[EligibleInvoice])
async def eligible_invoices(
    payment_id: UUID, _: User = Manager, service: PaymentService = Depends(get_service)
):
    return await service.eligible(payment_id)


@router.post("/payments/{payment_id}/actions", response_model=PaymentResponse)
async def payment_action(
    payment_id: UUID,
    payload: PaymentAction,
    user: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.action(
        payment_id,
        payload,
        user.id,
        any(role.name == SUPER_ADMIN_ROLE for role in user.roles),
    )


@router.get("/receivables", response_model=list[ReceivablePosition])
async def list_receivables(
    customer_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    loa_id: UUID | None = Query(default=None),
    railway_division_id: UUID | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    _: User = Manager,
    service: PaymentService = Depends(get_service),
):
    return await service.receivables(
        customer_id=customer_id,
        project_id=project_id,
        loa_id=loa_id,
        railway_division_id=railway_division_id,
        payment_status=payment_status,
        overdue=overdue,
    )


@router.get("/receivables/{invoice_id}", response_model=ReceivablePosition)
async def get_receivable(
    invoice_id: UUID, _: User = Manager, service: PaymentService = Depends(get_service)
):
    rows = await service.receivables(invoice_id=invoice_id)
    if not rows:
        from app.core.errors import AppError

        raise AppError(404, "receivable_not_found", "Issued Tax Invoice does not exist.")
    return rows[0]


@router.get("/tax-invoices/{invoice_id}/payments", response_model=list[InvoicePaymentHistory])
async def invoice_payment_history(
    invoice_id: UUID, _: User = Manager, service: PaymentService = Depends(get_service)
):
    return await service.invoice_history(invoice_id)
