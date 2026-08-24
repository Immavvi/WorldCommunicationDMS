from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.contracts import LoaItem, LoaVariation
from app.models.master_data import Loa, Party, Project, UnitOfMeasure
from app.models.procurement import PurchaseOrder, PurchaseOrderLine


class ContractRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        mapped = {attribute.key for attribute in record.__mapper__.column_attrs}
        timestamps = [name for name in ("created_at", "updated_at") if name in mapped]
        if timestamps:
            await self.session.refresh(record, attribute_names=timestamps)
        return record

    async def get_project(self, project_id: UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def list_projects(self) -> list[Project]:
        return list(await self.session.scalars(select(Project).order_by(Project.code)))

    async def get_loa(self, loa_id: UUID) -> Loa | None:
        return await self.session.get(Loa, loa_id)

    async def list_loas(self, project_id: UUID | None = None) -> list[Loa]:
        statement = select(Loa).order_by(Loa.loa_date.desc())
        if project_id:
            statement = statement.where(Loa.project_id == project_id)
        return list(await self.session.scalars(statement))

    async def get_party(self, party_id: UUID) -> Party | None:
        return await self.session.scalar(
            select(Party).options(selectinload(Party.roles)).where(Party.id == party_id)
        )

    async def get_unit(self, unit_id: UUID) -> UnitOfMeasure | None:
        return await self.session.get(UnitOfMeasure, unit_id)

    async def get_item(self, item_id: UUID) -> LoaItem | None:
        return await self.session.get(LoaItem, item_id)

    async def list_items(self, loa_id: UUID) -> list[LoaItem]:
        return list(
            await self.session.scalars(
                select(LoaItem).where(LoaItem.loa_id == loa_id).order_by(LoaItem.item_number)
            )
        )

    async def get_variation(self, variation_id: UUID) -> LoaVariation | None:
        return await self.session.scalar(
            select(LoaVariation)
            .options(selectinload(LoaVariation.lines))
            .where(LoaVariation.id == variation_id)
        )

    async def list_variations(self, loa_id: UUID) -> list[LoaVariation]:
        result = await self.session.scalars(
            select(LoaVariation)
            .options(selectinload(LoaVariation.lines))
            .where(LoaVariation.loa_id == loa_id)
            .order_by(LoaVariation.variation_date, LoaVariation.created_at)
        )
        return list(result.unique())

    async def committed_quantity(self, loa_item_id: UUID) -> Decimal:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(PurchaseOrderLine.ordered_quantity), 0))
            .join(PurchaseOrder)
            .where(
                PurchaseOrderLine.loa_item_id == loa_item_id,
                PurchaseOrder.status.in_(
                    ("APPROVED", "ISSUED", "PARTIALLY_FULFILLED", "FULFILLED")
                ),
            )
        )
        return Decimal(value or 0)

    async def lock_item(self, loa_item_id: UUID) -> None:
        await self.session.scalar(
            select(LoaItem.id).where(LoaItem.id == loa_item_id).with_for_update()
        )

    def audit(
        self, actor_id: UUID, action: str, entity_type: str, entity_id: UUID, old, new, reason=None
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
