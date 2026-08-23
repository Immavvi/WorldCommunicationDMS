from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.billing import ProformaInvoice, ProformaInvoiceLine
from app.models.invoicing import TaxInvoice, TaxInvoiceLine
from app.models.master_data import GstRegistration, Party, RailwayAuthority, TermsConditionVersion

COMMITTED_INVOICE_STATUSES = ("APPROVED", "ISSUED")


class InvoicingRepository:
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

    async def get_invoice(self, invoice_id: UUID):
        return await self.session.scalar(
            select(TaxInvoice)
            .options(selectinload(TaxInvoice.lines))
            .where(TaxInvoice.id == invoice_id)
        )

    async def list_invoices(self):
        result = await self.session.scalars(
            select(TaxInvoice)
            .options(selectinload(TaxInvoice.lines))
            .order_by(TaxInvoice.created_at.desc())
        )
        return list(result.unique())

    async def eligible_pi_lines(self, project_id: UUID | None = None):
        statement = (
            select(ProformaInvoiceLine, ProformaInvoice)
            .join(ProformaInvoice)
            .where(ProformaInvoice.status.in_(("APPROVED", "ISSUED")))
        )
        if project_id:
            statement = statement.where(ProformaInvoice.project_id == project_id)
        return (await self.session.execute(statement)).all()

    async def invoiced_quantity(self, pi_line_id: UUID, exclude_invoice_id: UUID | None = None):
        statement = (
            select(func.coalesce(func.sum(TaxInvoiceLine.invoiced_quantity), 0))
            .join(TaxInvoice)
            .where(
                TaxInvoiceLine.proforma_invoice_line_id == pi_line_id,
                TaxInvoice.status.in_(COMMITTED_INVOICE_STATUSES),
            )
        )
        if exclude_invoice_id:
            statement = statement.where(TaxInvoice.id != exclude_invoice_id)
        return await self.session.scalar(statement)

    async def lock_pi_lines(self, ids: list[UUID]):
        await self.session.scalars(
            select(ProformaInvoiceLine.id).where(ProformaInvoiceLine.id.in_(ids)).with_for_update()
        )

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
