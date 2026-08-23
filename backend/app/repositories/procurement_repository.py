from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.contracts import LoaItem, LoaVariation, LoaVariationLine
from app.models.master_data import (
    HsnCode,
    Organization,
    OrganizationAddress,
    Party,
    PartyAddress,
    PaymentTerm,
    Product,
    TermsConditionVersion,
    UnitOfMeasure,
)
from app.models.procurement import (
    NumberingSeries,
    ProcurementRequirement,
    ProcurementRequirementLine,
    PurchaseOrder,
    PurchaseOrderLine,
)


class ProcurementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_number(self, document_type: str) -> str:
        series = await self.session.scalar(
            select(NumberingSeries)
            .where(NumberingSeries.document_type == document_type)
            .with_for_update()
        )
        if series is None:
            raise RuntimeError(f"Missing numbering series: {document_type}")
        value = f"{series.prefix}{series.next_number:0{series.padding}d}"
        series.next_number += 1
        await self.session.flush()
        return value

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_requirement(self, record_id: UUID):
        return await self.session.scalar(
            select(ProcurementRequirement)
            .options(selectinload(ProcurementRequirement.lines))
            .where(ProcurementRequirement.id == record_id)
        )

    async def list_requirements(self):
        result = await self.session.scalars(
            select(ProcurementRequirement)
            .options(selectinload(ProcurementRequirement.lines))
            .order_by(ProcurementRequirement.created_at.desc())
        )
        return list(result.unique())

    async def get_po(self, record_id: UUID):
        return await self.session.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.id == record_id)
        )

    async def list_pos(self):
        result = await self.session.scalars(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .order_by(PurchaseOrder.created_at.desc())
        )
        return list(result.unique())

    async def get(self, model, record_id: UUID):
        statement = select(model).where(model.id == record_id)
        if model is Party:
            statement = statement.options(selectinload(Party.roles), selectinload(Party.addresses))
        if model is TermsConditionVersion:
            statement = statement.options(selectinload(TermsConditionVersion.terms_set))
        return await self.session.scalar(statement)

    async def get_variation_line(self, line_id: UUID):
        return await self.session.scalar(
            select(LoaVariationLine)
            .options(selectinload(LoaVariationLine.variation))
            .join(LoaVariation)
            .where(
                LoaVariationLine.id == line_id,
                LoaVariation.status.in_(("APPROVED", "APPLIED")),
            )
        )

    async def committed_quantity(
        self,
        *,
        loa_item_id: UUID | None,
        variation_line_id: UUID | None,
        exclude_po_id: UUID | None = None,
    ):
        statement = (
            select(func.coalesce(func.sum(PurchaseOrderLine.ordered_quantity), 0))
            .join(PurchaseOrder)
            .where(
                PurchaseOrder.status.in_(("APPROVED", "ISSUED", "PARTIALLY_FULFILLED", "FULFILLED"))
            )
        )
        if loa_item_id:
            statement = statement.where(PurchaseOrderLine.loa_item_id == loa_item_id)
        else:
            statement = statement.where(PurchaseOrderLine.variation_line_id == variation_line_id)
        if exclude_po_id:
            statement = statement.where(PurchaseOrder.id != exclude_po_id)
        return await self.session.scalar(statement)

    async def lock_contract_source(
        self, *, loa_item_id: UUID | None, variation_line_id: UUID | None
    ) -> None:
        model = LoaItem if loa_item_id else LoaVariationLine
        source_id = loa_item_id or variation_line_id
        await self.session.scalar(select(model.id).where(model.id == source_id).with_for_update())

    def audit(
        self,
        actor_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old=None,
        new=None,
        reason=None,
    ):
        self.session.add(
            AuditLog(
                actor_user_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                old_value=old,
                new_value=new,
                reason=reason,
            )
        )


MASTER_MODELS = {
    "organization": Organization,
    "organization_address": OrganizationAddress,
    "party": Party,
    "party_address": PartyAddress,
    "payment_term": PaymentTerm,
    "terms_version": TermsConditionVersion,
    "product": Product,
    "unit": UnitOfMeasure,
    "hsn": HsnCode,
    "requirement_line": ProcurementRequirementLine,
}
