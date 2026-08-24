from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.assets import Asset
from app.models.attention import Alert, Notification
from app.models.billing import ProformaInvoice
from app.models.contracts import LoaVariation
from app.models.invoicing import TaxInvoice
from app.models.master_data import Loa, Project
from app.models.payments import CustomerPayment
from app.models.procurement import PurchaseOrder
from app.models.quotations import Quotation
from app.models.receiving import MaterialReceipt
from app.repositories.payment_repository import PaymentRepository

ROUTES = {
    "purchase_order": "/procurement",
    "loa_variation": "/projects",
    "proforma_invoice": "/proforma-invoices",
    "tax_invoice": "/tax-invoices",
    "quotation": "/quotations",
    "customer_payment": "/payments",
    "asset": "/assets",
    "material_receipt": "/receiving",
    "project": "/projects",
    "loa": "/projects",
}


class AttentionService:
    def __init__(self, repository):
        self.repository = repository
        self.session = repository.session

    async def evaluate(self, actor_id):
        now = datetime.now(UTC)
        today = date.today()
        rules = {r.rule_type: r for r in await self.repository.rules() if r.is_enabled}
        specs = []

        def add(
            rule,
            obj,
            etype,
            number,
            title,
            message,
            due=None,
            project=None,
            loa=None,
            party=None,
            role="ADMIN",
            key="default",
            severity=None,
        ):
            if rule in rules:
                specs.append(
                    dict(
                        alert_type=rule,
                        severity=severity or rules[rule].severity,
                        title=title,
                        message=message,
                        source_entity_type=etype,
                        source_entity_id=str(obj.id),
                        dedup_key=f"{rule}:{etype}:{obj.id}:{key}",
                        project_id=project,
                        loa_id=loa,
                        party_id=party,
                        assigned_role=role,
                        due_date=due,
                        context={"reference": number},
                    )
                )

        workflows = [
            (
                LoaVariation,
                "loa_variation",
                "SUBMITTED",
                "Variation",
                "reference_number",
                "loa_id",
                None,
            ),
            (
                PurchaseOrder,
                "purchase_order",
                "SUBMITTED",
                "Purchase Order",
                "po_number",
                "loa_id",
                "vendor_party_id",
            ),
            (
                ProformaInvoice,
                "proforma_invoice",
                "SUBMITTED",
                "Proforma Invoice",
                "pi_number",
                "loa_id",
                "customer_party_id",
            ),
            (
                TaxInvoice,
                "tax_invoice",
                "SUBMITTED",
                "Tax Invoice",
                "invoice_number",
                "loa_id",
                "customer_party_id",
            ),
            (
                Quotation,
                "quotation",
                "SUBMITTED",
                "Quotation",
                "quotation_number",
                "loa_id",
                "customer_party_id",
            ),
            (
                CustomerPayment,
                "customer_payment",
                "DRAFT",
                "Payment",
                "receipt_number",
                None,
                "customer_party_id",
            ),
        ]
        for model, etype, state, label, num, loa_field, party_field in workflows:
            for obj in await self.session.scalars(select(model).where(model.status == state)):
                number = getattr(obj, num)
                add(
                    "WORKFLOW_PENDING",
                    obj,
                    etype,
                    number,
                    f"{label} awaiting action",
                    f"{label} {number} is awaiting approval or confirmation.",
                    project=getattr(obj, "project_id", None),
                    loa=getattr(obj, loa_field, None) if loa_field else None,
                    party=getattr(obj, party_field, None) if party_field else None,
                    role="SUPER-ADMIN",
                )
        if "PO_DELIVERY" in rules:
            window = rules["PO_DELIVERY"].warning_days or 0
            q = select(PurchaseOrder).where(
                PurchaseOrder.delivery_date.is_not(None),
                PurchaseOrder.status.in_(("ISSUED", "PARTIALLY_FULFILLED")),
            )
            for po in await self.session.scalars(q):
                days = (po.delivery_date - today).days
                if days <= window:
                    delivery_state = "overdue" if days < 0 else f"due in {days} days"
                    add(
                        "PO_DELIVERY",
                        po,
                        "purchase_order",
                        po.po_number,
                        "PO delivery overdue" if days < 0 else "PO delivery approaching",
                        f"Purchase Order {po.po_number} delivery is {delivery_state}.",
                        po.delivery_date,
                        po.project_id,
                        po.loa_id,
                        po.vendor_party_id,
                        severity="HIGH" if days < 0 else None,
                        key="overdue" if days < 0 else "warning",
                    )
        for receipt in await self.session.scalars(
            select(MaterialReceipt)
            .options(selectinload(MaterialReceipt.lines))
            .where(MaterialReceipt.status == "VERIFIED")
        ):
            totals = {
                name: sum((getattr(line, name) for line in receipt.lines), Decimal(0))
                for name in (
                    "quantity_short",
                    "quantity_damaged",
                    "quantity_rejected",
                    "quantity_excess",
                )
            }
            for name, value in totals.items():
                if value > 0:
                    discrepancy = name.removeprefix("quantity_").replace("_", " ")
                    add(
                        "GRN_DISCREPANCY",
                        receipt,
                        "material_receipt",
                        receipt.receipt_number,
                        f"GRN {discrepancy.title()}",
                        f"GRN {receipt.receipt_number} records {value} {discrepancy} quantity.",
                        project=receipt.project_id,
                        loa=receipt.loa_id,
                        party=receipt.vendor_party_id,
                        key=name,
                    )
        await self._dated(
            rules, "PROJECT_DEADLINE", Project, "project", "name", "end_date", today, specs
        )
        await self._dated(
            rules, "LOA_DEADLINE", Loa, "loa", "loa_number", "completion_date", today, specs
        )
        if "WARRANTY_EXPIRY" in rules:
            window = rules["WARRANTY_EXPIRY"].warning_days or 0
            for asset in await self.session.scalars(
                select(Asset).where(
                    Asset.warranty_expiry_date.is_not(None),
                    Asset.status.not_in(("RETIRED", "DISPOSED", "REPLACED", "CANCELLED")),
                )
            ):
                days = (asset.warranty_expiry_date - today).days
                if days <= window:
                    warranty_state = "expired" if days < 0 else f"expires in {days} days"
                    add(
                        "WARRANTY_EXPIRY",
                        asset,
                        "asset",
                        asset.asset_number,
                        "Warranty expired" if days < 0 else "Warranty expiring",
                        f"Asset {asset.asset_number} warranty {warranty_state}.",
                        asset.warranty_expiry_date,
                        asset.current_project_id or asset.source_project_id,
                        asset.source_loa_id,
                        key="expired" if days < 0 else "warning",
                        severity="HIGH" if days < 0 else None,
                    )
        for asset in await self.session.scalars(
            select(Asset).where(Asset.status.in_(("LOST", "DAMAGED")))
        ):
            add(
                "ASSET_EXCEPTION",
                asset,
                "asset",
                asset.asset_number,
                f"Asset {asset.status.lower()}",
                f"Asset {asset.asset_number} is marked {asset.status}.",
                project=asset.current_project_id or asset.source_project_id,
                loa=asset.source_loa_id,
                key=asset.status,
            )
        if "RECEIVABLE_DUE" in rules:
            window = rules["RECEIVABLE_DUE"].warning_days or 0
            payments = PaymentRepository(self.session)
            for inv in await self.session.scalars(
                select(TaxInvoice).where(
                    TaxInvoice.status == "ISSUED", TaxInvoice.due_date.is_not(None)
                )
            ):
                received = Decimal(await payments.confirmed_invoice_allocated(inv.id))
                outstanding = inv.grand_total - received
                days = (inv.due_date - today).days
                if outstanding > 0 and days <= window:
                    due_state = f"overdue by {-days} days" if days < 0 else f"due in {days} days"
                    add(
                        "RECEIVABLE_DUE",
                        inv,
                        "tax_invoice",
                        inv.invoice_number,
                        "Invoice overdue" if days < 0 else "Invoice due approaching",
                        f"Tax Invoice {inv.invoice_number} is {due_state}. "
                        f"Outstanding: ₹{outstanding:.2f}.",
                        inv.due_date,
                        inv.project_id,
                        inv.loa_id,
                        inv.customer_party_id,
                        "SUPER-ADMIN",
                        "overdue" if days < 0 else "warning",
                        "HIGH" if days < 0 else None,
                    )
        return await self._sync(specs, now, actor_id)

    async def _dated(self, rules, rule, model, etype, numfield, datefield, today, specs):
        if rule not in rules:
            return
        window = rules[rule].warning_days or 0
        for obj in await self.session.scalars(
            select(model).where(getattr(model, datefield).is_not(None), model.is_active.is_(True))
        ):
            due = getattr(obj, datefield)
            days = (due - today).days
            if days <= window:
                deadline_state = "overdue" if days < 0 else "approaching"
                deadline_message = "overdue" if days < 0 else f"in {days} days"
                specs.append(
                    dict(
                        alert_type=rule,
                        severity="HIGH" if days < 0 else rules[rule].severity,
                        title=f"{etype.upper()} deadline {deadline_state}",
                        message=f"{getattr(obj, numfield)} deadline is {deadline_message}.",
                        source_entity_type=etype,
                        source_entity_id=str(obj.id),
                        dedup_key=f"{rule}:{etype}:{obj.id}:{'overdue' if days < 0 else 'warning'}",
                        project_id=obj.id if etype == "project" else obj.project_id,
                        loa_id=obj.id if etype == "loa" else None,
                        party_id=getattr(obj, "customer_party_id", None),
                        assigned_role="ADMIN",
                        due_date=due,
                        context={"reference": getattr(obj, numfield)},
                    )
                )

    async def _sync(self, specs, now, actor):
        active = {a.dedup_key: a for a in await self.repository.active()}
        seen = set()
        created = updated = resolved = 0
        for spec in specs:
            seen.add(spec["dedup_key"])
            alert = active.get(spec["dedup_key"])
            if alert:
                for k, v in spec.items():
                    setattr(alert, k, v)
                alert.last_evaluated_at = now
                updated += 1
            else:
                alert = Alert(**spec, last_evaluated_at=now)
                self.session.add(alert)
                await self.session.flush()
                created += 1
                for user in await self.repository.users_for(alert):
                    self.session.add(
                        Notification(
                            recipient_user_id=user.id,
                            category=alert.alert_type,
                            title=alert.title,
                            message=alert.message,
                            source_entity_type=alert.source_entity_type,
                            source_entity_id=alert.source_entity_id,
                            alert_id=alert.id,
                            action_url=ROUTES.get(alert.source_entity_type),
                        )
                    )
        evaluated = {s["alert_type"] for s in specs} | {
            r.rule_type for r in await self.repository.rules() if r.is_enabled
        }
        for key, alert in active.items():
            if alert.alert_type in evaluated and key not in seen:
                alert.status = "RESOLVED"
                alert.resolved_at = now
                alert.resolution_reason = "Underlying condition cleared during evaluation."
                alert.last_evaluated_at = now
                resolved += 1
        self.repository.audit(
            actor,
            "evaluate",
            "alerts",
            "system",
            new={"created": created, "updated": updated, "resolved": resolved},
        )
        await self.session.flush()
        return {"created": created, "updated": updated, "resolved": resolved}

    async def action(self, alert_id, payload, user, is_super):
        alert = await self.repository.get_alert(alert_id)
        if not alert:
            raise AppError(404, "alert_not_found", "Alert does not exist.")
        if not is_super and alert.assigned_user_id != user.id and alert.assigned_role != "ADMIN":
            raise AppError(403, "authorization_denied", "Alert access is denied.")
        now = datetime.now(UTC)
        old = alert.status
        if payload.action == "ACKNOWLEDGE" and alert.status == "OPEN":
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_by_user_id = user.id
            alert.acknowledged_at = now
        elif payload.action in ("RESOLVE", "DISMISS") and is_super:
            if not payload.reason:
                raise AppError(422, "reason_required", "A reason is required.")
            alert.status = "RESOLVED" if payload.action == "RESOLVE" else "DISMISSED"
            alert.resolved_by_user_id = user.id
            alert.resolved_at = now
            alert.resolution_reason = payload.reason
        else:
            raise AppError(
                403 if payload.action != "ACKNOWLEDGE" else 409,
                "alert_action_denied",
                "Alert action is not allowed.",
            )
        self.repository.audit(
            user.id,
            payload.action.lower(),
            "alert",
            alert.id,
            {"status": old},
            {"status": alert.status},
            payload.reason,
        )
        await self.session.flush()
        await self.session.refresh(alert)
        return alert
