from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.master_data import Party, TermsConditionVersion


class MasterDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, model, *, offset: int, limit: int, active: bool | None):
        statement = select(model).order_by(model.created_at.desc()).offset(offset).limit(limit)
        if model is Party:
            statement = statement.options(selectinload(Party.roles))
        if active is not None:
            statement = statement.where(model.is_active == active)
        return list(await self.session.scalars(statement))

    async def count(self, model, *, active: bool | None) -> int:
        statement = select(func.count()).select_from(model)
        if active is not None:
            statement = statement.where(model.is_active == active)
        return (await self.session.scalar(statement)) or 0

    async def get(self, model, record_id: UUID):
        statement = select(model).where(model.id == record_id)
        if model is Party:
            statement = statement.options(selectinload(Party.roles))
        return await self.session.scalar(statement)

    async def find_by_code(self, model, code: str):
        if not hasattr(model, "code"):
            return None
        return await self.session.scalar(
            select(model).where(func.lower(model.code) == code.lower())
        )

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        mapped_names = {attribute.key for attribute in record.__mapper__.column_attrs}
        timestamp_names = [name for name in ("created_at", "updated_at") if name in mapped_names]
        await self.session.refresh(record, attribute_names=timestamp_names)
        return record

    def audit(
        self,
        *,
        actor_user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                old_value=jsonable_encoder(old_value),
                new_value=jsonable_encoder(new_value),
            )
        )

    async def list_terms_versions(self, terms_set_id: UUID) -> list[TermsConditionVersion]:
        return list(
            await self.session.scalars(
                select(TermsConditionVersion)
                .where(TermsConditionVersion.terms_set_id == terms_set_id)
                .order_by(TermsConditionVersion.version.desc())
            )
        )
