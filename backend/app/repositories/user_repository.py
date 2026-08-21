from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_users(self) -> int:
        return (await self.session.scalar(select(func.count()).select_from(User))) or 0

    async def get_role_by_name(self, name: str) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.name == name))

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
