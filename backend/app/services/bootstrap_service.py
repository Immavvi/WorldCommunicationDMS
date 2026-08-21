from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.models.auth import User
from app.repositories.user_repository import UserRepository

SUPER_ADMIN_ROLE = "SUPER-ADMIN"
ADMIN_ROLE = "ADMIN"


class BootstrapService:
    """Creates the first privileged user exactly once, through an operator-run command."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def create_initial_super_admin(self, email: str, password: str) -> User:
        if await self.repository.count_users():
            raise AppError(
                409, "bootstrap_unavailable", "Initial user bootstrap has already completed."
            )
        role = await self.repository.get_role_by_name(SUPER_ADMIN_ROLE)
        if role is None:
            raise AppError(500, "role_not_initialized", "SUPER-ADMIN role is not available.")
        user = User(email=email.lower(), password_hash=hash_password(password), roles=[role])
        return await self.repository.create(user)
