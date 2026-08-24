from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.auth import User
from app.models.procurement import NumberingSeries
from app.services.bootstrap_service import SUPER_ADMIN_ROLE

router = APIRouter(prefix="/admin", tags=["administration"])
Super = Depends(require_roles(SUPER_ADMIN_ROLE))


@router.get("/numbering")
async def numbering(_: User = Super, session: AsyncSession = Depends(get_db_session)):
    rows = await session.scalars(select(NumberingSeries).order_by(NumberingSeries.document_type))
    return [
        {
            "id": r.id,
            "document_type": r.document_type,
            "prefix": r.prefix,
            "next_number": r.next_number,
            "padding": r.padding,
            "preview": f"{r.prefix}{r.next_number:0{r.padding}d}",
        }
        for r in rows
    ]


@router.get("/system-status")
async def system_status(_: User = Super, session: AsyncSession = Depends(get_db_session)):
    settings = get_settings()
    await session.execute(text("SELECT 1"))
    revision = (
        (await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1")))
        if session.bind and session.bind.dialect.name == "postgresql"
        else "test-schema"
    )
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "connected",
        "schema_revision": revision,
    }
