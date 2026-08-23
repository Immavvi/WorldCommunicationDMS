from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.billing import ProformaInvoice, ProformaInvoiceLine
from app.models.dispatch import SupplyChallan, SupplyChallanLine
from app.models.master_data import Party, RailwayAuthority, TermsConditionVersion

COMMITTED_PI_STATUSES = ("APPROVED", "ISSUED")


class BillingRepository:
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

    async def get_pi(self, pi_id: UUID):
        return await self.session.scalar(
            select(ProformaInvoice)
            .options(selectinload(ProformaInvoice.lines))
            .where(ProformaInvoice.id == pi_id)
        )

    async def list_pis(self):
        result = await self.session.scalars(
            select(ProformaInvoice)
            .options(selectinload(ProformaInvoice.lines))
            .order_by(ProformaInvoice.created_at.desc())
        )
        return list(result.unique())

    async def eligible_challan_lines(self, project_id: UUID | None = None):
        statement = (
            select(SupplyChallanLine, SupplyChallan)
            .join(SupplyChallan)
            .where(SupplyChallan.status.in_(("DISPATCHED", "DELIVERED", "ACKNOWLEDGED")))
        )
        if project_id:
            statement = statement.where(SupplyChallan.project_id == project_id)
        return (await self.session.execute(statement)).all()

    async def committed_quantity(self, challan_line_id: UUID, exclude_pi_id: UUID | None = None):
        statement = (
            select(func.coalesce(func.sum(ProformaInvoiceLine.billable_quantity), 0))
            .join(ProformaInvoice)
            .where(
                ProformaInvoiceLine.supply_challan_line_id == challan_line_id,
                ProformaInvoice.status.in_(COMMITTED_PI_STATUSES),
            )
        )
        if exclude_pi_id:
            statement = statement.where(ProformaInvoice.id != exclude_pi_id)
        return await self.session.scalar(statement)

    async def lock_challan_lines(self, ids: list[UUID]):
        await self.session.scalars(
            select(SupplyChallanLine.id).where(SupplyChallanLine.id.in_(ids)).with_for_update()
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
