from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.procurement_repository import ProcurementRepository
from app.repositories.receiving_repository import ReceivingRepository
from app.schemas.receiving import (
    PoReceiptPositionLine,
    ReceiptAction,
    ReceiptCreate,
    ReceiptLineCreate,
    ReceiptResponse,
    ReceiptUpdate,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.receiving_service import ReceivingService

router = APIRouter(tags=["receiving"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return ReceivingService(ReceivingRepository(session), ProcurementRepository(session))


@router.get("/material-receipts", response_model=list[ReceiptResponse])
async def list_receipts(
    po_id: UUID | None = Query(default=None),
    _: User = Manager,
    service: ReceivingService = Depends(get_service),
):
    return await service.repository.list_receipts(po_id)


@router.post(
    "/material-receipts", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED
)
async def create_receipt(
    payload: ReceiptCreate, user: User = Manager, service: ReceivingService = Depends(get_service)
):
    return await service.create_receipt(payload, user.id)


@router.get("/material-receipts/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: UUID, _: User = Manager, service: ReceivingService = Depends(get_service)
):
    record = await service.repository.get_receipt(receipt_id)
    if record is None:
        raise AppError(404, "receipt_not_found", "Material receipt does not exist.")
    return record


@router.patch("/material-receipts/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(
    receipt_id: UUID,
    payload: ReceiptUpdate,
    user: User = Manager,
    service: ReceivingService = Depends(get_service),
):
    return await service.update_receipt(receipt_id, payload, user.id)


@router.put("/material-receipts/{receipt_id}/lines/{line_id}", response_model=ReceiptResponse)
async def update_receipt_line(
    receipt_id: UUID,
    line_id: UUID,
    payload: ReceiptLineCreate,
    user: User = Manager,
    service: ReceivingService = Depends(get_service),
):
    return await service.update_line(receipt_id, line_id, payload, user.id)


@router.post("/material-receipts/{receipt_id}/actions", response_model=ReceiptResponse)
async def receipt_action(
    receipt_id: UUID,
    payload: ReceiptAction,
    user: User = Manager,
    service: ReceivingService = Depends(get_service),
):
    is_super_admin = any(role.name == SUPER_ADMIN_ROLE for role in user.roles)
    return await service.transition(
        receipt_id, payload.action, payload.reason, user.id, is_super_admin
    )


@router.get("/purchase-orders/{po_id}/receipt-position", response_model=list[PoReceiptPositionLine])
async def po_receipt_position(
    po_id: UUID, _: User = Manager, service: ReceivingService = Depends(get_service)
):
    return await service.po_position(po_id)
