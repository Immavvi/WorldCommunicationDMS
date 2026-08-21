from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.dependencies import get_current_user, require_roles
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.session import engine


def test_database_configuration_initializes_an_async_engine() -> None:
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


def test_authentication_foundation_loads_and_handles_passwords_and_tokens() -> None:
    password_hash = hash_password("test-password")
    assert verify_password("test-password", password_hash)
    token = create_access_token("00000000-0000-0000-0000-000000000001")
    assert decode_access_token(token)["sub"] == "00000000-0000-0000-0000-000000000001"
    assert callable(get_current_user)
    assert callable(require_roles("SUPER-ADMIN"))
