from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import AuditLog
from app.models.loa_imports import RailwayLoaImport, RailwayLoaImportSchedule
from app.models.master_data import (
    HsnCode,
    Loa,
    Party,
    Project,
    RailwayAuthority,
    RailwayDivision,
    RailwayZone,
    UnitOfMeasure,
)


class RailwayLoaImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record):
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, import_id: UUID, *, lock: bool = False) -> RailwayLoaImport | None:
        statement = (
            select(RailwayLoaImport)
            .options(
                selectinload(RailwayLoaImport.lines),
                selectinload(RailwayLoaImport.schedules).selectinload(
                    RailwayLoaImportSchedule.groups
                ),
            )
            .where(RailwayLoaImport.id == import_id)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(self) -> list[RailwayLoaImport]:
        result = await self.session.scalars(
            select(RailwayLoaImport)
            .options(
                selectinload(RailwayLoaImport.lines),
                selectinload(RailwayLoaImport.schedules).selectinload(
                    RailwayLoaImportSchedule.groups
                ),
            )
            .order_by(RailwayLoaImport.uploaded_at.desc())
        )
        return list(result.unique())

    async def divisions(self) -> list[RailwayDivision]:
        return list(
            await self.session.scalars(
                select(RailwayDivision).where(RailwayDivision.is_active.is_(True))
            )
        )

    async def division(self, division_id: UUID, *, lock: bool = False) -> RailwayDivision | None:
        statement = select(RailwayDivision).where(RailwayDivision.id == division_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def party(self, party_id: UUID) -> Party | None:
        return await self.session.scalar(
            select(Party).options(selectinload(Party.roles)).where(Party.id == party_id)
        )

    async def zones(self) -> list[RailwayZone]:
        return list(
            await self.session.scalars(select(RailwayZone).where(RailwayZone.is_active.is_(True)))
        )

    async def authorities(self) -> list[RailwayAuthority]:
        return list(
            await self.session.scalars(
                select(RailwayAuthority).options(selectinload(RailwayAuthority.roles))
            )
        )

    async def projects(self, division_id: UUID | None) -> list[Project]:
        statement = select(Project).where(Project.is_active.is_(True))
        if division_id:
            statement = statement.where(Project.railway_division_id == division_id)
        return list(await self.session.scalars(statement))

    async def units(self) -> list[UnitOfMeasure]:
        return list(
            await self.session.scalars(
                select(UnitOfMeasure).where(UnitOfMeasure.is_active.is_(True))
            )
        )

    async def hsn_codes(self) -> list[HsnCode]:
        return list(await self.session.scalars(select(HsnCode).where(HsnCode.is_active.is_(True))))

    async def duplicate_loas(
        self, loa_number: str | None, division_id: UUID | None, tender_reference: str | None
    ) -> list[Loa]:
        if not loa_number and not tender_reference:
            return []
        conditions = []
        if loa_number:
            conditions.append(func.lower(Loa.loa_number) == loa_number.lower())
        if tender_reference:
            conditions.append(func.lower(Loa.customer_reference) == tender_reference.lower())
        statement = select(Loa).where(or_(*conditions))
        if division_id:
            statement = statement.where(Loa.railway_division_id == division_id)
        return list(await self.session.scalars(statement))

    def audit(self, actor_id: UUID, action: str, import_id: UUID, old, new, reason=None) -> None:
        self.session.add(
            AuditLog(
                actor_user_id=actor_id,
                action=action,
                entity_type="railway_loa_import",
                entity_id=str(import_id),
                old_value=old,
                new_value=new,
                reason=reason,
            )
        )
