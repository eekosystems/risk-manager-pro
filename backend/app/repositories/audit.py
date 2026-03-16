import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEntry


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_entries(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditEntry], int]:
        base = select(AuditEntry).where(AuditEntry.organization_id == organization_id)
        count_base = (
            select(func.count())
            .select_from(AuditEntry)
            .where(AuditEntry.organization_id == organization_id)
        )

        if action:
            base = base.where(AuditEntry.action == action)
            count_base = count_base.where(AuditEntry.action == action)
        if resource_type:
            base = base.where(AuditEntry.resource_type == resource_type)
            count_base = count_base.where(AuditEntry.resource_type == resource_type)
        if outcome:
            base = base.where(AuditEntry.outcome == outcome)
            count_base = count_base.where(AuditEntry.outcome == outcome)
        if user_id:
            base = base.where(AuditEntry.user_id == user_id)
            count_base = count_base.where(AuditEntry.user_id == user_id)
        if date_from:
            base = base.where(AuditEntry.timestamp >= date_from)
            count_base = count_base.where(AuditEntry.timestamp >= date_from)
        if date_to:
            base = base.where(AuditEntry.timestamp <= date_to)
            count_base = count_base.where(AuditEntry.timestamp <= date_to)

        count_result = await self._db.execute(count_base)
        total = count_result.scalar_one()

        stmt = base.order_by(AuditEntry.timestamp.desc()).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_distinct_actions(self, organization_id: uuid.UUID) -> list[str]:
        stmt = (
            select(AuditEntry.action)
            .where(AuditEntry.organization_id == organization_id)
            .distinct()
            .order_by(AuditEntry.action)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_distinct_resource_types(self, organization_id: uuid.UUID) -> list[str]:
        stmt = (
            select(AuditEntry.resource_type)
            .where(AuditEntry.organization_id == organization_id)
            .distinct()
            .order_by(AuditEntry.resource_type)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
