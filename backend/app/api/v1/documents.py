from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.db.session import get_db_session
from app.document_engine.service import DocumentExportService
from app.models.auth import User
from app.services.bootstrap_service import ADMIN_ROLE, SUPER_ADMIN_ROLE

router = APIRouter(tags=["document-exports"])
Manager = Depends(require_roles(SUPER_ADMIN_ROLE, ADMIN_ROLE))


@router.get("/documents/{document_type}/{document_id}/{output_format}")
async def export_document(
    document_type: str,
    document_id: UUID,
    output_format: str,
    _: User = Manager,
    session: AsyncSession = Depends(get_db_session),
):
    content, media_type, filename = await DocumentExportService(session).export(
        document_type, document_id, output_format
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
