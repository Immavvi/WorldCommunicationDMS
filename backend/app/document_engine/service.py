from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.document_engine import adapters
from app.document_engine.excel import render_excel
from app.document_engine.formatting import safe_filename
from app.document_engine.pdf import render_pdf
from app.models.billing import ProformaInvoice
from app.models.dispatch import SupplyChallan
from app.models.invoicing import TaxInvoice
from app.models.procurement import PurchaseOrder
from app.models.quotations import Quotation

DOCUMENTS = {
    "quotation": (Quotation, Quotation.lines, adapters.quotation),
    "purchase-order": (PurchaseOrder, PurchaseOrder.lines, adapters.purchase_order),
    "proforma-invoice": (ProformaInvoice, ProformaInvoice.lines, adapters.proforma_invoice),
    "tax-invoice": (TaxInvoice, TaxInvoice.lines, adapters.tax_invoice),
    "supply-challan": (SupplyChallan, SupplyChallan.lines, adapters.challan),
}


class DocumentExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def export(self, document_type: str, document_id: UUID, output_format: str):
        config = DOCUMENTS.get(document_type)
        if config is None:
            raise AppError(404, "document_type_not_found", "Document type is not supported.")
        model, relationship, adapter = config
        record = await self.session.scalar(
            select(model).options(selectinload(relationship)).where(model.id == document_id)
        )
        if record is None:
            raise AppError(404, "document_not_found", "Document does not exist.")
        document = adapter(record)
        if output_format == "pdf":
            return (
                render_pdf(document),
                "application/pdf",
                safe_filename(document.identifier, "pdf"),
            )
        if output_format == "excel":
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            return render_excel(document), media, safe_filename(document.identifier, "xlsx")
        raise AppError(404, "document_format_not_found", "Document format is not supported.")
