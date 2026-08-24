import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.core.security import verify_password
from app.db.base import Base
from app.models.auth import AuditLog, Role
from app.services.bootstrap_service import BootstrapService


@pytest.mark.asyncio
async def test_initial_super_admin_bootstrap_is_secure_audited_and_one_time(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with session_factory.begin() as session:
            session.add_all([Role(name="SUPER-ADMIN"), Role(name="ADMIN")])

        async with session_factory.begin() as session:
            user = await BootstrapService(session).create_initial_super_admin(
                "Owner@Example.com", "operator-entered-password", "System Owner"
            )
            assert user.email == "owner@example.com"
            assert user.display_name == "System Owner"
            assert user.must_change_password is False
            assert user.password_hash != "operator-entered-password"
            assert verify_password("operator-entered-password", user.password_hash)

        async with session_factory() as session:
            audit = await session.scalar(
                select(AuditLog).where(AuditLog.action == "bootstrap_super_admin")
            )
            assert audit is not None
            assert audit.actor_user_id is None
            assert "password" not in str(audit.new_value).lower()

        async with session_factory.begin() as session:
            with pytest.raises(AppError) as error:
                await BootstrapService(session).create_initial_super_admin(
                    "another@example.com", "another-password"
                )
            assert error.value.code == "bootstrap_unavailable"
    finally:
        await engine.dispose()
