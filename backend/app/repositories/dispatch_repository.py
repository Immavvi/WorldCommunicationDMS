from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.dispatch import ChallanReceiptAllocation, SupplyChallan, SupplyChallanLine
from app.models.master_data import OrganizationAddress, Party, RailwayAuthority
from app.models.procurement import PurchaseOrder, PurchaseOrderLine
from app.models.receiving import MaterialReceipt, MaterialReceiptLine

DISPATCHED_STATUSES = ("DISPATCHED", "DELIVERED", "ACKNOWLEDGED")


class DispatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_challan(self, challan_id: UUID):
        return await self.session.scalar(
            select(SupplyChallan)
            .options(selectinload(SupplyChallan.lines).selectinload(SupplyChallanLine.allocations))
            .where(SupplyChallan.id == challan_id)
        )

    async def list_challans(self):
        result = await self.session.scalars(
            select(SupplyChallan)
            .options(selectinload(SupplyChallan.lines).selectinload(SupplyChallanLine.allocations))
            .order_by(SupplyChallan.created_at.desc())
        )
        return list(result.unique())

    async def get(self, model, record_id: UUID):
        statement = select(model).where(model.id == record_id)
        if model is Party:
            statement = statement.options(selectinload(Party.roles))
        if model is RailwayAuthority:
            statement = statement.options(selectinload(RailwayAuthority.roles))
        if model is OrganizationAddress:
            statement = statement.options(selectinload(OrganizationAddress.organization))
        return await self.session.scalar(statement)

    async def receipt_line_context(self, line_id: UUID):
        return await self.session.execute(
            select(MaterialReceiptLine, MaterialReceipt, PurchaseOrderLine, PurchaseOrder)
            .join(MaterialReceipt, MaterialReceipt.id == MaterialReceiptLine.material_receipt_id)
            .join(
                PurchaseOrderLine,
                PurchaseOrderLine.id == MaterialReceiptLine.purchase_order_line_id,
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .where(MaterialReceiptLine.id == line_id)
        )

    async def verified_receipt_lines(self, project_id: UUID | None = None):
        statement = (
            select(MaterialReceiptLine, MaterialReceipt, PurchaseOrderLine)
            .join(MaterialReceipt, MaterialReceipt.id == MaterialReceiptLine.material_receipt_id)
            .join(
                PurchaseOrderLine,
                PurchaseOrderLine.id == MaterialReceiptLine.purchase_order_line_id,
            )
            .where(MaterialReceipt.status == "VERIFIED")
        )
        if project_id:
            statement = statement.where(MaterialReceipt.project_id == project_id)
        return (await self.session.execute(statement)).all()

    async def allocated_receipt_quantity(
        self, receipt_line_id: UUID, exclude_challan_id: UUID | None = None
    ):
        statement = (
            select(func.coalesce(func.sum(ChallanReceiptAllocation.allocated_quantity), 0))
            .join(SupplyChallanLine)
            .join(SupplyChallan)
            .where(
                ChallanReceiptAllocation.material_receipt_line_id == receipt_line_id,
                SupplyChallan.status.in_(DISPATCHED_STATUSES),
            )
        )
        if exclude_challan_id:
            statement = statement.where(SupplyChallan.id != exclude_challan_id)
        return await self.session.scalar(statement)

    async def dispatched_contract_quantity(
        self,
        loa_item_id: UUID | None,
        variation_line_id: UUID | None,
        exclude_challan_id: UUID | None = None,
    ):
        statement = (
            select(func.coalesce(func.sum(SupplyChallanLine.dispatched_quantity), 0))
            .join(SupplyChallan)
            .where(SupplyChallan.status.in_(DISPATCHED_STATUSES))
        )
        statement = (
            statement.where(SupplyChallanLine.loa_item_id == loa_item_id)
            if loa_item_id
            else statement.where(SupplyChallanLine.variation_line_id == variation_line_id)
        )
        if exclude_challan_id:
            statement = statement.where(SupplyChallan.id != exclude_challan_id)
        return await self.session.scalar(statement)

    async def lock_receipt_lines(self, ids: list[UUID]):
        await self.session.scalars(
            select(MaterialReceiptLine.id).where(MaterialReceiptLine.id.in_(ids)).with_for_update()
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
