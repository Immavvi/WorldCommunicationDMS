from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.invoicing import TaxInvoice
from app.models.master_data import Party
from app.models.payments import CustomerPayment, PaymentAllocation


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, payment_id: UUID, *, lock: bool = False):
        statement = (
            select(CustomerPayment)
            .options(selectinload(CustomerPayment.allocations))
            .where(CustomerPayment.id == payment_id)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(self, *, customer_id=None, status=None, offset=0, limit=100):
        statement = select(CustomerPayment).options(selectinload(CustomerPayment.allocations))
        if customer_id:
            statement = statement.where(CustomerPayment.customer_party_id == customer_id)
        if status:
            statement = statement.where(CustomerPayment.status == status)
        result = await self.session.scalars(
            statement.order_by(CustomerPayment.receipt_date.desc()).offset(offset).limit(limit)
        )
        return list(result.unique())

    async def invoice(self, invoice_id: UUID, *, lock: bool = False):
        statement = select(TaxInvoice).where(TaxInvoice.id == invoice_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def confirmed_invoice_allocated(
        self, invoice_id: UUID, *, exclude_payment_id: UUID | None = None
    ):
        statement = (
            select(func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0))
            .join(CustomerPayment)
            .where(
                PaymentAllocation.tax_invoice_id == invoice_id,
                CustomerPayment.status == "CONFIRMED",
            )
        )
        if exclude_payment_id:
            statement = statement.where(CustomerPayment.id != exclude_payment_id)
        return await self.session.scalar(statement)

    async def receivable_invoices(
        self,
        *,
        customer_id=None,
        project_id=None,
        loa_id=None,
        railway_division_id=None,
        invoice_id=None,
    ):
        statement = select(TaxInvoice).where(TaxInvoice.status == "ISSUED")
        if customer_id:
            statement = statement.where(TaxInvoice.customer_party_id == customer_id)
        if project_id:
            statement = statement.where(TaxInvoice.project_id == project_id)
        if loa_id:
            statement = statement.where(TaxInvoice.loa_id == loa_id)
        if railway_division_id:
            statement = statement.where(TaxInvoice.railway_division_id == railway_division_id)
        if invoice_id:
            statement = statement.where(TaxInvoice.id == invoice_id)
        return list(await self.session.scalars(statement.order_by(TaxInvoice.invoice_date.desc())))

    async def allocation(self, allocation_id: UUID):
        return await self.session.get(PaymentAllocation, allocation_id)

    async def invoice_payment_history(self, invoice_id: UUID):
        statement = (
            select(PaymentAllocation, CustomerPayment)
            .join(CustomerPayment)
            .where(PaymentAllocation.tax_invoice_id == invoice_id)
            .order_by(PaymentAllocation.allocation_date, PaymentAllocation.created_at)
        )
        return list((await self.session.execute(statement)).all())

    async def delete_draft_allocation(self, allocation):
        await self.session.delete(allocation)
        await self.session.flush()

    async def master(self, model, record_id):
        if not record_id:
            return None
        statement = select(model).where(model.id == record_id)
        if model is Party:
            statement = statement.options(selectinload(Party.roles))
        return await self.session.scalar(statement)

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
