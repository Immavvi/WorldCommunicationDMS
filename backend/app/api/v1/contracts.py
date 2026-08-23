from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.contract_repository import ContractRepository
from app.schemas.contracts import (
    ApprovedPositionResponse,
    LoaCreate,
    LoaItemCreate,
    LoaItemResponse,
    LoaResponse,
    LoaUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VariationAction,
    VariationCreate,
    VariationResponse,
)
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE
from app.services.contract_service import ContractService

router = APIRouter(tags=["contracts"])
ContractManager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


def get_service(session: AsyncSession = Depends(get_db_session)) -> ContractService:
    return ContractService(ContractRepository(session))


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    _: User = ContractManager, service: ContractService = Depends(get_service)
) -> list[ProjectResponse]:
    return [ProjectResponse.model_validate(item) for item in await service.list_projects()]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> ProjectResponse:
    return ProjectResponse.model_validate(await service.create_project(payload, user.id))


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await service.update_project(project_id, payload, user.id)
    )


@router.get("/loas", response_model=list[LoaResponse])
async def list_loas(
    project_id: UUID | None = Query(default=None),
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> list[LoaResponse]:
    return [LoaResponse.model_validate(item) for item in await service.list_loas(project_id)]


@router.post("/loas", response_model=LoaResponse, status_code=status.HTTP_201_CREATED)
async def create_loa(
    payload: LoaCreate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> LoaResponse:
    return LoaResponse.model_validate(await service.create_loa(payload, user.id))


@router.get("/loas/{loa_id}", response_model=LoaResponse)
async def get_loa(
    loa_id: UUID,
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> LoaResponse:
    return LoaResponse.model_validate(await service._loa(loa_id))


@router.patch("/loas/{loa_id}", response_model=LoaResponse)
async def update_loa(
    loa_id: UUID,
    payload: LoaUpdate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> LoaResponse:
    return LoaResponse.model_validate(await service.update_loa(loa_id, payload, user.id))


@router.get("/loas/{loa_id}/items", response_model=list[LoaItemResponse])
async def list_loa_items(
    loa_id: UUID,
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> list[LoaItemResponse]:
    await service._loa(loa_id)
    return [
        LoaItemResponse.model_validate(item) for item in await service.repository.list_items(loa_id)
    ]


@router.post(
    "/loas/{loa_id}/items", response_model=LoaItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_loa_item(
    loa_id: UUID,
    payload: LoaItemCreate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> LoaItemResponse:
    return LoaItemResponse.model_validate(await service.create_item(loa_id, payload, user.id))


@router.get("/loas/{loa_id}/variations", response_model=list[VariationResponse])
async def list_variations(
    loa_id: UUID,
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> list[VariationResponse]:
    await service._loa(loa_id)
    return [
        VariationResponse.model_validate(item)
        for item in await service.repository.list_variations(loa_id)
    ]


@router.post(
    "/loas/{loa_id}/variations",
    response_model=VariationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_variation(
    loa_id: UUID,
    payload: VariationCreate,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> VariationResponse:
    return VariationResponse.model_validate(
        await service.create_variation(loa_id, payload, user.id)
    )


@router.get("/variations/{variation_id}", response_model=VariationResponse)
async def get_variation(
    variation_id: UUID,
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> VariationResponse:
    return VariationResponse.model_validate(await service._variation(variation_id))


@router.post("/variations/{variation_id}/actions", response_model=VariationResponse)
async def transition_variation(
    variation_id: UUID,
    payload: VariationAction,
    user: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> VariationResponse:
    variation = await service.transition_variation(
        variation_id, payload.action, payload.reason, user.id
    )
    return VariationResponse.model_validate(variation)


@router.get("/loas/{loa_id}/approved-position", response_model=ApprovedPositionResponse)
async def approved_position(
    loa_id: UUID,
    _: User = ContractManager,
    service: ContractService = Depends(get_service),
) -> ApprovedPositionResponse:
    return await service.approved_position(loa_id)
