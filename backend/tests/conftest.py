import os

os.environ.setdefault(
    "WCDMS_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/wcdms_test"
)
os.environ.setdefault(
    "WCDMS_JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-validation"
)
