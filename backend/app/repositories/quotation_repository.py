from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.master_data import GstRegistration, Party, RailwayAuthority, TermsConditionVersion
from app.models.quotations import Quotation


class QuotationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, model, record_id: UUID):
        statement = select(model).where(model.id == record_id)
        if model is Party:
            statement = statement.options(selectinload(Party.roles))
        if model is RailwayAuthority:
            statement = statement.options(selectinload(RailwayAuthority.roles))
        if model is TermsConditionVersion:
            statement = statement.options(selectinload(TermsConditionVersion.terms_set))
        return await self.session.scalar(statement)

    async def get_quotation(self, quotation_id: UUID):
        return await self.session.scalar(
            select(Quotation)
            .options(selectinload(Quotation.lines))
            .where(Quotation.id == quotation_id)
        )

    async def list_quotations(self):
        result = await self.session.scalars(
            select(Quotation)
            .options(selectinload(Quotation.lines))
            .order_by(Quotation.created_at.desc())
        )
        return list(result.unique())

    async def revision_history(self, quotation_number: str):
        result = await self.session.scalars(
            select(Quotation)
            .options(selectinload(Quotation.lines))
            .where(Quotation.quotation_number == quotation_number)
            .order_by(Quotation.revision_number.desc())
        )
        return list(result.unique())

    async def customer_gst(self, party_id: UUID, on_date: date):
        return await self.session.scalar(
            select(GstRegistration)
            .where(
                GstRegistration.party_id == party_id,
                GstRegistration.is_active.is_(True),
                GstRegistration.effective_from <= on_date,
                or_(
                    GstRegistration.effective_to.is_(None), GstRegistration.effective_to >= on_date
                ),
            )
            .order_by(GstRegistration.is_default.desc())
        )

    def audit(self, actor_id, action, entity_type, entity_id, old=None, new=None, reason=None):
        self.session.add(
            AuditLog(
                actor_user_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                old_value=old,
                new_value=new,
                reason=reason,
            )
        )
