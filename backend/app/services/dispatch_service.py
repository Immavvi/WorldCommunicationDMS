from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.models.dispatch import ChallanReceiptAllocation, SupplyChallan, SupplyChallanLine
from app.models.master_data import (
    Loa,
    OrganizationAddress,
    Party,
    PartyAddress,
    Project,
    RailwayAuthority,
    RailwayAuthorityAddress,
    RailwayDivision,
)
from app.repositories.dispatch_repository import DispatchRepository
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.dispatch import AcknowledgementCreate, ChallanCreate, DispatchAvailability
from app.services.contract_service import ContractService

COUNTED_CHALLAN_STATUSES = frozenset({"DISPATCHED", "DELIVERED", "ACKNOWLEDGED"})


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


class DispatchService:
    def __init__(
        self,
        repository: DispatchRepository,
        procurement_repository: ProcurementRepository,
        contract_service: ContractService,
    ):
        self.repository = repository
        self.procurement_repository = procurement_repository
        self.contract_service = contract_service

    async def availability(self, project_id: UUID | None = None):
        result = []
        for receipt_line, receipt, po_line in await self.repository.verified_receipt_lines(
            project_id
        ):
            allocated = Decimal(await self.repository.allocated_receipt_quantity(receipt_line.id))
            contract_id = po_line.variation_line_id or po_line.loa_item_id
            contract_origin = (
                "VARIATION"
                if po_line.variation_line_id
                else "ORIGINAL_LOA"
                if po_line.loa_item_id
                else None
            )
            approved = None
            dispatched_contract = Decimal("0")
            remaining_contract = None
            if contract_id and receipt.loa_id:
                position = await self.contract_service.approved_position(receipt.loa_id)
                contract = next(
                    (line for line in position.lines if line.contractual_item_id == contract_id),
                    None,
                )
                if contract:
                    approved = contract.current_approved_quantity
                    dispatched_contract = Decimal(
                        await self.repository.dispatched_contract_quantity(
                            po_line.loa_item_id, po_line.variation_line_id
                        )
                    )
                    remaining_contract = approved - dispatched_contract
            result.append(
                DispatchAvailability(
                    material_receipt_line_id=receipt_line.id,
                    description=receipt_line.description_snapshot,
                    unit=receipt_line.unit_snapshot,
                    contractual_item_id=contract_id,
                    contract_origin=contract_origin,
                    verified_accepted_quantity=receipt_line.quantity_accepted,
                    allocated_dispatched_quantity=allocated,
                    available_quantity=receipt_line.quantity_accepted - allocated,
                    approved_contract_quantity=approved,
                    previously_dispatched_contract_quantity=dispatched_contract,
                    remaining_contract_quantity=remaining_contract,
                )
            )
        return result

    async def create(self, payload: ChallanCreate, actor_id: UUID):
        project = await self._get(Project, payload.project_id, "project")
        if (
            project.business_scope != payload.business_scope
            or project.customer_party_id != payload.customer_party_id
        ):
            raise AppError(
                422, "invalid_project_context", "Challan scope/customer must match the project."
            )
        customer = await self._get(Party, payload.customer_party_id, "customer")
        if not customer.is_active or not any(role.role == "CUSTOMER" for role in customer.roles):
            raise AppError(422, "invalid_customer", "Selected party is not an active customer.")
        if payload.loa_id:
            loa = await self._get(Loa, payload.loa_id, "loa")
            if loa.project_id != project.id:
                raise AppError(422, "invalid_loa", "LOA does not belong to the project.")
        if payload.bill_to_authority_id:
            bill_to = await self._get(
                RailwayAuthority, payload.bill_to_authority_id, "bill_to_authority"
            )
            if not any(role.role == "BILL_TO" for role in bill_to.roles):
                raise AppError(
                    422,
                    "invalid_bill_to_authority",
                    "Selected Railway authority does not have the BILL_TO role.",
                )
        division, consignee, delivery = await self._destination(payload)
        dispatch_from = await self._get(
            OrganizationAddress, payload.dispatch_from_address_id, "dispatch_from"
        )
        lines = [
            await self._build_line(payload, number, line)
            for number, line in enumerate(payload.lines, 1)
        ]
        challan = SupplyChallan(
            challan_number=await self.procurement_repository.next_number("SUPPLY_CHALLAN"),
            created_by_user_id=actor_id,
            customer_snapshot=snapshot(
                customer, ("code", "legal_name", "trade_name", "email", "phone")
            ),
            division_snapshot=snapshot(division, ("code", "name")) if division else None,
            consignee_snapshot=snapshot(
                consignee, ("code", "name", "designation", "email", "phone")
            )
            if consignee
            else None,
            delivery_address_snapshot=snapshot(delivery, ADDRESS_FIELDS),
            dispatch_from_snapshot=snapshot(dispatch_from, ADDRESS_FIELDS),
            organization_snapshot=snapshot(
                dispatch_from.organization,
                ("code", "legal_name", "trade_name", "pan", "email", "phone"),
            ),
            lines=lines,
            **payload.model_dump(exclude={"lines"}),
        )
        await self.repository.save(challan)
        self.repository.audit(
            actor_id,
            "assign_number",
            "supply_challan",
            challan.id,
            new={"challan_number": challan.challan_number},
        )
        self.repository.audit(
            actor_id,
            "create",
            "supply_challan",
            challan.id,
            new={"business_scope": challan.business_scope},
        )
        for line in challan.lines:
            self.repository.audit(
                actor_id,
                "create",
                "supply_challan_line",
                line.id,
                new={
                    "quantity": str(line.dispatched_quantity),
                    "allocations": [
                        {
                            "receipt_line_id": str(a.material_receipt_line_id),
                            "quantity": str(a.allocated_quantity),
                        }
                        for a in line.allocations
                    ],
                },
            )
        return await self.repository.get_challan(challan.id)

    async def transition(self, challan_id, action, reason, actor_id, is_super_admin):
        challan = await self._challan(challan_id)
        transitions = {
            ("DRAFT", "READY"): "READY",
            ("READY", "DISPATCH"): "DISPATCHED",
            ("DISPATCHED", "DELIVER"): "DELIVERED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("READY", "CANCEL"): "CANCELLED",
            ("DISPATCHED", "CANCEL"): "CANCELLED",
            ("DELIVERED", "CANCEL"): "CANCELLED",
            ("ACKNOWLEDGED", "CANCEL"): "CANCELLED",
        }
        new_status = transitions.get((challan.status, action))
        if not new_status:
            raise AppError(409, "invalid_challan_transition", "Challan action is not allowed.")
        if action == "CANCEL" and challan.status in COUNTED_CHALLAN_STATUSES and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "DISPATCH":
            await self._validate_dispatch(challan)
            challan.dispatched_at = datetime.now(UTC)
        if action == "DELIVER":
            challan.delivered_at = datetime.now(UTC)
        old = challan.status
        challan.status = new_status
        await self.repository.save(challan)
        self.repository.audit(
            actor_id,
            action.lower(),
            "supply_challan",
            challan.id,
            {"status": old},
            {"status": new_status},
            reason,
        )
        return await self.repository.get_challan(challan.id)

    async def update_line(self, challan_id, line_id, payload, actor_id):
        challan = await self._challan(challan_id)
        if challan.status != "DRAFT":
            raise AppError(409, "challan_not_draft", "Only draft Challans can be edited.")
        existing = next((line for line in challan.lines if line.id == line_id), None)
        if existing is None:
            raise AppError(404, "challan_line_not_found", "Challan line does not exist.")
        old = {
            "quantity": str(existing.dispatched_quantity),
            "allocations": [
                {
                    "receipt_line_id": str(item.material_receipt_line_id),
                    "quantity": str(item.allocated_quantity),
                }
                for item in existing.allocations
            ],
        }
        replacement = await self._build_line(
            challan,
            existing.line_number,
            payload,
        )
        for field in (
            "loa_item_id",
            "variation_line_id",
            "product_id",
            "description_snapshot",
            "hsn_snapshot",
            "unit_snapshot",
            "dispatched_quantity",
            "remarks",
        ):
            setattr(existing, field, getattr(replacement, field))
        existing.allocations.clear()
        await self.repository.session.flush()
        existing.allocations = [
            ChallanReceiptAllocation(**item.model_dump()) for item in payload.allocations
        ]
        await self.repository.save(challan)
        self.repository.audit(
            actor_id,
            "update",
            "supply_challan_line",
            existing.id,
            old,
            {"quantity": str(existing.dispatched_quantity)},
        )
        return await self.repository.get_challan(challan.id)

    async def acknowledge(self, challan_id: UUID, payload: AcknowledgementCreate, actor_id: UUID):
        challan = await self._challan(challan_id)
        if challan.status != "DELIVERED":
            raise AppError(
                409, "challan_not_delivered", "Only delivered Challans can be acknowledged."
            )
        challan.status = "ACKNOWLEDGED"
        challan.acknowledged_at = datetime.now(UTC)
        for key, value in payload.model_dump().items():
            setattr(challan, key, value)
        await self.repository.save(challan)
        self.repository.audit(
            actor_id,
            "acknowledge",
            "supply_challan",
            challan.id,
            {"status": "DELIVERED"},
            {
                "status": "ACKNOWLEDGED",
                **{
                    k: str(v) if k == "acknowledged_date" else v
                    for k, v in payload.model_dump().items()
                },
            },
            "Customer/Railway acknowledgement recorded",
        )
        return await self.repository.get_challan(challan.id)

    async def _build_line(self, payload, number, line_payload):
        contexts = []
        for allocation in line_payload.allocations:
            row = (
                await self.repository.receipt_line_context(allocation.material_receipt_line_id)
            ).first()
            if row is None:
                raise AppError(422, "invalid_receipt_line", "Receipt allocation does not exist.")
            receipt_line, receipt, po_line, _ = row
            if receipt.status != "VERIFIED" or receipt.project_id != payload.project_id:
                raise AppError(
                    422,
                    "invalid_receipt_line",
                    "Only verified material for this project can be allocated.",
                )
            contexts.append((receipt_line, po_line, allocation))
        first_receipt, first_po_line, _ = contexts[0]
        identity = (
            first_po_line.product_id,
            first_po_line.loa_item_id,
            first_po_line.variation_line_id,
            first_receipt.description_snapshot,
            first_receipt.unit_snapshot,
        )
        if any(
            (
                p.product_id,
                p.loa_item_id,
                p.variation_line_id,
                r.description_snapshot,
                r.unit_snapshot,
            )
            != identity
            for r, p, _ in contexts
        ):
            raise AppError(
                422,
                "mixed_allocation_identity",
                "One Challan line cannot mix different material or contractual items.",
            )
        return SupplyChallanLine(
            line_number=number,
            loa_item_id=first_po_line.loa_item_id,
            variation_line_id=first_po_line.variation_line_id,
            product_id=first_po_line.product_id,
            description_snapshot=first_receipt.description_snapshot,
            hsn_snapshot=first_po_line.hsn_code,
            unit_snapshot=first_receipt.unit_snapshot,
            dispatched_quantity=line_payload.dispatched_quantity,
            remarks=line_payload.remarks,
            allocations=[
                ChallanReceiptAllocation(**item.model_dump()) for item in line_payload.allocations
            ],
        )

    async def _validate_dispatch(self, challan):
        allocation_ids = [
            a.material_receipt_line_id for line in challan.lines for a in line.allocations
        ]
        await self.repository.lock_receipt_lines(allocation_ids)
        receipt_totals = defaultdict(lambda: Decimal("0"))
        contract_totals = defaultdict(lambda: Decimal("0"))
        for line in challan.lines:
            for allocation in line.allocations:
                receipt_totals[allocation.material_receipt_line_id] += allocation.allocated_quantity
            source = line.variation_line_id or line.loa_item_id
            if source:
                contract_totals[source] += line.dispatched_quantity
        for receipt_line_id, requested in receipt_totals.items():
            row = (await self.repository.receipt_line_context(receipt_line_id)).first()
            receipt_line, receipt, _, _ = row
            allocated = Decimal(
                await self.repository.allocated_receipt_quantity(receipt_line.id, challan.id)
            )
            if (
                receipt.status != "VERIFIED"
                or allocated + requested > receipt_line.quantity_accepted
            ):
                raise AppError(
                    422,
                    "dispatch_quantity_exceeded",
                    "Dispatch exceeds verified available material.",
                )
        validated_contracts = set()
        for line in challan.lines:
            if line.loa_item_id or line.variation_line_id:
                if challan.loa_id is None:
                    raise AppError(
                        422,
                        "loa_required",
                        "Contract-linked dispatch material requires an LOA.",
                    )
                await self.procurement_repository.lock_contract_source(
                    loa_item_id=line.loa_item_id, variation_line_id=line.variation_line_id
                )
                position = await self.contract_service.approved_position(challan.loa_id)
                source = line.variation_line_id or line.loa_item_id
                if source in validated_contracts:
                    continue
                validated_contracts.add(source)
                approved = next(
                    (
                        item.current_approved_quantity
                        for item in position.lines
                        if item.contractual_item_id == source
                    ),
                    None,
                )
                previous = Decimal(
                    await self.repository.dispatched_contract_quantity(
                        line.loa_item_id, line.variation_line_id, challan.id
                    )
                )
                if approved is None or previous + contract_totals[source] > approved:
                    raise AppError(
                        422,
                        "contract_dispatch_exceeded",
                        "Dispatch exceeds current approved contract quantity.",
                    )

    async def _destination(self, payload):
        if payload.business_scope == "RAILWAY":
            division = await self._get(
                RailwayDivision, payload.railway_division_id, "railway_division"
            )
            consignee = await self._get(
                RailwayAuthority, payload.consignee_authority_id, "consignee"
            )
            if consignee.division_id != division.id or not any(
                role.role == "CONSIGNEE" for role in consignee.roles
            ):
                raise AppError(
                    422, "invalid_consignee", "Select a consignee for the Railway division."
                )
            delivery = await self._get(
                RailwayAuthorityAddress, payload.ship_to_railway_address_id, "railway_ship_to"
            )
            if delivery.authority_id != consignee.id:
                raise AppError(
                    422,
                    "invalid_delivery_address",
                    "Railway delivery address must belong to the consignee.",
                )
            return division, consignee, delivery
        return (
            None,
            None,
            await self._get(PartyAddress, payload.ship_to_party_address_id, "party_ship_to"),
        )

    async def _get(self, model, record_id, name):
        record = await self.repository.get(model, record_id)
        if record is None:
            raise AppError(
                422, f"invalid_{name}", f"Selected {name.replace('_', ' ')} does not exist."
            )
        return record

    async def _challan(self, challan_id):
        record = await self.repository.get_challan(challan_id)
        if record is None:
            raise AppError(404, "challan_not_found", "Supply Challan does not exist.")
        return record
