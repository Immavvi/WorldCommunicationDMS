from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog, Role, User

USER_WITH_ROLES = selectinload(User.roles).selectinload(Role.permissions)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_users(self) -> int:
        return (await self.session.scalar(select(func.count()).select_from(User))) or 0

    async def get_role_by_name(self, name: str) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.name == name))

    async def lock_role_by_name(self, name: str) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.name == name).with_for_update())

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.scalar(
            select(User).options(USER_WITH_ROLES).where(User.id == user_id)
        )

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).options(USER_WITH_ROLES).where(func.lower(User.email) == email.lower())
        )

    async def list(self, offset: int, limit: int) -> list[User]:
        result = await self.session.scalars(
            select(User).options(USER_WITH_ROLES).order_by(User.email).offset(offset).limit(limit)
        )
        return list(result.unique())

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def lock_active_super_admins(self) -> list[User]:
        result = await self.session.scalars(
            select(User)
            .join(User.roles)
            .where(User.is_active.is_(True), Role.name == "SUPER-ADMIN")
            .with_for_update()
        )
        return list(result.unique())

    async def add_audit_log(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        entity_id: UUID,
        old_value: dict | None = None,
        new_value: dict | None = None,
        reason: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type="user",
                entity_id=str(entity_id),
                old_value=old_value,
                new_value=new_value,
                reason=reason,
            )
        )
