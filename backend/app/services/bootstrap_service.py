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

    async def create_initial_super_admin(
        self, email: str, password: str, display_name: str | None = None
    ) -> User:
        # The role row serializes concurrent bootstrap attempts on PostgreSQL.
        role = await self.repository.lock_role_by_name(SUPER_ADMIN_ROLE)
        if role is None:
            raise AppError(500, "role_not_initialized", "SUPER-ADMIN role is not available.")
        if await self.repository.count_users():
            raise AppError(
                409, "bootstrap_unavailable", "Initial user bootstrap has already completed."
            )
        user = User(
            email=email.lower(),
            display_name=display_name.strip() if display_name else None,
            password_hash=hash_password(password),
            roles=[role],
            must_change_password=False,
        )
        await self.repository.create(user)
        await self.repository.add_audit_log(
            actor_user_id=None,
            action="bootstrap_super_admin",
            entity_id=user.id,
            new_value={"email": user.email, "roles": [SUPER_ADMIN_ROLE], "is_active": True},
        )
        return user
