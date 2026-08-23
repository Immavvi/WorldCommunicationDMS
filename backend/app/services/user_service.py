from uuid import UUID

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models.auth import User
from app.repositories.user_repository import UserRepository
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE

ALLOWED_ROLE_NAMES = frozenset({SUPER_ADMIN_ROLE, ADMIN_ROLE})


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def list_users(self, offset: int, limit: int) -> list[User]:
        return await self.repository.list(offset, limit)

    async def get_user(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise AppError(404, "user_not_found", "The requested user does not exist.")
        return user

    async def create_user(self, email: str, password: str, role_name: str, actor_id: UUID) -> User:
        normalized_email = email.lower()
        if await self.repository.get_by_email(normalized_email):
            raise AppError(409, "user_exists", "A user with this email already exists.")
        role = await self._get_assignable_role(role_name)
        user = await self.repository.create(
            User(email=normalized_email, password_hash=hash_password(password), roles=[role])
        )
        await self.repository.add_audit_log(
            actor_user_id=actor_id,
            action="create",
            entity_id=user.id,
            new_value={"email": user.email, "roles": [role.name], "is_active": user.is_active},
        )
        return user

    async def set_active(self, user_id: UUID, is_active: bool, actor_id: UUID) -> User:
        user = await self.get_user(user_id)
        old_value = {"is_active": user.is_active}
        user.is_active = is_active
        await self.repository.add_audit_log(
            actor_user_id=actor_id,
            action="activate" if is_active else "deactivate",
            entity_id=user.id,
            old_value=old_value,
            new_value={"is_active": is_active},
        )
        return user

    async def assign_role(self, user_id: UUID, role_name: str, actor_id: UUID) -> User:
        user = await self.get_user(user_id)
        role = await self._get_assignable_role(role_name)
        old_roles = [existing_role.name for existing_role in user.roles]
        user.roles = [role]
        await self.repository.add_audit_log(
            actor_user_id=actor_id,
            action="assign_role",
            entity_id=user.id,
            old_value={"roles": old_roles},
            new_value={"roles": [role.name]},
        )
        return user

    async def reset_password(self, user_id: UUID, password: str, actor_id: UUID) -> User:
        user = await self.get_user(user_id)
        user.password_hash = hash_password(password)
        user.token_version += 1
        await self.repository.add_audit_log(
            actor_user_id=actor_id,
            action="reset_password",
            entity_id=user.id,
            new_value={"token_version": user.token_version},
        )
        return user

    async def change_password(self, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise AppError(400, "invalid_current_password", "The current password is incorrect.")
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        await self.repository.add_audit_log(
            actor_user_id=user.id,
            action="change_password",
            entity_id=user.id,
            new_value={"token_version": user.token_version},
        )
        return user

    async def _get_assignable_role(self, role_name: str):
        if role_name not in ALLOWED_ROLE_NAMES:
            raise AppError(422, "invalid_role", "The supplied role is not available.")
        role = await self.repository.get_role_by_name(role_name)
        if role is None:
            raise AppError(500, "role_not_initialized", "The requested role is not available.")
        return role
