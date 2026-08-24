from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.core.errors import AppError
from app.core.number_words import inr_amount_in_words
from app.models.billing import ProformaInvoice, ProformaInvoiceLine
from app.models.contracts import LoaItem, LoaVariationLine
from app.models.dispatch import SupplyChallanLine
from app.models.master_data import (
    BankAccount,
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
    UnitOfMeasure,
)
from app.repositories.billing_repository import BillingRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.billing import BillablePosition, PiCreate
from app.services.snapshot_service import contract_snapshot_values, gst_snapshot_values

MONEY = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def snapshot(record, fields):
    return {field: getattr(record, field) for field in fields}


ADDRESS_FIELDS = (
    "label",
    "address_line_1",
    "address_line_2",
    "city",
    "district",
    "state",
    "state_code",
    "postal_code",
    "country",
    "contact_name",
    "phone",
    "email",
)


class BillingService:
    def __init__(self, repository: BillingRepository, numbering: ProcurementRepository):
        self.repository = repository
        self.numbering = numbering

    async def billable_position(self, project_id: UUID | None = None):
        positions = []
        for line, challan in await self.repository.eligible_challan_lines(project_id):
            committed = Decimal(await self.repository.committed_quantity(line.id))
            rate = await self._contract_rate(line.loa_item_id, line.variation_line_id)
            source = line.variation_line_id or line.loa_item_id
            positions.append(
                BillablePosition(
                    supply_challan_line_id=line.id,
                    challan_number=challan.challan_number,
                    description=line.description_snapshot,
                    unit=line.unit_snapshot,
                    contract_origin="VARIATION"
                    if line.variation_line_id
                    else "ORIGINAL_LOA"
                    if line.loa_item_id
                    else None,
                    contractual_item_id=source,
                    eligible_dispatched_quantity=line.dispatched_quantity,
                    previously_committed_pi_quantity=committed,
                    remaining_billable_quantity=line.dispatched_quantity - committed,
                    contractual_sales_rate=rate,
                )
            )
        return positions

    async def create(self, payload: PiCreate, actor_id: UUID):
        project = await self._get(Project, payload.project_id, "project")
        if (
            project.customer_party_id != payload.customer_party_id
            or project.business_scope != payload.business_scope
        ):
            raise AppError(
                422, "invalid_project_context", "PI customer and scope must match the project."
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
        organization_gst = await self.repository.effective_gst(
            payload.pi_date, organization_id=organization.id
        )
        customer_gst = await self.repository.effective_gst(payload.pi_date, party_id=customer.id)
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
        payment = await self._optional(PaymentTerm, payload.payment_term_id)
        terms = await self._optional(TermsConditionVersion, payload.terms_version_id)
        if terms and terms.terms_set.context not in {
            "INVOICE",
            "RAILWAY",
            "NON_RAILWAY",
            "GENERAL",
        }:
            raise AppError(422, "invalid_terms_context", "Selected terms are not valid for a PI.")
        pi = ProformaInvoice(
            pi_number=await self.numbering.next_number("PROFORMA_INVOICE"),
            created_by_user_id=actor_id,
            organization_snapshot=snapshot(
                organization, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            organization_gst_snapshot=gst_snapshot_values(organization_gst),
            customer_snapshot=snapshot(
                customer, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            customer_gst_snapshot=gst_snapshot_values(customer_gst),
            division_snapshot=snapshot(division, ("code", "name")) if division else None,
            authority_snapshot=snapshot(
                authority, ("code", "name", "designation", "email", "phone")
            )
            if authority
            else None,
            bill_to_snapshot=snapshot(bill_to, ADDRESS_FIELDS),
            ship_to_snapshot=snapshot(ship_to, ADDRESS_FIELDS),
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
            **payload.model_dump(exclude={"lines"}),
        )
        pi.lines = [await self._line(pi, n, item) for n, item in enumerate(payload.lines, 1)]
        self._totals(pi, payload.round_off)
        await self.repository.save(pi)
        self.repository.audit(
            actor_id, "assign_number", "proforma_invoice", pi.id, new={"pi_number": pi.pi_number}
        )
        self.repository.audit(
            actor_id, "create", "proforma_invoice", pi.id, new={"grand_total": str(pi.grand_total)}
        )
        return await self.repository.get_pi(pi.id)

    async def update_line(self, pi_id, line_id, payload, actor_id):
        pi = await self._pi(pi_id)
        if pi.status != "DRAFT":
            raise AppError(409, "pi_not_draft", "Only draft PI lines can be edited.")
        line = next((candidate for candidate in pi.lines if candidate.id == line_id), None)
        if line is None:
            raise AppError(404, "pi_line_not_found", "PI line does not exist.")
        old = {
            "quantity": str(line.billable_quantity),
            "sales_rate": str(line.sales_rate),
            "line_total": str(line.line_total),
        }
        calculated = await self._line(pi, line.line_number, payload)
        excluded = {"id", "proforma_invoice_id", "invoice", "line_number"}
        for column in calculated.__mapper__.column_attrs:
            if column.key not in excluded:
                setattr(line, column.key, getattr(calculated, column.key))
        self._totals(pi, pi.round_off)
        await self.repository.save(pi)
        self.repository.audit(
            actor_id,
            "update",
            "proforma_invoice_line",
            line.id,
            old,
            {
                "quantity": str(line.billable_quantity),
                "sales_rate": str(line.sales_rate),
                "line_total": str(line.line_total),
            },
        )
        return await self.repository.get_pi(pi.id)

    async def transition(self, pi_id, action, reason, actor_id, is_super_admin):
        pi = await self._pi(pi_id)
        transitions = {
            ("DRAFT", "SUBMIT"): "SUBMITTED",
            ("SUBMITTED", "APPROVE"): "APPROVED",
            ("APPROVED", "ISSUE"): "ISSUED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("SUBMITTED", "CANCEL"): "CANCELLED",
            ("APPROVED", "CANCEL"): "CANCELLED",
            ("ISSUED", "CANCEL"): "CANCELLED",
        }
        new = transitions.get((pi.status, action))
        if not new:
            raise AppError(409, "invalid_pi_transition", "PI action is not allowed.")
        if action in {"APPROVE", "ISSUE", "CANCEL"} and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "APPROVE":
            if pi.created_by_user_id == actor_id:
                raise AppError(403, "self_approval_denied", "The PI creator cannot approve it.")
            await self._validate_quantities(pi)
            pi.approved_by_user_id = actor_id
            pi.approved_at = datetime.now(UTC)
        if action == "ISSUE":
            await self._validate_quantities(pi)
            pi.issued_at = datetime.now(UTC)
        old = pi.status
        pi.status = new
        await self.repository.save(pi)
        self.repository.audit(
            actor_id,
            action.lower(),
            "proforma_invoice",
            pi.id,
            {"status": old},
            {"status": new},
            reason,
        )
        return await self.repository.get_pi(pi.id)

    async def _line(self, pi, number, item):
        challan_line = None
        if item.supply_challan_line_id:
            challan_line = await self._get(
                SupplyChallanLine, item.supply_challan_line_id, "challan_line"
            )
            from app.models.dispatch import SupplyChallan

            challan = await self._get(SupplyChallan, challan_line.supply_challan_id, "challan")
            if challan.project_id != pi.project_id or challan.status not in {
                "DISPATCHED",
                "DELIVERED",
                "ACKNOWLEDGED",
            }:
                raise AppError(
                    422,
                    "invalid_challan_line",
                    "Select an eligible dispatched Challan line for this project.",
                )
            if challan.loa_id != pi.loa_id:
                raise AppError(
                    422,
                    "invalid_challan_loa",
                    "Challan and PI must reference the same LOA.",
                )
            if (challan_line.loa_item_id or challan_line.variation_line_id) and pi.loa_id is None:
                raise AppError(422, "loa_required", "Contract-linked PI lines require an LOA.")
            item.loa_item_id, item.variation_line_id, item.product_id = (
                challan_line.loa_item_id,
                challan_line.variation_line_id,
                challan_line.product_id,
            )
            description, hsn, unit = (
                challan_line.description_snapshot,
                challan_line.hsn_snapshot,
                challan_line.unit_snapshot,
            )
            oem = challan_line.oem_snapshot
            model = challan_line.model_snapshot
            challan_number = challan.challan_number
            challan_date = challan.challan_date
        else:
            if not item.description or not item.unit_id:
                raise AppError(
                    422, "line_snapshot_required", "Non-Challan lines require description and UOM."
                )
            unit_record = await self._get(UnitOfMeasure, item.unit_id, "unit")
            description, hsn, unit = (
                item.description,
                item.hsn_code,
                f"{unit_record.code} - {unit_record.symbol}",
            )
            oem = model = challan_number = challan_date = None
        rate = await self._contract_rate(item.loa_item_id, item.variation_line_id)
        if rate is None:
            rate = item.sales_rate
        if rate is None:
            raise AppError(422, "sales_rate_required", "A customer-facing sales rate is required.")
        subtotal = money(item.billable_quantity * rate)
        discount = money(subtotal * item.discount_percent / 100)
        taxable = money(subtotal - discount)
        cgst, sgst, igst = (
            money(taxable * percent / 100)
            for percent in (item.cgst_percent, item.sgst_percent, item.igst_percent)
        )
        return ProformaInvoiceLine(
            line_number=number,
            description_snapshot=description,
            hsn_snapshot=hsn,
            unit_snapshot=unit,
            oem_snapshot=oem,
            model_snapshot=model,
            challan_number_snapshot=challan_number,
            challan_date_snapshot=challan_date,
            sales_rate=rate,
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=taxable,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            line_total=money(taxable + cgst + sgst + igst),
            **item.model_dump(exclude={"description", "hsn_code", "unit_id", "sales_rate"}),
        )

    def _totals(self, pi, round_off):
        for field in (
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
        ):
            setattr(
                pi, field, money(sum((getattr(line, field) for line in pi.lines), Decimal("0")))
            )
        pi.round_off = money(round_off)
        pi.grand_total = money(
            pi.taxable_amount + pi.cgst_amount + pi.sgst_amount + pi.igst_amount + pi.round_off
        )
        pi.amount_in_words = inr_amount_in_words(pi.grand_total)

    async def _validate_quantities(self, pi):
        ids = [line.supply_challan_line_id for line in pi.lines if line.supply_challan_line_id]
        await self.repository.lock_challan_lines(ids)
        totals = defaultdict(lambda: Decimal("0"))
        for line in pi.lines:
            if line.supply_challan_line_id:
                totals[line.supply_challan_line_id] += line.billable_quantity
        for line_id, requested in totals.items():
            challan_line = await self._get(SupplyChallanLine, line_id, "challan_line")
            previous = Decimal(await self.repository.committed_quantity(line_id, pi.id))
            if previous + requested > challan_line.dispatched_quantity:
                raise AppError(
                    422, "pi_quantity_exceeded", "PI quantity exceeds eligible dispatched quantity."
                )

    async def _contract_rate(self, loa_item_id, variation_line_id):
        if loa_item_id:
            return (await self._get(LoaItem, loa_item_id, "loa_item")).contractual_rate
        if variation_line_id:
            return (await self._get(LoaVariationLine, variation_line_id, "variation_line")).rate
        return None

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

    async def _pi(self, pi_id):
        record = await self.repository.get_pi(pi_id)
        if record is None:
            raise AppError(404, "pi_not_found", "Proforma Invoice does not exist.")
        return record
