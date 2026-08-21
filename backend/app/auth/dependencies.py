from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.auth import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise AppError(401, "authentication_required", "A bearer token is required.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AppError(401, "invalid_token", "The access token is invalid or expired.") from exc

    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "The token does not identify an active user.")
    return user


def require_roles(*allowed_roles: str):
    async def role_guard(current_user: User = Depends(get_current_user)) -> User:
        if not {role.name for role in current_user.roles}.intersection(allowed_roles):
            raise AppError(
                403,
                "authorization_denied",
                "The current role is not allowed to perform this action.",
            )
        return current_user

    return role_guard
