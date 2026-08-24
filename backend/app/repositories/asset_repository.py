from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assets import Asset, ChallanAssetAssignment
from app.models.auth import AuditLog
from app.models.dispatch import SupplyChallanLine
from app.models.master_data import Loa, OemProfile, Party, Product, ProductModel, Project
from app.models.procurement import PurchaseOrder, PurchaseOrderLine
from app.models.receiving import MaterialReceipt, MaterialReceiptLine


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def receipt_context(self, line_id: UUID, *, lock: bool = False):
        statement = (
            select(MaterialReceiptLine, MaterialReceipt, PurchaseOrderLine, PurchaseOrder)
            .join(MaterialReceipt, MaterialReceipt.id == MaterialReceiptLine.material_receipt_id)
            .join(
                PurchaseOrderLine,
                PurchaseOrderLine.id == MaterialReceiptLine.purchase_order_line_id,
            )
            .join(PurchaseOrder, PurchaseOrder.id == MaterialReceipt.purchase_order_id)
            .where(MaterialReceiptLine.id == line_id)
        )
        if lock:
            statement = statement.with_for_update(of=MaterialReceiptLine)
        return (await self.session.execute(statement)).first()

    async def registered_count(self, receipt_line_id: UUID):
        return await self.session.scalar(
            select(func.count(Asset.id)).where(
                Asset.material_receipt_line_id == receipt_line_id,
                Asset.status != "CANCELLED",
            )
        )

    async def serial_exists(self, normalized_serial: str):
        return bool(
            await self.session.scalar(
                select(Asset.id).where(Asset.normalized_serial == normalized_serial)
            )
        )

    async def eligible_receipt_lines(self):
        return (
            await self.session.execute(
                select(MaterialReceiptLine, MaterialReceipt, Product)
                .join(MaterialReceipt)
                .join(Product, Product.id == MaterialReceiptLine.product_id)
                .where(
                    MaterialReceipt.status == "VERIFIED",
                    Product.tracking_class == "SERIALIZED",
                    MaterialReceiptLine.quantity_accepted > 0,
                )
                .order_by(MaterialReceipt.receipt_date.desc())
            )
        ).all()

    async def get(self, asset_id: UUID, *, lock: bool = False):
        statement = select(Asset).options(selectinload(Asset.events)).where(Asset.id == asset_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        product_id: UUID | None = None,
        project_id: UUID | None = None,
        warranty_from: date | None = None,
        warranty_to: date | None = None,
    ):
        statement = select(Asset).options(selectinload(Asset.events))
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Asset.asset_number.ilike(pattern),
                    Asset.manufacturer_serial_number.ilike(pattern),
                    Asset.product_snapshot.ilike(pattern),
                    Asset.oem_snapshot.ilike(pattern),
                    Asset.model_snapshot.ilike(pattern),
                )
            )
        if status:
            statement = statement.where(Asset.status == status)
        if product_id:
            statement = statement.where(Asset.product_id == product_id)
        if project_id:
            statement = statement.where(Asset.current_project_id == project_id)
        if warranty_from:
            statement = statement.where(Asset.warranty_expiry_date >= warranty_from)
        if warranty_to:
            statement = statement.where(Asset.warranty_expiry_date <= warranty_to)
        result = await self.session.scalars(statement.order_by(Asset.asset_number))
        return list(result.unique())

    async def master(self, model, record_id):
        return await self.session.get(model, record_id) if record_id else None

    async def product_identity(self, product: Product):
        model = await self.master(ProductModel, product.product_model_id)
        if not model:
            return None, None
        profile = await self.master(OemProfile, model.oem_profile_id)
        party = await self.master(Party, profile.party_id) if profile else None
        return model, party

    async def challan_line(self, line_id: UUID, *, lock: bool = False):
        statement = select(SupplyChallanLine).where(SupplyChallanLine.id == line_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def assignment_count(self, line_id: UUID):
        return await self.session.scalar(
            select(func.count(ChallanAssetAssignment.id)).where(
                ChallanAssetAssignment.supply_challan_line_id == line_id
            )
        )

    async def source_names(self, project_id: UUID, loa_id: UUID | None):
        project = await self.master(Project, project_id)
        loa = await self.master(Loa, loa_id)
        return project, loa

    def audit(self, actor_id, action, entity_id, old=None, new=None, reason=None):
        self.session.add(
            AuditLog(
                actor_user_id=actor_id,
                action=action,
                entity_type="asset",
                entity_id=str(entity_id),
                old_value=old,
                new_value=new,
                reason=reason,
            )
        )
