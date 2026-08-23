from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.auth import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AccessTokenResponse, ChangePasswordRequest, LoginRequest, UserResponse
from app.services.auth_service import AuthenticationService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> AccessTokenResponse:
    user, token = await AuthenticationService(UserRepository(session)).authenticate(
        str(payload.email), payload.password
    )
    return AccessTokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await UserService(UserRepository(session)).change_password(
        current_user, payload.current_password, payload.new_password
    )
