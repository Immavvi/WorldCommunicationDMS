from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.assets import Asset
from app.models.attention import Alert, Notification
from app.models.billing import ProformaInvoice
from app.models.contracts import LoaVariation
from app.models.dispatch import SupplyChallan
from app.models.invoicing import TaxInvoice
from app.models.master_data import Project
from app.models.payments import CustomerPayment
from app.models.procurement import ProcurementRequirement, PurchaseOrder
from app.models.receiving import MaterialReceipt

MODELS = {
    "projects": Project,
    "variations": LoaVariation,
    "requirements": ProcurementRequirement,
    "purchase-orders": PurchaseOrder,
    "receipts": MaterialReceipt,
    "challans": SupplyChallan,
    "assets": Asset,
    "proforma-invoices": ProformaInvoice,
    "tax-invoices": TaxInvoice,
    "payments": CustomerPayment,
    "alerts": Alert,
}
DATE_FIELDS = {
    "projects": Project.start_date,
    "variations": LoaVariation.variation_date,
    "requirements": ProcurementRequirement.requirement_date,
    "purchase-orders": PurchaseOrder.po_date,
    "receipts": MaterialReceipt.receipt_date,
    "challans": SupplyChallan.challan_date,
    "assets": Asset.created_at,
    "proforma-invoices": ProformaInvoice.pi_date,
    "tax-invoices": TaxInvoice.invoice_date,
    "payments": CustomerPayment.receipt_date,
    "alerts": Alert.triggered_at,
}


class ReportingRepository:
    def __init__(self, session):
        self.session = session

    async def rows(self, name, filters, offset=0, limit=1000):
        model = MODELS[name]
        q = select(model)
        if hasattr(model, "lines"):
            q = q.options(selectinload(model.lines))
        if name == "payments":
            q = q.options(selectinload(CustomerPayment.allocations))
        if name == "projects" and filters.get("project_id"):
            q = q.where(Project.id == filters["project_id"])
        if name == "assets" and filters.get("project_id"):
            q = q.where(Asset.current_project_id == filters["project_id"])
        if name == "assets" and filters.get("product_id"):
            q = q.where(Asset.product_id == filters["product_id"])
        if name == "assets" and filters.get("oem_party_id"):
            q = q.where(Asset.oem_party_id == filters["oem_party_id"])
        if name == "assets" and filters.get("railway_division_id"):
            q = q.where(Asset.current_railway_division_id == filters["railway_division_id"])
        for field in (
            "project_id",
            "loa_id",
            "status",
            "customer_party_id",
            "vendor_party_id",
            "railway_division_id",
        ):
            value = filters.get(field)
            if value is not None and hasattr(model, field):
                q = q.where(getattr(model, field) == value)
        date_field = DATE_FIELDS[name]
        if filters.get("date_from"):
            q = q.where(date_field >= filters["date_from"])
        if filters.get("date_to"):
            q = q.where(date_field <= filters["date_to"])
        return list(
            (
                await self.session.scalars(
                    q.order_by(date_field.desc()).offset(offset).limit(limit)
                )
            ).unique()
        )

    async def count(self, model, *criteria):
        return await self.session.scalar(select(func.count()).select_from(model).where(*criteria))

    async def sum(self, column, *criteria):
        return await self.session.scalar(
            select(func.coalesce(func.sum(column), 0)).where(*criteria)
        )

    async def unread(self, user):
        return await self.count(
            Notification, Notification.recipient_user_id == user, Notification.is_read.is_(False)
        )
