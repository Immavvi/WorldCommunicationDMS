from datetime import UTC, datetime
from decimal import Decimal

from app.core.errors import AppError
from app.core.number_words import inr_amount_in_words
from app.models.master_data import (
    GstRegistration,
    HsnCode,
    Loa,
    OemProfile,
    Organization,
    Party,
    PartyAddress,
    PaymentTerm,
    Product,
    ProductModel,
    Project,
    RailwayAuthority,
    RailwayAuthorityAddress,
    RailwayDivision,
    RailwayZone,
    TermsConditionVersion,
    UnitOfMeasure,
)
from app.models.quotations import Quotation, QuotationLine
from app.repositories.procurement_repository import ProcurementRepository
from app.repositories.quotation_repository import QuotationRepository
from app.services.billing_service import ADDRESS_FIELDS, money, snapshot
from app.services.invoicing_service import gst_snapshot


class QuotationService:
    def __init__(self, repository: QuotationRepository, numbering: ProcurementRepository):
        self.repository, self.numbering = repository, numbering

    async def create(self, payload, actor_id):
        customer = await self._get(Party, payload.customer_party_id, "customer")
        if not any(role.role == "CUSTOMER" for role in customer.roles):
            raise AppError(422, "invalid_customer", "Selected party is not a customer.")
        project = await self._optional(Project, payload.project_id)
        if project and (
            project.customer_party_id != customer.id
            or project.business_scope != payload.business_scope
        ):
            raise AppError(
                422,
                "invalid_project_context",
                "Project customer and scope must match the quotation.",
            )
        loa = await self._optional(Loa, payload.loa_id)
        if loa and (not project or loa.project_id != project.id):
            raise AppError(
                422, "invalid_loa", "LOA requires and must belong to the selected project."
            )
        organization = await self._get(Organization, payload.organization_id, "organization")
        gst = await self._get(GstRegistration, payload.gst_registration_id, "gst_registration")
        if (
            gst.organization_id != organization.id
            or not gst.is_active
            or gst.effective_from > payload.quotation_date
            or (gst.effective_to and gst.effective_to < payload.quotation_date)
        ):
            raise AppError(
                422,
                "invalid_gst_registration",
                "Select an active organization GST registration effective on the quotation date.",
            )
        zone, division, authority, bill, ship = await self._addresses(payload)
        state = payload.place_of_supply_state or (ship or bill).state
        state_code = payload.place_of_supply_state_code or (ship or bill).state_code
        if not state or not state_code:
            raise AppError(
                422,
                "place_of_supply_required",
                "Place-of-supply state and state code are required.",
            )
        automatic_mode = "INTRA_STATE" if gst.state_code == state_code else "INTER_STATE"
        if payload.tax_mode and payload.tax_mode != automatic_mode:
            raise AppError(
                422,
                "tax_mode_conflict",
                "Selected tax mode conflicts with organization and place-of-supply states.",
            )
        self._validate_line_tax(payload.lines, automatic_mode)
        payment = await self._optional(PaymentTerm, payload.payment_term_id)
        terms = await self._optional(TermsConditionVersion, payload.terms_version_id)
        customer_gst = await self.repository.customer_gst(customer.id, payload.quotation_date)
        quotation = Quotation(
            quotation_number=await self.numbering.next_number("QUOTATION"),
            revision_number=0,
            created_by_user_id=actor_id,
            tax_mode=automatic_mode,
            place_of_supply_state=state,
            place_of_supply_state_code=state_code,
            organization_snapshot=snapshot(
                organization, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            organization_gst_snapshot=gst_snapshot(gst),
            customer_snapshot=snapshot(
                customer, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            customer_gst_snapshot=gst_snapshot(customer_gst) if customer_gst else None,
            zone_snapshot=snapshot(zone, ("code", "name")) if zone else None,
            division_snapshot=snapshot(division, ("code", "name")) if division else None,
            authority_snapshot=snapshot(
                authority, ("code", "name", "designation", "email", "phone")
            )
            if authority
            else None,
            bill_to_snapshot=snapshot(bill, ADDRESS_FIELDS),
            ship_to_snapshot=snapshot(ship, ADDRESS_FIELDS) if ship else None,
            place_of_supply_snapshot={
                "state": state,
                "state_code": state_code,
                "tax_mode": automatic_mode,
            },
            payment_terms_snapshot=snapshot(payment, ("code", "name", "description", "due_days"))
            if payment
            else None,
            terms_snapshot={
                "id": str(terms.id),
                "version": terms.version,
                "context": terms.terms_set.context,
                "content": terms.content,
                "effective_from": str(terms.effective_from),
            }
            if terms
            else None,
            **payload.model_dump(
                exclude={"lines", "tax_mode", "place_of_supply_state", "place_of_supply_state_code"}
            ),
        )
        quotation.lines = [
            await self._line(quotation, i, line) for i, line in enumerate(payload.lines, 1)
        ]
        self._totals(quotation, payload.round_off)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id,
            "assign_number",
            "quotation",
            quotation.id,
            new={"quotation_number": quotation.quotation_number},
        )
        self.repository.audit(
            actor_id,
            "create",
            "quotation",
            quotation.id,
            new={"revision": 0, "grand_total": str(quotation.grand_total)},
        )
        return await self.repository.get_quotation(quotation.id)

    async def update_header(self, quotation_id, payload, actor_id):
        quotation = await self._draft(quotation_id)
        old = {key: str(getattr(quotation, key)) for key in payload.model_fields_set}
        values = payload.model_dump(exclude_unset=True)
        if (
            "validity_date" in values
            and values["validity_date"]
            and values["validity_date"] < quotation.quotation_date
        ):
            raise AppError(422, "invalid_validity", "Validity date cannot precede quotation date.")
        if "payment_term_id" in values:
            payment = await self._optional(PaymentTerm, values["payment_term_id"])
            quotation.payment_terms_snapshot = (
                snapshot(payment, ("code", "name", "description", "due_days")) if payment else None
            )
        if "terms_version_id" in values:
            terms = await self._optional(TermsConditionVersion, values["terms_version_id"])
            quotation.terms_snapshot = (
                {
                    "id": str(terms.id),
                    "version": terms.version,
                    "context": terms.terms_set.context,
                    "content": terms.content,
                    "effective_from": str(terms.effective_from),
                }
                if terms
                else None
            )
        for key, value in values.items():
            setattr(quotation, key, value)
        self._totals(quotation, quotation.round_off)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id,
            "update",
            "quotation",
            quotation.id,
            old=old,
            new={key: str(getattr(quotation, key)) for key in payload.model_fields_set},
        )
        return await self.repository.get_quotation(quotation.id)

    async def add_line(self, quotation_id, payload, actor_id):
        quotation = await self._draft(quotation_id)
        self._validate_line_tax([payload], quotation.tax_mode)
        line = await self._line(
            quotation, max((x.line_number for x in quotation.lines), default=0) + 1, payload
        )
        quotation.lines.append(line)
        self._totals(quotation, quotation.round_off)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id, "add_line", "quotation", quotation.id, new={"line_number": line.line_number}
        )
        return await self.repository.get_quotation(quotation.id)

    async def update_line(self, quotation_id, line_id, payload, actor_id):
        quotation = await self._draft(quotation_id)
        old_line = next((x for x in quotation.lines if x.id == line_id), None)
        if not old_line:
            raise AppError(404, "quotation_line_not_found", "Quotation line does not exist.")
        self._validate_line_tax([payload], quotation.tax_mode)
        new_line = await self._line(quotation, old_line.line_number, payload)
        old = {
            "quantity": str(old_line.quantity),
            "rate": str(old_line.quoted_rate),
            "total": str(old_line.line_total),
        }
        for attr in new_line.__mapper__.column_attrs:
            if attr.key not in {"id", "quotation_id", "line_number"}:
                setattr(old_line, attr.key, getattr(new_line, attr.key))
        self._totals(quotation, quotation.round_off)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id,
            "update_line",
            "quotation",
            quotation.id,
            old=old,
            new={
                "quantity": str(old_line.quantity),
                "rate": str(old_line.quoted_rate),
                "total": str(old_line.line_total),
            },
        )
        return await self.repository.get_quotation(quotation.id)

    async def delete_line(self, quotation_id, line_id, actor_id):
        quotation = await self._draft(quotation_id)
        line = next((x for x in quotation.lines if x.id == line_id), None)
        if not line:
            raise AppError(404, "quotation_line_not_found", "Quotation line does not exist.")
        if len(quotation.lines) == 1:
            raise AppError(
                422, "quotation_line_required", "A quotation must retain at least one line."
            )
        quotation.lines.remove(line)
        for index, item in enumerate(sorted(quotation.lines, key=lambda x: x.line_number), 1):
            item.line_number = index
        self._totals(quotation, quotation.round_off)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id,
            "delete_line",
            "quotation",
            quotation.id,
            old={"line_number": line.line_number},
        )
        return await self.repository.get_quotation(quotation.id)

    async def transition(self, quotation_id, action, reason, actor_id, is_super):
        quotation = await self._quotation(quotation_id)
        transitions = {
            ("DRAFT", "SUBMIT"): "SUBMITTED",
            ("SUBMITTED", "APPROVE"): "APPROVED",
            ("APPROVED", "ISSUE"): "ISSUED",
            ("ISSUED", "ACCEPT"): "ACCEPTED",
            ("ISSUED", "REJECT"): "REJECTED",
            ("ISSUED", "EXPIRE"): "EXPIRED",
        }
        if action == "CANCEL" and quotation.status in {"DRAFT", "SUBMITTED", "APPROVED", "ISSUED"}:
            new = "CANCELLED"
        else:
            new = transitions.get((quotation.status, action))
        if not new:
            raise AppError(409, "invalid_quotation_transition", "Quotation action is not allowed.")
        if action in {"APPROVE", "ISSUE", "CANCEL"} and not is_super:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "APPROVE" and quotation.created_by_user_id == actor_id:
            raise AppError(403, "self_approval_denied", "The quotation creator cannot approve it.")
        old = quotation.status
        quotation.status = new
        if new == "APPROVED":
            quotation.approved_by_user_id, quotation.approved_at = actor_id, datetime.now(UTC)
        if new == "ISSUED":
            quotation.issued_at = datetime.now(UTC)
        await self.repository.save(quotation)
        self.repository.audit(
            actor_id,
            action.lower(),
            "quotation",
            quotation.id,
            {"status": old},
            {"status": new},
            reason,
        )
        return await self.repository.get_quotation(quotation.id)

    async def create_revision(self, quotation_id, reason, actor_id):
        source = await self._quotation(quotation_id)
        if not source.is_latest or source.status not in {
            "ISSUED",
            "ACCEPTED",
            "REJECTED",
            "EXPIRED",
        }:
            raise AppError(
                409,
                "revision_not_allowed",
                "Only the latest issued or concluded quotation can be revised.",
            )
        source.is_latest = False
        excluded = {
            "id",
            "revision_number",
            "previous_revision_id",
            "is_latest",
            "status",
            "approved_by_user_id",
            "approved_at",
            "issued_at",
            "created_at",
            "updated_at",
            "created_by_user_id",
        }
        values = {
            column.key: getattr(source, column.key)
            for column in source.__mapper__.column_attrs
            if column.key not in excluded
        }
        revision = Quotation(
            **values,
            revision_number=source.revision_number + 1,
            previous_revision_id=source.id,
            is_latest=True,
            status="DRAFT",
            created_by_user_id=actor_id,
            approved_by_user_id=None,
            approved_at=None,
            issued_at=None,
        )
        revision.lines = [
            QuotationLine(
                **{
                    column.key: getattr(line, column.key)
                    for column in line.__mapper__.column_attrs
                    if column.key not in {"id", "quotation_id"}
                }
            )
            for line in source.lines
        ]
        await self.repository.save(revision)
        self.repository.audit(
            actor_id,
            "create_revision",
            "quotation",
            revision.id,
            old={"source_id": str(source.id), "revision": source.revision_number},
            new={"revision": revision.revision_number},
            reason=reason,
        )
        return await self.repository.get_quotation(revision.id)

    async def _line(self, quotation, number, item):
        product = await self._optional(Product, item.product_id)
        model = await self._optional(ProductModel, item.product_model_id)
        oem = await self._optional(Party, item.oem_party_id)
        if product:
            unit = await self._get(UnitOfMeasure, product.unit_id, "unit")
            hsn = await self._optional(HsnCode, product.hsn_code_id)
            description, unit_text, hsn_text = (
                item.description or product.description,
                unit.symbol,
                item.hsn_code or (hsn.code if hsn else None),
            )
            if item.product_model_id and product.product_model_id != item.product_model_id:
                raise AppError(
                    422,
                    "invalid_product_model",
                    "Product model does not match the selected product.",
                )
        else:
            unit = await self._optional(UnitOfMeasure, item.unit_id)
            description, unit_text, hsn_text = (
                item.description,
                (unit.symbol if unit else item.unit_text),
                item.hsn_code,
            )
        if not description or not unit_text:
            raise AppError(422, "invalid_quotation_line", "Description and UOM are required.")
        if oem and not any(role.role == "OEM" for role in oem.roles):
            raise AppError(422, "invalid_oem", "Selected party is not an OEM.")
        if model:
            profile = await self.repository.get(OemProfile, model.oem_profile_id)
            if item.oem_party_id and profile.party_id != item.oem_party_id:
                raise AppError(422, "invalid_oem_model", "OEM and model do not match.")
        subtotal = money(item.quantity * item.quoted_rate)
        discount = money(subtotal * item.discount_percent / 100)
        taxable = money(subtotal - discount)
        cgst, sgst, igst = (
            money(taxable * p / 100)
            for p in (item.cgst_percent, item.sgst_percent, item.igst_percent)
        )
        return QuotationLine(
            line_number=number,
            product_id=item.product_id,
            product_model_id=item.product_model_id,
            oem_party_id=item.oem_party_id,
            description_snapshot=description,
            oem_snapshot=oem.legal_name if oem else None,
            model_snapshot=model.model_number if model else None,
            hsn_snapshot=hsn_text,
            unit_snapshot=unit_text,
            quantity=item.quantity,
            quoted_rate=item.quoted_rate,
            discount_percent=item.discount_percent,
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=taxable,
            cgst_percent=item.cgst_percent,
            sgst_percent=item.sgst_percent,
            igst_percent=item.igst_percent,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            line_total=money(taxable + cgst + sgst + igst),
            remarks=item.remarks,
        )

    def _totals(self, quotation, round_off):
        for field in (
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
        ):
            setattr(
                quotation,
                field,
                money(sum((getattr(line, field) for line in quotation.lines), Decimal("0"))),
            )
        quotation.round_off = money(round_off)
        quotation.grand_total = money(
            quotation.taxable_amount
            + quotation.cgst_amount
            + quotation.sgst_amount
            + quotation.igst_amount
            + quotation.round_off
        )
        quotation.amount_in_words = inr_amount_in_words(quotation.grand_total)

    def _validate_line_tax(self, lines, mode):
        for line in lines:
            if mode == "INTRA_STATE" and line.igst_percent:
                raise AppError(
                    422, "invalid_line_tax", "Intra-state quotation cannot include IGST."
                )
            if mode == "INTER_STATE" and (line.cgst_percent or line.sgst_percent):
                raise AppError(
                    422, "invalid_line_tax", "Inter-state quotation cannot include CGST/SGST."
                )

    async def _addresses(self, payload):
        if payload.business_scope == "RAILWAY":
            zone = await self._optional(RailwayZone, payload.railway_zone_id)
            division = await self._get(RailwayDivision, payload.railway_division_id, "division")
            authority = await self._get(RailwayAuthority, payload.railway_authority_id, "authority")
            bill = await self._get(
                RailwayAuthorityAddress, payload.bill_to_railway_address_id, "bill_to"
            )
            ship = await self._optional(RailwayAuthorityAddress, payload.ship_to_railway_address_id)
            if (
                authority.division_id != division.id
                or bill.authority_id != authority.id
                or (ship and ship.authority_id != authority.id)
                or (zone and division.zone_id != zone.id)
            ):
                raise AppError(
                    422,
                    "invalid_railway_address",
                    "Railway hierarchy/address selection is inconsistent.",
                )
            return zone, division, authority, bill, ship
        bill = await self._get(PartyAddress, payload.bill_to_party_address_id, "bill_to")
        ship = await self._optional(PartyAddress, payload.ship_to_party_address_id)
        if bill.party_id != payload.customer_party_id or (
            ship and ship.party_id != payload.customer_party_id
        ):
            raise AppError(
                422, "invalid_customer_address", "Quotation addresses must belong to the customer."
            )
        return None, None, None, bill, ship

    async def _optional(self, model, record_id):
        return await self._get(model, record_id, model.__tablename__) if record_id else None

    async def _get(self, model, record_id, name):
        record = await self.repository.get(model, record_id)
        if not record:
            raise AppError(
                422, f"invalid_{name}", f"Selected {name.replace('_', ' ')} does not exist."
            )
        return record

    async def _quotation(self, quotation_id):
        record = await self.repository.get_quotation(quotation_id)
        if not record:
            raise AppError(404, "quotation_not_found", "Quotation does not exist.")
        return record

    async def _draft(self, quotation_id):
        record = await self._quotation(quotation_id)
        if record.status != "DRAFT":
            raise AppError(409, "quotation_not_draft", "Only a draft quotation can be edited.")
        return record
