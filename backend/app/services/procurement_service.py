from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.core.errors import AppError
from app.models.contracts import LoaItem
from app.models.master_data import Loa, Project
from app.models.procurement import (
    ProcurementRequirement,
    ProcurementRequirementLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.repositories.procurement_repository import MASTER_MODELS, ProcurementRepository
from app.schemas.procurement import (
    CommitmentResponse,
    PoLineCreate,
    PurchaseOrderCreate,
    RequirementCreate,
    RequirementUpdate,
)
from app.services.contract_service import ContractService

MONEY = Decimal("0.01")
COMMITTED_PO_STATUSES = frozenset({"APPROVED", "ISSUED", "PARTIALLY_FULFILLED", "FULFILLED"})


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def snapshot(record, fields: tuple[str, ...]) -> dict:
    return {field: getattr(record, field) for field in fields}


class ProcurementService:
    def __init__(
        self, repository: ProcurementRepository, contract_service: ContractService
    ) -> None:
        self.repository = repository
        self.contract_service = contract_service

    async def create_requirement(self, payload: RequirementCreate, actor_id: UUID):
        project = await self._get(Project, payload.project_id, "project")
        await self._validate_loa(payload.loa_id, project.id)
        lines = []
        for number, item in enumerate(payload.lines, 1):
            await self._validate_contract_source(
                payload.loa_id, item.loa_item_id, item.variation_line_id
            )
            await self._get(MASTER_MODELS["unit"], item.unit_id, "unit")
            lines.append(ProcurementRequirementLine(line_number=number, **item.model_dump()))
        requirement = ProcurementRequirement(
            requirement_number=await self.repository.next_number("PROCUREMENT_REQUIREMENT"),
            requested_by_user_id=actor_id,
            lines=lines,
            **payload.model_dump(exclude={"lines"}),
        )
        await self.repository.save(requirement)
        self.repository.audit(
            actor_id,
            "create",
            "procurement_requirement",
            requirement.id,
            new={"requirement_number": requirement.requirement_number},
        )
        return await self.repository.get_requirement(requirement.id)

    async def create_po(self, payload: PurchaseOrderCreate, actor_id: UUID):
        project = await self._get(Project, payload.project_id, "project")
        await self._validate_loa(payload.loa_id, project.id)
        vendor = await self._get(MASTER_MODELS["party"], payload.vendor_party_id, "vendor")
        if not vendor.is_active or not any(role.role == "VENDOR" for role in vendor.roles):
            raise AppError(422, "invalid_vendor", "The selected party is not an active vendor.")
        organization = await self._get(
            MASTER_MODELS["organization"], payload.organization_id, "organization"
        )
        billing = await self._get(
            MASTER_MODELS["organization_address"],
            payload.billing_organization_address_id,
            "billing_address",
        )
        if billing.organization_id != organization.id or billing.address_type not in {
            "BILL_TO",
            "REGISTERED",
            "OFFICE",
        }:
            raise AppError(
                422,
                "invalid_billing_address",
                "Billing address does not belong to the buyer organization.",
            )
        shipping = await self._shipping_address(payload, organization.id)
        payment_term = await self._optional("payment_term", payload.payment_term_id)
        terms = await self._optional("terms_version", payload.terms_version_id)
        if terms and terms.terms_set.context not in {"PURCHASE", "GENERAL"}:
            raise AppError(422, "invalid_terms_context", "Select PURCHASE or GENERAL terms.")
        po = PurchaseOrder(
            po_number=await self.repository.next_number("PURCHASE_ORDER"),
            created_by_user_id=actor_id,
            vendor_snapshot=snapshot(
                vendor, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            organization_snapshot=snapshot(
                organization, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            billing_address_snapshot=self._address_snapshot(billing),
            shipping_address_snapshot=self._address_snapshot(shipping),
            payment_terms_snapshot=snapshot(
                payment_term, ("code", "name", "description", "due_days")
            )
            if payment_term
            else None,
            terms_snapshot={"id": str(terms.id), "version": terms.version, "content": terms.content}
            if terms
            else None,
            **payload.model_dump(exclude={"lines"}),
        )
        po.lines = [
            await self._build_po_line(po, number, item)
            for number, item in enumerate(payload.lines, 1)
        ]
        self._set_totals(po, payload.round_off)
        await self.repository.save(po)
        self.repository.audit(
            actor_id, "assign_number", "purchase_order", po.id, new={"po_number": po.po_number}
        )
        self.repository.audit(
            actor_id, "create", "purchase_order", po.id, new={"grand_total": str(po.grand_total)}
        )
        return await self.repository.get_po(po.id)

    async def transition_requirement(
        self, requirement_id: UUID, action: str, reason: str, actor_id: UUID
    ):
        record = await self.repository.get_requirement(requirement_id)
        if record is None:
            raise AppError(404, "requirement_not_found", "Procurement requirement does not exist.")
        transitions = {
            ("DRAFT", "SUBMIT"): "SUBMITTED",
            ("SUBMITTED", "APPROVE"): "APPROVED",
            ("SUBMITTED", "REJECT"): "REJECTED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("SUBMITTED", "CANCEL"): "CANCELLED",
        }
        new_status = transitions.get((record.status, action))
        if not new_status:
            raise AppError(
                409, "invalid_requirement_transition", "Requirement action is not allowed."
            )
        old = record.status
        record.status = new_status
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            action.lower(),
            "procurement_requirement",
            record.id,
            {"status": old},
            {"status": new_status},
            reason,
        )
        return await self.repository.get_requirement(record.id)

    async def update_requirement(
        self, requirement_id: UUID, payload: RequirementUpdate, actor_id: UUID
    ):
        record = await self.repository.get_requirement(requirement_id)
        if record is None:
            raise AppError(404, "requirement_not_found", "Procurement requirement does not exist.")
        if record.status != "DRAFT":
            raise AppError(409, "requirement_immutable", "Only draft requirements can be edited.")
        values = payload.model_dump(exclude_unset=True)
        old = {key: str(getattr(record, key)) if getattr(record, key) else None for key in values}
        for key, value in values.items():
            setattr(record, key, value)
        await self.repository.save(record)
        self.repository.audit(
            actor_id,
            "update",
            "procurement_requirement",
            record.id,
            old,
            {key: str(value) if value else None for key, value in values.items()},
        )
        return await self.repository.get_requirement(record.id)

    async def update_po_line(
        self, po_id: UUID, line_id: UUID, payload: PoLineCreate, actor_id: UUID
    ):
        po = await self.repository.get_po(po_id)
        if po is None:
            raise AppError(404, "purchase_order_not_found", "Purchase order does not exist.")
        if po.status != "DRAFT":
            raise AppError(409, "purchase_order_immutable", "Only draft PO lines can be edited.")
        line = next((candidate for candidate in po.lines if candidate.id == line_id), None)
        if line is None:
            raise AppError(404, "purchase_order_line_not_found", "PO line does not exist.")
        old = {
            "ordered_quantity": str(line.ordered_quantity),
            "unit_rate": str(line.unit_rate),
            "line_total": str(line.line_total),
        }
        calculated = await self._build_po_line(po, line.line_number, payload)
        excluded = {"id", "purchase_order_id", "purchase_order", "line_number"}
        for column in calculated.__mapper__.column_attrs:
            if column.key not in excluded:
                setattr(line, column.key, getattr(calculated, column.key))
        self._set_totals(po, po.round_off)
        await self.repository.save(po)
        self.repository.audit(
            actor_id,
            "update_line",
            "purchase_order_line",
            line.id,
            old,
            {
                "ordered_quantity": str(line.ordered_quantity),
                "unit_rate": str(line.unit_rate),
                "line_total": str(line.line_total),
            },
        )
        return await self.repository.get_po(po.id)

    async def transition_po(
        self, po_id: UUID, action: str, reason: str, actor_id: UUID, is_super_admin: bool
    ):
        po = await self.repository.get_po(po_id)
        if po is None:
            raise AppError(404, "purchase_order_not_found", "Purchase order does not exist.")
        transitions = {
            ("DRAFT", "SUBMIT"): "SUBMITTED",
            ("SUBMITTED", "APPROVE"): "APPROVED",
            ("APPROVED", "ISSUE"): "ISSUED",
            ("SUBMITTED", "REJECT"): "REJECTED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("SUBMITTED", "CANCEL"): "CANCELLED",
            ("APPROVED", "CANCEL"): "CANCELLED",
        }
        new_status = transitions.get((po.status, action))
        if not new_status:
            raise AppError(409, "invalid_po_transition", "Purchase order action is not allowed.")
        if action in {"APPROVE", "ISSUE"} and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "REJECT" and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "CANCEL" and po.status == "APPROVED" and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "APPROVE" and po.created_by_user_id == actor_id:
            raise AppError(403, "self_approval_denied", "The PO creator cannot approve it.")
        if action == "APPROVE":
            await self._validate_po_commitments(po)
            po.approved_by_user_id = actor_id
            po.approved_at = datetime.now(UTC)
        if action == "ISSUE":
            po.issued_at = datetime.now(UTC)
        old = po.status
        po.status = new_status
        await self.repository.save(po)
        self.repository.audit(
            actor_id,
            action.lower(),
            "purchase_order",
            po.id,
            {"status": old},
            {"status": new_status},
            reason,
        )
        return await self.repository.get_po(po.id)

    async def commitments(self, loa_id: UUID):
        position = await self.contract_service.approved_position(loa_id)
        result = []
        for item in position.lines:
            committed = Decimal(
                await self.repository.committed_quantity(
                    loa_item_id=item.loa_item_id,
                    variation_line_id=item.contractual_item_id
                    if item.origin == "VARIATION"
                    else None,
                )
            )
            result.append(
                CommitmentResponse(
                    contractual_item_id=item.contractual_item_id,
                    origin=item.origin,
                    approved_quantity=item.current_approved_quantity,
                    committed_quantity=committed,
                    remaining_quantity=item.current_approved_quantity - committed,
                )
            )
        return result

    async def _build_po_line(self, po, number, item):
        await self._validate_contract_source(po.loa_id, item.loa_item_id, item.variation_line_id)
        unit = await self._get(MASTER_MODELS["unit"], item.unit_id, "unit")
        hsn = await self._optional("hsn", item.hsn_code_id)
        if po.tax_mode == "INTRA_STATE" and item.igst_percent != 0:
            raise AppError(
                422, "invalid_tax_components", "Intra-state PO lines cannot contain IGST."
            )
        if po.tax_mode == "INTER_STATE" and (item.cgst_percent != 0 or item.sgst_percent != 0):
            raise AppError(
                422, "invalid_tax_components", "Inter-state PO lines cannot contain CGST or SGST."
            )
        subtotal = money(item.ordered_quantity * item.unit_rate)
        discount = money(subtotal * item.discount_percent / Decimal("100"))
        taxable = money(subtotal - discount)
        cgst = money(taxable * item.cgst_percent / Decimal("100"))
        sgst = money(taxable * item.sgst_percent / Decimal("100"))
        igst = money(taxable * item.igst_percent / Decimal("100"))
        return PurchaseOrderLine(
            line_number=number,
            hsn_code=hsn.code if hsn else None,
            unit_snapshot=f"{unit.code} - {unit.symbol}",
            subtotal=subtotal,
            discount_amount=discount,
            taxable_amount=taxable,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            line_total=money(taxable + cgst + sgst + igst),
            **item.model_dump(exclude={"hsn_code_id"}),
        )

    def _set_totals(self, po, round_off):
        po.subtotal = money(sum((line.subtotal for line in po.lines), Decimal("0")))
        po.discount_amount = money(sum((line.discount_amount for line in po.lines), Decimal("0")))
        po.taxable_amount = money(sum((line.taxable_amount for line in po.lines), Decimal("0")))
        po.cgst_amount = money(sum((line.cgst_amount for line in po.lines), Decimal("0")))
        po.sgst_amount = money(sum((line.sgst_amount for line in po.lines), Decimal("0")))
        po.igst_amount = money(sum((line.igst_amount for line in po.lines), Decimal("0")))
        po.round_off = money(round_off)
        po.grand_total = money(
            sum((line.line_total for line in po.lines), Decimal("0")) + po.round_off
        )

    async def _validate_po_commitments(self, po):
        for line in po.lines:
            if not line.loa_item_id and not line.variation_line_id:
                continue
            await self.repository.lock_contract_source(
                loa_item_id=line.loa_item_id, variation_line_id=line.variation_line_id
            )
            approved = await self._approved_quantity(
                po.loa_id, line.loa_item_id, line.variation_line_id
            )
            committed = Decimal(
                await self.repository.committed_quantity(
                    loa_item_id=line.loa_item_id,
                    variation_line_id=line.variation_line_id,
                    exclude_po_id=po.id,
                )
            )
            same_po = sum(
                (
                    candidate.ordered_quantity
                    for candidate in po.lines
                    if candidate.loa_item_id == line.loa_item_id
                    and candidate.variation_line_id == line.variation_line_id
                ),
                Decimal("0"),
            )
            if committed + same_po > approved:
                raise AppError(
                    422,
                    "contract_quantity_exceeded",
                    "PO quantity exceeds the remaining approved contractual quantity.",
                )

    async def _approved_quantity(self, loa_id, loa_item_id, variation_line_id):
        if loa_id is None:
            raise AppError(422, "loa_required", "Contract-linked lines require an LOA.")
        position = await self.contract_service.approved_position(loa_id)
        target = variation_line_id or loa_item_id
        line = next(
            (entry for entry in position.lines if entry.contractual_item_id == target), None
        )
        if line is None:
            raise AppError(
                422,
                "invalid_contract_source",
                "Contractual item is not in the current approved position.",
            )
        return line.current_approved_quantity

    async def _validate_contract_source(self, loa_id, loa_item_id, variation_line_id):
        if loa_item_id:
            item = await self._get(LoaItem, loa_item_id, "loa_item")
            if loa_id is None or item.loa_id != loa_id:
                raise AppError(
                    422, "invalid_contract_source", "LOA item does not belong to the selected LOA."
                )
        if variation_line_id:
            line = await self.repository.get_variation_line(variation_line_id)
            if (
                line is None
                or line.loa_item_id is not None
                or line.direction != "POSITIVE"
                or loa_id is None
                or line.variation.loa_id != loa_id
            ):
                raise AppError(
                    422,
                    "invalid_contract_source",
                    "Variation item is not an approved standalone item for the selected LOA.",
                )

    async def _validate_loa(self, loa_id, project_id):
        if loa_id:
            loa = await self._get(Loa, loa_id, "loa")
            if loa.project_id != project_id:
                raise AppError(422, "invalid_loa", "LOA does not belong to the selected project.")

    async def _shipping_address(self, payload, organization_id):
        if payload.ship_to_organization_address_id:
            address = await self._get(
                MASTER_MODELS["organization_address"],
                payload.ship_to_organization_address_id,
                "shipping_address",
            )
            if address.organization_id != organization_id or address.address_type != "SHIP_TO":
                raise AppError(
                    422,
                    "invalid_shipping_address",
                    "Select a saved SHIP_TO address for the buyer organization.",
                )
            return address
        address = await self._get(
            MASTER_MODELS["party_address"], payload.ship_to_party_address_id, "shipping_address"
        )
        if address.address_type not in {"SHIP_TO", "CONSIGNEE"}:
            raise AppError(
                422, "invalid_shipping_address", "Select a saved party shipping address."
            )
        return address

    async def _optional(self, kind, record_id):
        return await self._get(MASTER_MODELS[kind], record_id, kind) if record_id else None

    async def _get(self, model, record_id, name):
        record = await self.repository.get(model, record_id)
        if record is None:
            raise AppError(
                422, f"invalid_{name}", f"Selected {name.replace('_', ' ')} does not exist."
            )
        return record

    @staticmethod
    def _address_snapshot(address):
        return snapshot(
            address,
            (
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
            ),
        )
