import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "WCDMS_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/wcdms_test"
)
os.environ.setdefault(
    "WCDMS_JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-validation"
)

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.auth import Role, User
from app.models.procurement import NumberingSeries


@pytest_asyncio.fixture
async def client(tmp_path) -> AsyncGenerator[AsyncClient]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'wcdms-test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory.begin() as session:
        super_admin_role = Role(name="SUPER-ADMIN")
        admin_role = Role(name="ADMIN")
        session.add_all(
            [
                super_admin_role,
                admin_role,
                User(
                    email="superadmin@example.com",
                    password_hash=hash_password("super-admin-password"),
                    roles=[super_admin_role],
                ),
                NumberingSeries(
                    document_type="PROCUREMENT_REQUIREMENT", prefix="PR-", next_number=1, padding=6
                ),
                NumberingSeries(
                    document_type="PURCHASE_ORDER", prefix="PO-", next_number=1, padding=6
                ),
                NumberingSeries(
                    document_type="MATERIAL_RECEIPT", prefix="GRN-", next_number=1, padding=6
                ),
                NumberingSeries(
                    document_type="SUPPLY_CHALLAN", prefix="CH-", next_number=1, padding=6
                ),
                User(
                    email="admin@example.com",
                    password_hash=hash_password("admin-user-password"),
                    roles=[admin_role],
                ),
            ]
        )

    async def get_test_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = get_test_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        test_client._session_factory = session_factory
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()
