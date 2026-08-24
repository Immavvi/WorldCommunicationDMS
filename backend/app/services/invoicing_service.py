from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.core.number_words import inr_amount_in_words
from app.models.billing import ProformaInvoice, ProformaInvoiceLine
from app.models.dispatch import SupplyChallan
from app.models.invoicing import TaxInvoice, TaxInvoiceLine
from app.models.master_data import (
    BankAccount,
    GstRegistration,
    Loa,
    Organization,
    Party,
    PartyAddress,
    PaymentTerm,
    Project,
    RailwayAuthority,
    RailwayAuthorityAddress,
    RailwayDivision,
    RailwayZone,
    TermsConditionVersion,
)
from app.repositories.invoicing_repository import InvoicingRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.invoicing import InvoiceablePosition, InvoiceCreate
from app.services.billing_service import ADDRESS_FIELDS, money, snapshot
from app.services.snapshot_service import contract_snapshot_values


def gst_snapshot(record):
    return {
        "gstin": record.gstin,
        "registered_name": record.registered_name,
        "state": record.state,
        "state_code": record.state_code,
        "effective_from": str(record.effective_from),
        "effective_to": str(record.effective_to) if record.effective_to else None,
    }


class InvoicingService:
    def __init__(self, repository: InvoicingRepository, numbering: ProcurementRepository):
        self.repository = repository
        self.numbering = numbering

    async def invoiceable_position(self, project_id: UUID | None = None):
        result = []
        for line, pi in await self.repository.eligible_pi_lines(project_id):
            previous = Decimal(await self.repository.invoiced_quantity(line.id))
            result.append(
                InvoiceablePosition(
                    proforma_invoice_line_id=line.id,
                    pi_number=pi.pi_number,
                    description=line.description_snapshot,
                    unit=line.unit_snapshot,
                    contract_origin="VARIATION"
                    if line.variation_line_id
                    else "ORIGINAL_LOA"
                    if line.loa_item_id
                    else None,
                    contractual_item_id=line.variation_line_id or line.loa_item_id,
                    challan_line_id=line.supply_challan_line_id,
                    eligible_pi_quantity=line.billable_quantity,
                    previously_invoiced_quantity=previous,
                    remaining_invoiceable_quantity=line.billable_quantity - previous,
                    sales_rate=line.sales_rate,
                )
            )
        return result

    async def create(self, payload: InvoiceCreate, actor_id: UUID):
        project = await self._get(Project, payload.project_id, "project")
        if (
            project.customer_party_id != payload.customer_party_id
            or project.business_scope != payload.business_scope
        ):
            raise AppError(
                422, "invalid_project_context", "Invoice customer and scope must match the project."
            )
        customer = await self._get(Party, payload.customer_party_id, "customer")
        if not any(role.role == "CUSTOMER" for role in customer.roles):
            raise AppError(422, "invalid_customer", "Selected party is not a customer.")
        loa = None
        if payload.loa_id:
            loa = await self._get(Loa, payload.loa_id, "loa")
            if loa.project_id != project.id:
                raise AppError(422, "invalid_loa", "LOA does not belong to the project.")
        organization = await self._get(Organization, payload.organization_id, "organization")
        gst = await self._get(GstRegistration, payload.gst_registration_id, "gst_registration")
        if (
            gst.organization_id != organization.id
            or not gst.is_active
            or gst.effective_from > payload.invoice_date
            or (gst.effective_to and gst.effective_to < payload.invoice_date)
        ):
            raise AppError(
                422,
                "invalid_gst_registration",
                "Select an active organization GST registration effective on the invoice date.",
            )
        bank = await self._get(BankAccount, payload.bank_account_id, "bank_account")
        if bank.organization_id != organization.id or not bank.is_active:
            raise AppError(
                422,
                "invalid_bank_account",
                "Bank account must be active and belong to the organization.",
            )
        division, authority, bill_to, ship_to = await self._addresses(payload)
        zone = await self._optional(RailwayZone, project.railway_zone_id)
        contract_division = division or await self._optional(
            RailwayDivision,
            loa.railway_division_id if loa else project.railway_division_id,
        )
        state = payload.place_of_supply_state or ship_to.state
        state_code = payload.place_of_supply_state_code or ship_to.state_code
        if not state or not state_code:
            raise AppError(
                422,
                "place_of_supply_required",
                "Place-of-supply state and state code are required when address data "
                "is incomplete.",
            )
        automatic_mode = "INTRA_STATE" if gst.state_code == state_code else "INTER_STATE"
        if payload.tax_mode and payload.tax_mode != automatic_mode:
            raise AppError(
                422,
                "tax_mode_conflict",
                "Selected tax mode conflicts with unambiguous GST and place-of-supply states.",
            )
        tax_mode = automatic_mode
        payment = await self._optional(PaymentTerm, payload.payment_term_id)
        terms = await self._optional(TermsConditionVersion, payload.terms_version_id)
        customer_gst = await self.repository.customer_gst(customer.id, payload.invoice_date)
        invoice = TaxInvoice(
            invoice_number=await self.numbering.next_number("TAX_INVOICE"),
            created_by_user_id=actor_id,
            tax_mode=tax_mode,
            place_of_supply_state=state,
            place_of_supply_state_code=state_code,
            due_date=payload.invoice_date + timedelta(days=payment.due_days)
            if payment and payment.due_days is not None
            else None,
            organization_snapshot=snapshot(
                organization, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            organization_gst_snapshot=gst_snapshot(gst),
            customer_snapshot=snapshot(
                customer, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            customer_gst_snapshot=gst_snapshot(customer_gst) if customer_gst else None,
            division_snapshot=snapshot(division, ("code", "name")) if division else None,
            authority_snapshot=snapshot(
                authority, ("code", "name", "designation", "email", "phone")
            )
            if authority
            else None,
            bill_to_snapshot=snapshot(bill_to, ADDRESS_FIELDS),
            ship_to_snapshot=snapshot(ship_to, ADDRESS_FIELDS),
            place_of_supply_snapshot={
                "state": state,
                "state_code": state_code,
                "tax_mode": tax_mode,
            },
            bank_snapshot=snapshot(
                bank,
                (
                    "account_name",
                    "bank_name",
                    "branch_name",
                    "account_number",
                    "account_type",
                    "ifsc",
                    "swift",
                ),
            ),
            payment_terms_snapshot=snapshot(payment, ("code", "name", "description", "due_days"))
            if payment
            else None,
            terms_snapshot={
                "id": str(terms.id),
                "version": terms.version,
                "content": terms.content,
                "effective_from": str(terms.effective_from),
            }
            if terms
            else None,
            **contract_snapshot_values(project, loa, zone, contract_division),
            **payload.model_dump(
                exclude={"lines", "tax_mode", "place_of_supply_state", "place_of_supply_state_code"}
            ),
        )
        invoice.lines = [
            await self._line(invoice, number, item) for number, item in enumerate(payload.lines, 1)
        ]
        self._totals(invoice, payload.round_off)
        await self.repository.save(invoice)
        self.repository.audit(
            actor_id,
            "assign_number",
            "tax_invoice",
            invoice.id,
            new={"invoice_number": invoice.invoice_number},
        )
        self.repository.audit(
            actor_id,
            "create",
            "tax_invoice",
            invoice.id,
            new={"grand_total": str(invoice.grand_total)},
        )
        return await self.repository.get_invoice(invoice.id)

    async def update_line(self, invoice_id, line_id, payload, actor_id):
        invoice = await self._invoice(invoice_id)
        if invoice.status != "DRAFT":
            raise AppError(409, "invoice_not_draft", "Only draft invoice lines can be edited.")
        line = next((candidate for candidate in invoice.lines if candidate.id == line_id), None)
        if line is None:
            raise AppError(404, "invoice_line_not_found", "Invoice line does not exist.")
        old = {"quantity": str(line.invoiced_quantity), "line_total": str(line.line_total)}
        calculated = await self._line(invoice, line.line_number, payload)
        excluded = {"id", "tax_invoice_id", "invoice", "line_number"}
        for column in calculated.__mapper__.column_attrs:
            if column.key not in excluded:
                setattr(line, column.key, getattr(calculated, column.key))
        self._totals(invoice, invoice.round_off)
        await self.repository.save(invoice)
        self.repository.audit(
            actor_id,
            "update",
            "tax_invoice_line",
            line.id,
            old,
            {"quantity": str(line.invoiced_quantity), "line_total": str(line.line_total)},
        )
        return await self.repository.get_invoice(invoice.id)

    async def transition(self, invoice_id, action, reason, actor_id, is_super_admin):
        invoice = await self._invoice(invoice_id)
        transitions = {
            ("DRAFT", "SUBMIT"): "SUBMITTED",
            ("SUBMITTED", "APPROVE"): "APPROVED",
            ("APPROVED", "ISSUE"): "ISSUED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("SUBMITTED", "CANCEL"): "CANCELLED",
            ("APPROVED", "CANCEL"): "CANCELLED",
            ("ISSUED", "CANCEL"): "CANCELLED",
        }
        new = transitions.get((invoice.status, action))
        if not new:
            raise AppError(409, "invalid_invoice_transition", "Invoice action is not allowed.")
        if action in {"APPROVE", "ISSUE", "CANCEL"} and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "APPROVE":
            if invoice.created_by_user_id == actor_id:
                raise AppError(
                    403, "self_approval_denied", "The invoice creator cannot approve it."
                )
            await self._validate_quantities(invoice)
            invoice.approved_by_user_id, invoice.approved_at = actor_id, datetime.now(UTC)
        if action == "ISSUE":
            await self._validate_quantities(invoice)
            invoice.issued_at = datetime.now(UTC)
        old = invoice.status
        invoice.status = new
        await self.repository.save(invoice)
        self.repository.audit(
            actor_id,
            action.lower(),
            "tax_invoice",
            invoice.id,
            {"status": old},
            {"status": new},
            reason,
        )
        return await self.repository.get_invoice(invoice.id)

    async def _line(self, invoice, number, item):
        pi_line = await self._get(ProformaInvoiceLine, item.proforma_invoice_line_id, "pi_line")
        pi = await self._get(ProformaInvoice, pi_line.proforma_invoice_id, "pi")
        challan = None
        if pi_line.supply_challan_line_id:
            from app.models.dispatch import SupplyChallanLine

            challan_line = await self._get(
                SupplyChallanLine, pi_line.supply_challan_line_id, "challan_line"
            )
            challan = await self._get(SupplyChallan, challan_line.supply_challan_id, "challan")
        if (
            pi.status not in {"APPROVED", "ISSUED"}
            or pi.project_id != invoice.project_id
            or pi.loa_id != invoice.loa_id
            or pi.customer_party_id != invoice.customer_party_id
        ):
            raise AppError(
                422,
                "invalid_pi_line",
                "Select an approved or issued PI line matching the invoice context.",
            )
        if invoice.tax_mode == "INTRA_STATE" and pi_line.igst_percent:
            raise AppError(
                422,
                "pi_tax_mode_conflict",
                "PI line tax percentages do not match the invoice tax mode.",
            )
        if invoice.tax_mode == "INTER_STATE" and (pi_line.cgst_percent or pi_line.sgst_percent):
            raise AppError(
                422,
                "pi_tax_mode_conflict",
                "PI line tax percentages do not match the invoice tax mode.",
            )
        subtotal = money(item.invoiced_quantity * pi_line.sales_rate)
        discount = money(subtotal * pi_line.discount_percent / 100)
        taxable = money(subtotal - discount)
        cgst, sgst, igst = (
            money(taxable * percent / 100)
            for percent in (pi_line.cgst_percent, pi_line.sgst_percent, pi_line.igst_percent)
        )
        return TaxInvoiceLine(
            line_number=number,
            supply_challan_line_id=pi_line.supply_challan_line_id,
            loa_item_id=pi_line.loa_item_id,
            variation_line_id=pi_line.variation_line_id,
            product_id=pi_line.product_id,
            description_snapshot=pi_line.description_snapshot,
            hsn_snapshot=pi_line.hsn_snapshot,
            unit_snapshot=pi_line.unit_snapshot,
            oem_snapshot=pi_line.oem_snapshot,
            model_snapshot=pi_line.model_snapshot,
            pi_number_snapshot=pi.pi_number,
            pi_date_snapshot=pi.pi_date,
            challan_number_snapshot=challan.challan_number if challan else None,
            challan_date_snapshot=challan.challan_date if challan else None,
            invoiced_quantity=item.invoiced_quantity,
            sales_rate=pi_line.sales_rate,
            discount_percent=pi_line.discount_percent,
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=taxable,
            cgst_percent=pi_line.cgst_percent,
            sgst_percent=pi_line.sgst_percent,
            igst_percent=pi_line.igst_percent,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            line_total=money(taxable + cgst + sgst + igst),
            proforma_invoice_line_id=pi_line.id,
            remarks=item.remarks,
        )

    def _totals(self, invoice, round_off):
        for field in (
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
        ):
            setattr(
                invoice,
                field,
                money(sum((getattr(line, field) for line in invoice.lines), Decimal("0"))),
            )
        invoice.round_off = money(round_off)
        invoice.grand_total = money(
            invoice.taxable_amount
            + invoice.cgst_amount
            + invoice.sgst_amount
            + invoice.igst_amount
            + invoice.round_off
        )
        invoice.amount_in_words = inr_amount_in_words(invoice.grand_total)

    async def _validate_quantities(self, invoice):
        ids = [line.proforma_invoice_line_id for line in invoice.lines]
        await self.repository.lock_pi_lines(ids)
        totals = defaultdict(lambda: Decimal("0"))
        for line in invoice.lines:
            totals[line.proforma_invoice_line_id] += line.invoiced_quantity
        for pi_line_id, requested in totals.items():
            pi_line = await self._get(ProformaInvoiceLine, pi_line_id, "pi_line")
            previous = Decimal(await self.repository.invoiced_quantity(pi_line_id, invoice.id))
            if previous + requested > pi_line.billable_quantity:
                raise AppError(
                    422,
                    "invoice_quantity_exceeded",
                    "Invoice quantity exceeds eligible PI quantity.",
                )

    async def _addresses(self, payload):
        if payload.business_scope == "RAILWAY":
            division = await self._get(RailwayDivision, payload.railway_division_id, "division")
            authority = await self._get(RailwayAuthority, payload.railway_authority_id, "authority")
            bill = await self._get(
                RailwayAuthorityAddress, payload.bill_to_railway_address_id, "bill_to"
            )
            ship = await self._get(
                RailwayAuthorityAddress, payload.ship_to_railway_address_id, "ship_to"
            )
            if (
                authority.division_id != division.id
                or bill.authority_id != authority.id
                or ship.authority_id != authority.id
            ):
                raise AppError(
                    422,
                    "invalid_railway_address",
                    "Railway authority/address selection is inconsistent.",
                )
            return division, authority, bill, ship
        bill = await self._get(PartyAddress, payload.bill_to_party_address_id, "bill_to")
        ship = await self._get(PartyAddress, payload.ship_to_party_address_id, "ship_to")
        if bill.party_id != payload.customer_party_id or ship.party_id != payload.customer_party_id:
            raise AppError(
                422,
                "invalid_customer_address",
                "Billing and shipping addresses must belong to the customer.",
            )
        return None, None, bill, ship

    async def _optional(self, model, record_id):
        return await self._get(model, record_id, model.__tablename__) if record_id else None

    async def _get(self, model, record_id, name):
        record = await self.repository.get(model, record_id)
        if record is None:
            raise AppError(
                422, f"invalid_{name}", f"Selected {name.replace('_', ' ')} does not exist."
            )
        return record

    async def _invoice(self, invoice_id):
        record = await self.repository.get_invoice(invoice_id)
        if record is None:
            raise AppError(404, "invoice_not_found", "Tax Invoice does not exist.")
        return record
