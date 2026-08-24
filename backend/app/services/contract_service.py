from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.core.errors import AppError
from app.models.contracts import LoaItem, LoaVariation, LoaVariationLine
from app.models.master_data import Loa, Project
from app.repositories.contract_repository import ContractRepository
from app.schemas.contracts import (
    ApprovedPositionLine,
    ApprovedPositionResponse,
    LoaCreate,
    LoaItemCreate,
    LoaUpdate,
    ProjectCreate,
    ProjectUpdate,
    VariationCreate,
)

MONEY = Decimal("0.01")
CONTRIBUTING_STATUSES = {"APPROVED", "APPLIED"}
TERMINAL_VARIATION_STATUSES = {"APPLIED", "REJECTED", "CANCELLED"}


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


class ContractService:
    def __init__(self, repository: ContractRepository) -> None:
        self.repository = repository

    async def list_projects(self) -> list[Project]:
        return await self.repository.list_projects()

    async def create_project(self, payload: ProjectCreate, actor_id: UUID) -> Project:
        await self._validate_customer(payload.customer_party_id)
        if payload.business_scope == "RAILWAY" and payload.railway_division_id is None:
            raise AppError(422, "railway_division_required", "Railway projects require a division.")
        project = Project(**payload.model_dump())
        project.code = project.code.upper()
        await self.repository.save(project)
        self.repository.audit(
            actor_id, "create", "project", project.id, None, {"code": project.code}
        )
        return project

    async def update_project(
        self, project_id: UUID, payload: ProjectUpdate, actor_id: UUID
    ) -> Project:
        project = await self._project(project_id)
        old = {"name": project.name, "status": project.status}
        values = payload.model_dump(exclude_unset=True)
        if "customer_party_id" in values:
            await self._validate_customer(values["customer_party_id"])
        for field, value in values.items():
            setattr(project, field, value)
        await self.repository.save(project)
        self.repository.audit(actor_id, "update", "project", project.id, old, values)
        return project

    async def list_loas(self, project_id: UUID | None = None) -> list[Loa]:
        return await self.repository.list_loas(project_id)

    async def create_loa(self, payload: LoaCreate, actor_id: UUID) -> Loa:
        await self._project(payload.project_id)
        if payload.issuing_party_id:
            await self._validate_customer(payload.issuing_party_id)
        loa = Loa(**payload.model_dump())
        await self.repository.save(loa)
        self.repository.audit(
            actor_id,
            "create",
            "loa",
            loa.id,
            None,
            {
                "loa_number": loa.loa_number,
                "original_contract_value": str(loa.original_contract_value),
            },
        )
        return loa

    async def update_loa(self, loa_id: UUID, payload: LoaUpdate, actor_id: UUID) -> Loa:
        loa = await self._loa(loa_id)
        old = {"status": loa.status, "original_contract_value": str(loa.original_contract_value)}
        values = payload.model_dump(exclude_unset=True)
        if "issuing_party_id" in values and values["issuing_party_id"]:
            await self._validate_customer(values["issuing_party_id"])
        for field, value in values.items():
            setattr(loa, field, value)
        await self.repository.save(loa)
        audited = {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in values.items()
        }
        self.repository.audit(actor_id, "update", "loa", loa.id, old, audited)
        return loa

    async def create_item(self, loa_id: UUID, payload: LoaItemCreate, actor_id: UUID) -> LoaItem:
        loa = await self._loa(loa_id)
        if loa.status in {"COMPLETED", "CLOSED"}:
            raise AppError(409, "loa_locked", "Items cannot be added to a completed or closed LOA.")
        unit = await self.repository.get_unit(payload.unit_id)
        if unit is None or not unit.is_active:
            raise AppError(422, "invalid_unit", "The selected unit is unavailable.")
        values = payload.model_dump()
        line_value = money(payload.original_approved_quantity * payload.contractual_rate)
        item = LoaItem(loa_id=loa_id, original_line_value=line_value, **values)
        await self.repository.save(item)
        self.repository.audit(
            actor_id,
            "create",
            "loa_item",
            item.id,
            None,
            {
                "quantity": str(item.original_approved_quantity),
                "rate": str(item.contractual_rate),
                "value": str(line_value),
            },
        )
        return item

    async def create_variation(
        self, loa_id: UUID, payload: VariationCreate, actor_id: UUID
    ) -> LoaVariation:
        await self._loa(loa_id)
        lines: list[LoaVariationLine] = []
        for line_payload in payload.lines:
            if line_payload.loa_item_id is None and line_payload.direction == "NEGATIVE":
                raise AppError(
                    422,
                    "negative_variation_requires_item",
                    "A standalone variation item must be positive.",
                )
            if line_payload.loa_item_id:
                item = await self.repository.get_item(line_payload.loa_item_id)
                if item is None or item.loa_id != loa_id:
                    raise AppError(
                        422, "invalid_loa_item", "Variation item does not belong to the LOA."
                    )
            await self._validate_unit(line_payload.unit_id)
            values = line_payload.model_dump()
            lines.append(
                LoaVariationLine(
                    line_value=money(line_payload.quantity * line_payload.rate), **values
                )
            )
        variation = LoaVariation(
            loa_id=loa_id,
            reference_number=payload.reference_number,
            variation_date=payload.variation_date,
            remarks=payload.remarks,
            created_by_user_id=actor_id,
            lines=lines,
        )
        await self.repository.save(variation)
        self.repository.audit(
            actor_id,
            "create",
            "loa_variation",
            variation.id,
            None,
            {"reference_number": variation.reference_number, "status": variation.status},
        )
        return await self.repository.get_variation(variation.id)

    async def transition_variation(
        self, variation_id: UUID, action: str, reason: str, actor_id: UUID
    ) -> LoaVariation:
        variation = await self._variation(variation_id)
        if variation.status in TERMINAL_VARIATION_STATUSES:
            raise AppError(409, "variation_immutable", "The variation can no longer be changed.")
        transitions = {
            ("DRAFT", "APPROVE"): "APPROVED",
            ("APPROVED", "APPLY"): "APPLIED",
            ("DRAFT", "REJECT"): "REJECTED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("APPROVED", "CANCEL"): "CANCELLED",
        }
        new_status = transitions.get((variation.status, action))
        if new_status is None:
            raise AppError(
                409, "invalid_variation_transition", "The variation action is not allowed."
            )
        if action == "APPROVE" and variation.created_by_user_id == actor_id:
            raise AppError(403, "self_approval_denied", "The variation creator cannot approve it.")
        if action == "APPROVE":
            await self._validate_nonnegative_position(variation)
        old_status = variation.status
        variation.status = new_status
        variation.decided_by_user_id = actor_id
        variation.decided_at = datetime.now(UTC)
        await self.repository.save(variation)
        self.repository.audit(
            actor_id,
            action.lower(),
            "loa_variation",
            variation.id,
            {"status": old_status},
            {"status": new_status},
            reason,
        )
        return variation

    async def approved_position(self, loa_id: UUID) -> ApprovedPositionResponse:
        await self._loa(loa_id)
        items = await self.repository.list_items(loa_id)
        variations = await self.repository.list_variations(loa_id)
        contributing = [v for v in variations if v.status in CONTRIBUTING_STATUSES]
        result: list[ApprovedPositionLine] = []
        for item in items:
            positive = sum(
                (
                    line.quantity
                    for v in contributing
                    for line in v.lines
                    if line.loa_item_id == item.id and line.direction == "POSITIVE"
                ),
                Decimal("0"),
            )
            negative = sum(
                (
                    line.quantity
                    for v in contributing
                    for line in v.lines
                    if line.loa_item_id == item.id and line.direction == "NEGATIVE"
                ),
                Decimal("0"),
            )
            current_quantity = item.original_approved_quantity + positive - negative
            variation_value = money(
                sum(
                    (
                        line.line_value if line.direction == "POSITIVE" else -line.line_value
                        for variation in contributing
                        for line in variation.lines
                        if line.loa_item_id == item.id
                    ),
                    Decimal("0"),
                )
            )
            result.append(
                ApprovedPositionLine(
                    contractual_item_id=item.id,
                    origin="ORIGINAL_LOA",
                    loa_item_id=item.id,
                    item_number=item.item_number,
                    product_id=item.product_id,
                    description=item.description,
                    hsn_code_id=item.hsn_code_id,
                    unit_id=item.unit_id,
                    original_quantity=item.original_approved_quantity,
                    positive_variation_quantity=positive,
                    negative_variation_quantity=negative,
                    current_approved_quantity=current_quantity,
                    contractual_rate=item.contractual_rate,
                    original_value=item.original_line_value,
                    variation_value=variation_value,
                    current_approved_value=money(item.original_line_value + variation_value),
                )
            )
        for variation in contributing:
            for line in variation.lines:
                if line.loa_item_id is not None:
                    continue
                result.append(
                    ApprovedPositionLine(
                        contractual_item_id=line.id,
                        origin="VARIATION",
                        loa_item_id=None,
                        originating_variation_id=variation.id,
                        originating_variation_reference=variation.reference_number,
                        item_number=variation.reference_number,
                        product_id=line.product_id,
                        description=line.description,
                        hsn_code_id=line.hsn_code_id,
                        unit_id=line.unit_id,
                        original_quantity=Decimal("0"),
                        positive_variation_quantity=line.quantity,
                        negative_variation_quantity=Decimal("0"),
                        current_approved_quantity=line.quantity,
                        contractual_rate=line.rate,
                        original_value=Decimal("0"),
                        variation_value=line.line_value,
                        current_approved_value=line.line_value,
                    )
                )
        original_total = money(sum((line.original_value for line in result), Decimal("0")))
        variation_total = money(sum((line.variation_value for line in result), Decimal("0")))
        return ApprovedPositionResponse(
            loa_id=loa_id,
            lines=result,
            original_total=original_total,
            variation_total=variation_total,
            current_approved_total=money(original_total + variation_total),
        )

    async def _validate_nonnegative_position(self, pending: LoaVariation) -> None:
        for loa_item_id in {line.loa_item_id for line in pending.lines if line.loa_item_id}:
            await self.repository.lock_item(loa_item_id)
        current = await self.approved_position(pending.loa_id)
        quantities = {line.loa_item_id: line.current_approved_quantity for line in current.lines}
        for line in pending.lines:
            if line.loa_item_id is None and line.direction == "NEGATIVE":
                raise AppError(
                    422,
                    "negative_variation_requires_item",
                    "Negative variations require an LOA item.",
                )
            if line.loa_item_id:
                delta = line.quantity if line.direction == "POSITIVE" else -line.quantity
                quantities[line.loa_item_id] += delta
        for loa_item_id in {line.loa_item_id for line in pending.lines if line.loa_item_id}:
            if quantities[loa_item_id] < 0:
                raise AppError(
                    422,
                    "negative_approved_quantity",
                    "Variation would make approved quantity negative.",
                )
            committed = await self.repository.committed_quantity(loa_item_id)
            if quantities[loa_item_id] < committed:
                raise AppError(
                    422,
                    "variation_below_committed_quantity",
                    "Variation would reduce approved quantity below existing PO commitments.",
                )

    async def _validate_customer(self, party_id: UUID) -> None:
        party = await self.repository.get_party(party_id)
        if (
            party is None
            or not party.is_active
            or not any(role.role == "CUSTOMER" for role in party.roles)
        ):
            raise AppError(422, "invalid_customer", "The selected party is not an active customer.")

    async def _validate_unit(self, unit_id: UUID) -> None:
        unit = await self.repository.get_unit(unit_id)
        if unit is None or not unit.is_active:
            raise AppError(422, "invalid_unit", "The selected unit is unavailable.")

    async def _project(self, project_id: UUID) -> Project:
        project = await self.repository.get_project(project_id)
        if project is None:
            raise AppError(404, "project_not_found", "Project does not exist.")
        return project

    async def _loa(self, loa_id: UUID) -> Loa:
        loa = await self.repository.get_loa(loa_id)
        if loa is None:
            raise AppError(404, "loa_not_found", "LOA does not exist.")
        return loa

    async def _variation(self, variation_id: UUID) -> LoaVariation:
        variation = await self.repository.get_variation(variation_id)
        if variation is None:
            raise AppError(404, "variation_not_found", "Variation does not exist.")
        return variation
