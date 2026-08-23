from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.procurement import PurchaseOrder, PurchaseOrderLine
from app.models.receiving import MaterialReceipt, MaterialReceiptLine


class ReceivingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_po(self, po_id: UUID, *, lock: bool = False):
        statement = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.id == po_id)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def lock_po_lines(self, line_ids: list[UUID]) -> None:
        await self.session.scalars(
            select(PurchaseOrderLine.id).where(PurchaseOrderLine.id.in_(line_ids)).with_for_update()
        )

    async def get_receipt(self, receipt_id: UUID):
        return await self.session.scalar(
            select(MaterialReceipt)
            .options(selectinload(MaterialReceipt.lines))
            .where(MaterialReceipt.id == receipt_id)
        )

    async def list_receipts(self, po_id: UUID | None = None):
        statement = (
            select(MaterialReceipt)
            .options(selectinload(MaterialReceipt.lines))
            .order_by(MaterialReceipt.created_at.desc())
        )
        if po_id:
            statement = statement.where(MaterialReceipt.purchase_order_id == po_id)
        result = await self.session.scalars(statement)
        return list(result.unique())

    async def accepted_quantity(self, po_line_id: UUID, *, exclude_receipt_id: UUID | None = None):
        statement = (
            select(func.coalesce(func.sum(MaterialReceiptLine.quantity_accepted), 0))
            .join(MaterialReceipt)
            .where(
                MaterialReceiptLine.purchase_order_line_id == po_line_id,
                MaterialReceipt.status == "VERIFIED",
            )
        )
        if exclude_receipt_id:
            statement = statement.where(MaterialReceipt.id != exclude_receipt_id)
        return await self.session.scalar(statement)

    def audit(
        self,
        actor_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old=None,
        new=None,
        reason=None,
    ):
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
