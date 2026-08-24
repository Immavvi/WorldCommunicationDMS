from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import func, select

from app.models.assets import Asset
from app.models.attention import Alert
from app.models.billing import ProformaInvoice, ProformaInvoiceLine
from app.models.contracts import LoaVariation
from app.models.dispatch import SupplyChallan, SupplyChallanLine
from app.models.invoicing import TaxInvoice, TaxInvoiceLine
from app.models.master_data import Loa, Project
from app.models.payments import CustomerPayment, PaymentAllocation
from app.models.procurement import ProcurementRequirement, PurchaseOrder, PurchaseOrderLine
from app.models.receiving import MaterialReceipt, MaterialReceiptLine
from app.repositories.contract_repository import ContractRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.contract_service import ContractService

FINANCE = {"proforma-invoices", "tax-invoices", "receivables", "payments"}


class ReportingService:
    def __init__(self, repository):
        self.repository = repository
        self.session = repository.session

    async def dashboard(self, user_id, is_super):
        today = date.today()
        r = self.repository
        result = {
            "operational": {
                "active_projects": await r.count(
                    Project, Project.is_active.is_(True), Project.status == "ACTIVE"
                ),
                "active_loas": await r.count(Loa, Loa.is_active.is_(True), Loa.status == "ACTIVE"),
                "open_variations": await r.count(
                    LoaVariation, LoaVariation.status.in_(("DRAFT", "SUBMITTED"))
                ),
                "open_requirements": await r.count(
                    ProcurementRequirement,
                    ProcurementRequirement.status.in_(("DRAFT", "SUBMITTED", "APPROVED")),
                ),
                "active_purchase_orders": await r.count(
                    PurchaseOrder,
                    PurchaseOrder.status.in_(
                        ("SUBMITTED", "APPROVED", "ISSUED", "PARTIALLY_FULFILLED")
                    ),
                ),
                "overdue_deliveries": await r.count(
                    PurchaseOrder,
                    PurchaseOrder.delivery_date < today,
                    PurchaseOrder.status.in_(("ISSUED", "PARTIALLY_FULFILLED")),
                ),
                "verified_received_quantity": await r.sum(
                    MaterialReceiptLine.quantity_accepted,
                    MaterialReceipt.status == "VERIFIED",
                    MaterialReceiptLine.material_receipt_id == MaterialReceipt.id,
                ),
                "dispatched_quantity": await r.sum(
                    SupplyChallanLine.dispatched_quantity,
                    SupplyChallan.status.in_(("DISPATCHED", "DELIVERED", "ACKNOWLEDGED")),
                    SupplyChallanLine.supply_challan_id == SupplyChallan.id,
                ),
                "assets_total": await r.count(Asset),
                "assets_available": await r.count(Asset, Asset.status == "AVAILABLE"),
                "assets_installed": await r.count(
                    Asset, Asset.status.in_(("INSTALLED", "IN_SERVICE"))
                ),
                "assets_exception": await r.count(
                    Asset, Asset.status.in_(("UNDER_REPAIR", "LOST", "DAMAGED"))
                ),
                "critical_alerts": await r.count(
                    Alert, Alert.status.in_(("OPEN", "ACKNOWLEDGED")), Alert.severity == "CRITICAL"
                ),
                "high_alerts": await r.count(
                    Alert, Alert.status.in_(("OPEN", "ACKNOWLEDGED")), Alert.severity == "HIGH"
                ),
                "my_attention": await r.count(
                    Alert,
                    Alert.status.in_(("OPEN", "ACKNOWLEDGED")),
                    (Alert.assigned_user_id == user_id) | (Alert.assigned_role == "ADMIN"),
                ),
                "unread_notifications": await r.unread(user_id),
            }
        }
        if is_super:
            positions = await self.receivables({})
            payments = await self.report("payments", {}, True, 0, 100000)
            result["financial"] = {
                "pi_value": await r.sum(
                    ProformaInvoice.grand_total, ProformaInvoice.status.in_(("APPROVED", "ISSUED"))
                ),
                "invoice_value": sum((x["invoice_total"] for x in positions), Decimal(0)),
                "received": sum((x["received"] for x in positions), Decimal(0)),
                "outstanding": sum((x["outstanding"] for x in positions), Decimal(0)),
                "overdue_outstanding": sum(
                    (x["outstanding"] for x in positions if x["days_overdue"] > 0), Decimal(0)
                ),
                "overdue_invoices": sum(1 for x in positions if x["days_overdue"] > 0),
                "unallocated_receipts": sum(
                    (x["unallocated"] for x in payments if x["status"] == "CONFIRMED"), Decimal(0)
                ),
            }
        return result

    async def report(self, name, filters, is_super, offset=0, limit=100):
        if name == "receivables":
            return (await self.receivables(filters))[offset : offset + limit]
        rows = await self.repository.rows(name, filters, offset, limit)
        result = [self._serialize(name, x, is_super) for x in rows]
        if name == "purchase-orders" and rows:
            received_rows = await self.session.execute(
                select(
                    PurchaseOrderLine.purchase_order_id,
                    func.coalesce(func.sum(MaterialReceiptLine.quantity_accepted), 0),
                )
                .join(
                    MaterialReceiptLine,
                    MaterialReceiptLine.purchase_order_line_id == PurchaseOrderLine.id,
                )
                .join(MaterialReceipt)
                .where(
                    PurchaseOrderLine.purchase_order_id.in_([row.id for row in rows]),
                    MaterialReceipt.status == "VERIFIED",
                )
                .group_by(PurchaseOrderLine.purchase_order_id)
            )
            received = dict(received_rows.all())
            today = date.today()
            for record, source in zip(result, rows, strict=True):
                record["received_quantity"] = Decimal(received.get(source.id, 0))
                record["pending_quantity"] = (
                    record["ordered_quantity"] - record["received_quantity"]
                )
                record["overdue"] = bool(
                    source.delivery_date
                    and source.delivery_date < today
                    and record["pending_quantity"] > 0
                )
        if name == "tax-invoices" and rows:
            allocation_rows = await self.session.execute(
                select(
                    PaymentAllocation.tax_invoice_id,
                    func.coalesce(func.sum(PaymentAllocation.allocated_amount), 0),
                )
                .join(CustomerPayment)
                .where(
                    PaymentAllocation.tax_invoice_id.in_([row.id for row in rows]),
                    CustomerPayment.status == "CONFIRMED",
                )
                .group_by(PaymentAllocation.tax_invoice_id)
            )
            allocated = dict(allocation_rows.all())
            today = date.today()
            for record, source in zip(result, rows, strict=True):
                received = Decimal(allocated.get(source.id, 0))
                outstanding = source.grand_total - received
                days = max((today - source.due_date).days, 0) if source.due_date else 0
                record.update(
                    received=received,
                    outstanding=outstanding,
                    days_overdue=days if outstanding > 0 else 0,
                    payment_status=(
                        "PAID"
                        if outstanding == 0
                        else "PARTIALLY_PAID"
                        if received > 0
                        else "UNPAID"
                    ),
                )
        return result

    def _serialize(self, name, x, is_super):
        if name == "projects":
            return {
                "id": x.id,
                "code": x.code,
                "name": x.name,
                "work_reference": x.work_reference,
                "business_scope": x.business_scope,
                "start_date": x.start_date,
                "end_date": x.end_date,
                "status": x.status,
            }
        if name == "variations":
            return {
                "id": x.id,
                "loa_id": x.loa_id,
                "reference": x.reference_number,
                "date": x.variation_date,
                "status": x.status,
                "positive_quantity": sum(
                    (line.quantity for line in x.lines if line.direction == "POSITIVE"), Decimal(0)
                ),
                "negative_quantity": sum(
                    (line.quantity for line in x.lines if line.direction == "NEGATIVE"), Decimal(0)
                ),
                "value_impact": sum(
                    (
                        line.line_value if line.direction == "POSITIVE" else -line.line_value
                        for line in x.lines
                    ),
                    Decimal(0),
                ),
                "created_by": x.created_by_user_id,
                "approved_by": x.approved_by_user_id,
            }
        if name == "requirements":
            return {
                "id": x.id,
                "number": x.requirement_number,
                "project_id": x.project_id,
                "loa_id": x.loa_id,
                "date": x.requirement_date,
                "required_by": x.required_by_date,
                "status": x.status,
                "requested_quantity": sum((line.required_quantity for line in x.lines), Decimal(0)),
            }
        if name == "purchase-orders":
            return {
                "id": x.id,
                "number": x.po_number,
                "vendor": x.vendor_snapshot.get("trade_name")
                or x.vendor_snapshot.get("legal_name"),
                "project": x.project_name_snapshot,
                "loa": x.loa_number_snapshot,
                "date": x.po_date,
                "delivery_date": x.delivery_date,
                "status": x.status,
                "ordered_quantity": sum((line.ordered_quantity for line in x.lines), Decimal(0)),
                **({"grand_total": x.grand_total} if is_super else {}),
            }
        if name == "receipts":
            return {
                "id": x.id,
                "number": x.receipt_number,
                "po": x.po_number_snapshot,
                "vendor": x.vendor_snapshot.get("trade_name")
                or x.vendor_snapshot.get("legal_name"),
                "project_id": x.project_id,
                "loa_id": x.loa_id,
                "date": x.receipt_date,
                "status": x.status,
                **{
                    k: sum((getattr(line, k) for line in x.lines), Decimal(0))
                    for k in (
                        "quantity_received",
                        "quantity_accepted",
                        "quantity_short",
                        "quantity_damaged",
                        "quantity_rejected",
                        "quantity_excess",
                    )
                },
            }
        if name == "challans":
            return {
                "id": x.id,
                "number": x.challan_number,
                "project": x.project_name_snapshot,
                "loa": x.loa_number_snapshot,
                "division": x.railway_division_snapshot,
                "consignee": (x.consignee_snapshot or {}).get("name"),
                "date": x.challan_date,
                "status": x.status,
                "quantity": sum((line.dispatched_quantity for line in x.lines), Decimal(0)),
                "acknowledged_date": x.acknowledged_date,
                "transport_reference": x.transport_reference,
            }
        if name == "assets":
            return {
                "id": x.id,
                "asset_number": x.asset_number,
                "serial_number": x.manufacturer_serial_number,
                "product": x.product_snapshot,
                "oem": x.oem_snapshot,
                "model": x.model_snapshot,
                "project": x.project_snapshot,
                "status": x.status,
                "location": " / ".join(
                    filter(
                        None, (x.current_site, x.current_building, x.current_room, x.current_rack)
                    )
                ),
                "installation_date": x.installation_date,
                "warranty_expiry": x.warranty_expiry_date,
                "purchase_order_id": x.purchase_order_id,
                "material_receipt_id": x.material_receipt_id,
            }
        if name == "proforma-invoices":
            return {
                "id": x.id,
                "number": x.pi_number,
                "date": x.pi_date,
                "customer": x.customer_snapshot.get("trade_name")
                or x.customer_snapshot.get("legal_name"),
                "project": x.project_name_snapshot,
                "loa": x.loa_number_snapshot,
                "status": x.status,
                "quantity": sum((line.billable_quantity for line in x.lines), Decimal(0)),
                "taxable": x.taxable_amount,
                "tax": x.cgst_amount + x.sgst_amount + x.igst_amount,
                "grand_total": x.grand_total,
            }
        if name == "tax-invoices":
            return {
                "id": x.id,
                "number": x.invoice_number,
                "date": x.invoice_date,
                "customer": x.customer_snapshot.get("trade_name")
                or x.customer_snapshot.get("legal_name"),
                "project": x.project_name_snapshot,
                "loa": x.loa_number_snapshot,
                "due_date": x.due_date,
                "status": x.status,
                "taxable": x.taxable_amount,
                "tax": x.cgst_amount + x.sgst_amount + x.igst_amount,
                "grand_total": x.grand_total,
            }
        if name == "payments":
            allocated = sum((a.allocated_amount for a in x.allocations), Decimal(0))
            return {
                "id": x.id,
                "number": x.receipt_number,
                "date": x.receipt_date,
                "customer": x.customer_snapshot.get("trade_name")
                or x.customer_snapshot.get("legal_name"),
                "mode": x.payment_mode,
                "reference": x.transaction_reference,
                "amount": x.amount_received,
                "allocated": allocated,
                "unallocated": x.amount_received - allocated,
                "status": x.status,
            }
        if name == "alerts":
            return {
                "id": x.id,
                "type": x.alert_type,
                "severity": x.severity,
                "project_id": x.project_id,
                "loa_id": x.loa_id,
                "source": f"{x.source_entity_type}:{x.source_entity_id}",
                "triggered_at": x.triggered_at,
                "target_date": x.due_date,
                "status": x.status,
                "acknowledged_by": x.acknowledged_by_user_id,
                "resolved_at": x.resolved_at,
            }
        return {}

    async def receivables(self, filters):
        invoices = await self.repository.rows(
            "tax-invoices", {**filters, "status": "ISSUED"}, 0, 100000
        )
        payments = PaymentRepository(self.session)
        today = date.today()
        result = []
        for x in invoices:
            received = Decimal(await payments.confirmed_invoice_allocated(x.id))
            outstanding = x.grand_total - received
            overdue = max((today - x.due_date).days, 0) if x.due_date and outstanding > 0 else 0
            result.append(
                {
                    "id": x.id,
                    "invoice": x.invoice_number,
                    "customer": x.customer_snapshot.get("trade_name")
                    or x.customer_snapshot.get("legal_name"),
                    "project": x.project_name_snapshot,
                    "loa": x.loa_number_snapshot,
                    "invoice_date": x.invoice_date,
                    "due_date": x.due_date,
                    "invoice_total": x.grand_total,
                    "received": received,
                    "outstanding": outstanding,
                    "days_overdue": overdue,
                    "aging": "CURRENT"
                    if overdue == 0
                    else "1-30"
                    if overdue <= 30
                    else "31-60"
                    if overdue <= 60
                    else "61-90"
                    if overdue <= 90
                    else "90+",
                }
            )
        return result

    async def loa_reconciliation(self, loa_id, is_super):
        position = await ContractService(ContractRepository(self.session)).approved_position(loa_id)
        result = []
        status_po = ("APPROVED", "ISSUED", "PARTIALLY_FULFILLED", "FULFILLED")
        status_ch = ("DISPATCHED", "DELIVERED", "ACKNOWLEDGED")
        status_pi = ("APPROVED", "ISSUED")
        for p in position.lines:

            def conditions(model):
                if p.origin == "VARIATION":
                    return model.variation_line_id == p.contractual_item_id
                return model.loa_item_id == p.loa_item_id

            po = await self.session.scalar(
                select(func.coalesce(func.sum(PurchaseOrderLine.ordered_quantity), 0))
                .join(PurchaseOrder)
                .where(PurchaseOrder.status.in_(status_po), conditions(PurchaseOrderLine))
            )
            received = await self.session.scalar(
                select(func.coalesce(func.sum(MaterialReceiptLine.quantity_accepted), 0))
                .join(MaterialReceipt)
                .join(
                    PurchaseOrderLine,
                    MaterialReceiptLine.purchase_order_line_id == PurchaseOrderLine.id,
                )
                .where(MaterialReceipt.status == "VERIFIED", conditions(PurchaseOrderLine))
            )
            dispatched = await self.session.scalar(
                select(func.coalesce(func.sum(SupplyChallanLine.dispatched_quantity), 0))
                .join(SupplyChallan)
                .where(SupplyChallan.status.in_(status_ch), conditions(SupplyChallanLine))
            )
            pi = await self.session.scalar(
                select(func.coalesce(func.sum(ProformaInvoiceLine.billable_quantity), 0))
                .join(ProformaInvoice)
                .where(ProformaInvoice.status.in_(status_pi), conditions(ProformaInvoiceLine))
            )
            invoiced = await self.session.scalar(
                select(func.coalesce(func.sum(TaxInvoiceLine.invoiced_quantity), 0))
                .join(TaxInvoice)
                .where(TaxInvoice.status == "ISSUED", conditions(TaxInvoiceLine))
            )
            row = {
                "contractual_item_id": p.contractual_item_id,
                "origin": p.origin,
                "item_number": p.item_number,
                "description": p.description,
                "original_quantity": p.original_quantity,
                "positive_variation": p.positive_variation_quantity,
                "negative_variation": p.negative_variation_quantity,
                "current_approved_quantity": p.current_approved_quantity,
                "po_committed": po,
                "received": received,
                "dispatched": dispatched,
                "pi_quantity": pi,
                "invoiced_quantity": invoiced,
                "remaining_procurement": p.current_approved_quantity - po,
                "remaining_dispatch": p.current_approved_quantity - dispatched,
                "remaining_billing": p.current_approved_quantity - invoiced,
            }
            if is_super:
                row.update(
                    contract_rate=p.contractual_rate,
                    current_approved_value=p.current_approved_value,
                    billed_value=p.contractual_rate * invoiced,
                )
            result.append(row)
        return result

    def excel(self, name, rows):
        book = Workbook()
        sheet = book.active
        sheet.title = name[:31]
        if rows:
            headers = list(rows[0])
            sheet.append(headers)
            for row in rows:
                sheet.append([self._excel_value(row.get(h)) for h in headers])
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = cell.font.copy(bold=True)
        stream = BytesIO()
        book.save(stream)
        stream.seek(0)
        return stream

    @staticmethod
    def _excel_value(value):
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "hex") and not isinstance(value, str):
            return str(value)
        if isinstance(value, (dict, list)):
            return str(value)
        return value
