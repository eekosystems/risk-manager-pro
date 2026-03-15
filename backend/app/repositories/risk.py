import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.risk import Mitigation, MitigationStatus, RiskEntry


class RiskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # --- Risk Entries ---

    async def create(self, **kwargs: object) -> RiskEntry:
        entry = RiskEntry(**kwargs)
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def get_by_id(
        self, risk_id: uuid.UUID, organization_id: uuid.UUID
    ) -> RiskEntry | None:
        stmt = (
            select(RiskEntry)
            .options(selectinload(RiskEntry.mitigations))
            .where(
                RiskEntry.id == risk_id,
                RiskEntry.organization_id == organization_id,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[list[RiskEntry], int]:
        base = select(RiskEntry).where(RiskEntry.organization_id == organization_id)
        count_base = (
            select(func.count())
            .select_from(RiskEntry)
            .where(RiskEntry.organization_id == organization_id)
        )

        if status:
            base = base.where(RiskEntry.status == status)
            count_base = count_base.where(RiskEntry.status == status)
        if risk_level:
            base = base.where(RiskEntry.risk_level == risk_level)
            count_base = count_base.where(RiskEntry.risk_level == risk_level)

        count_result = await self._db.execute(count_base)
        total = count_result.scalar_one()

        stmt = base.order_by(RiskEntry.created_at.desc()).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def update(self, entry: RiskEntry) -> RiskEntry:
        await self._db.flush()
        return entry

    async def delete(self, risk_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        entry = await self.get_by_id(risk_id, organization_id)
        if not entry:
            return False
        await self._db.delete(entry)
        await self._db.flush()
        return True

    # --- Mitigations ---

    async def create_mitigation(self, **kwargs: object) -> Mitigation:
        mitigation = Mitigation(**kwargs)
        self._db.add(mitigation)
        await self._db.flush()
        return mitigation

    async def get_mitigation_by_id(
        self, mitigation_id: uuid.UUID, risk_entry_id: uuid.UUID
    ) -> Mitigation | None:
        stmt = select(Mitigation).where(
            Mitigation.id == mitigation_id,
            Mitigation.risk_entry_id == risk_entry_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_mitigations(self, risk_entry_id: uuid.UUID) -> list[Mitigation]:
        stmt = (
            select(Mitigation)
            .where(Mitigation.risk_entry_id == risk_entry_id)
            .order_by(Mitigation.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update_mitigation(self, mitigation: Mitigation) -> Mitigation:
        await self._db.flush()
        return mitigation

    async def delete_mitigation(
        self, mitigation_id: uuid.UUID, risk_entry_id: uuid.UUID
    ) -> bool:
        mitigation = await self.get_mitigation_by_id(mitigation_id, risk_entry_id)
        if not mitigation:
            return False
        await self._db.delete(mitigation)
        await self._db.flush()
        return True

    async def update_mitigation_status(
        self, mitigation: Mitigation, status: MitigationStatus
    ) -> Mitigation:
        from datetime import datetime, timezone

        mitigation.status = status
        if status == MitigationStatus.COMPLETED:
            mitigation.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        return mitigation
