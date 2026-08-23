from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.users import (
    AssignRoleRequest,
    CreateUserRequest,
    ResetPasswordRequest,
    SetUserActiveRequest,
    UserListResponse,
)
from app.services.bootstrap_service import SUPER_ADMIN_ROLE
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
SuperAdmin = Depends(require_roles(SUPER_ADMIN_ROLE))


def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(UserRepository(session))


@router.get("", response_model=UserListResponse)
async def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> UserListResponse:
    users = await service.list_users(offset, limit)
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users], offset=offset, limit=limit
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    return UserResponse.model_validate(await service.get_user(user_id))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    current_user: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.create_user(
        str(payload.email), payload.password, payload.role_name, current_user.id
    )
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/active", response_model=UserResponse)
async def set_user_active(
    user_id: UUID,
    payload: SetUserActiveRequest,
    current_user: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.set_active(user_id, payload.is_active, current_user.id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}/role", response_model=UserResponse)
async def assign_user_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    current_user: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.assign_role(user_id, payload.role_name, current_user.id)
    return UserResponse.model_validate(user)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: UUID,
    payload: ResetPasswordRequest,
    current_user: User = SuperAdmin,
    service: UserService = Depends(get_user_service),
) -> None:
    await service.reset_password(user_id, payload.new_password, current_user.id)
