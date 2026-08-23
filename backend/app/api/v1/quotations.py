from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.procurement_repository import ProcurementRepository
from app.repositories.quotation_repository import QuotationRepository
from app.schemas.quotations import (
    QuotationAction,
    QuotationCreate,
    QuotationHeaderUpdate,
    QuotationLineInput,
    QuotationResponse,
    RevisionCreate,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.quotation_service import QuotationService

router = APIRouter(tags=["quotations"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)):
    return QuotationService(QuotationRepository(session), ProcurementRepository(session))


@router.get("/quotations", response_model=list[QuotationResponse])
async def list_quotations(_: User = Manager, service: QuotationService = Depends(get_service)):
    return await service.repository.list_quotations()


@router.post("/quotations", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
async def create_quotation(
    payload: QuotationCreate, user: User = Manager, service: QuotationService = Depends(get_service)
):
    return await service.create(payload, user.id)


@router.get("/quotations/{quotation_id}", response_model=QuotationResponse)
async def get_quotation(
    quotation_id: UUID, _: User = Manager, service: QuotationService = Depends(get_service)
):
    record = await service.repository.get_quotation(quotation_id)
    if not record:
        raise AppError(404, "quotation_not_found", "Quotation does not exist.")
    return record


@router.patch("/quotations/{quotation_id}", response_model=QuotationResponse)
async def update_header(
    quotation_id: UUID,
    payload: QuotationHeaderUpdate,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    return await service.update_header(quotation_id, payload, user.id)


@router.post("/quotations/{quotation_id}/lines", response_model=QuotationResponse)
async def add_line(
    quotation_id: UUID,
    payload: QuotationLineInput,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    return await service.add_line(quotation_id, payload, user.id)


@router.put("/quotations/{quotation_id}/lines/{line_id}", response_model=QuotationResponse)
async def update_line(
    quotation_id: UUID,
    line_id: UUID,
    payload: QuotationLineInput,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    return await service.update_line(quotation_id, line_id, payload, user.id)


@router.delete("/quotations/{quotation_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line(
    quotation_id: UUID,
    line_id: UUID,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    await service.delete_line(quotation_id, line_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/quotations/{quotation_id}/actions", response_model=QuotationResponse)
async def quotation_action(
    quotation_id: UUID,
    payload: QuotationAction,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    return await service.transition(
        quotation_id,
        payload.action,
        payload.reason,
        user.id,
        any(role.name == SUPER_ADMIN_ROLE for role in user.roles),
    )


@router.post(
    "/quotations/{quotation_id}/revisions",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision(
    quotation_id: UUID,
    payload: RevisionCreate,
    user: User = Manager,
    service: QuotationService = Depends(get_service),
):
    return await service.create_revision(quotation_id, payload.reason, user.id)


@router.get("/quotations/{quotation_id}/revisions", response_model=list[QuotationResponse])
async def revision_history(
    quotation_id: UUID, _: User = Manager, service: QuotationService = Depends(get_service)
):
    record = await service.repository.get_quotation(quotation_id)
    if not record:
        raise AppError(404, "quotation_not_found", "Quotation does not exist.")
    return await service.repository.revision_history(record.quotation_number)
