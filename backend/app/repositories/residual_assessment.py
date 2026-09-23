import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.residual_assessment import (
    OPEN_ASSESSMENT_STATUSES,
    ResidualAssessment,
    ResidualAssessmentStatus,
)


class ResidualAssessmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, **kwargs: object) -> ResidualAssessment:
        assessment = ResidualAssessment(**kwargs)
        self._db.add(assessment)
        await self._db.flush()
        return assessment

    async def get(
        self,
        assessment_id: uuid.UUID,
        risk_entry_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ResidualAssessment | None:
        stmt = select(ResidualAssessment).where(
            ResidualAssessment.id == assessment_id,
            ResidualAssessment.risk_entry_id == risk_entry_id,
            ResidualAssessment.organization_id == organization_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_for_run(
        self, assessment_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ResidualAssessment | None:
        stmt = (
            select(ResidualAssessment)
            .where(
                ResidualAssessment.id == assessment_id,
                ResidualAssessment.organization_id == organization_id,
            )
            .with_for_update()
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def supersede_open(self, risk_entry_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        stmt = (
            update(ResidualAssessment)
            .where(
                ResidualAssessment.risk_entry_id == risk_entry_id,
                ResidualAssessment.organization_id == organization_id,
                ResidualAssessment.status.in_(OPEN_ASSESSMENT_STATUSES),
            )
            .values(status=ResidualAssessmentStatus.SUPERSEDED)
        )
        await self._db.execute(stmt)

    async def latest_for_entries(
        self, risk_entry_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> dict[uuid.UUID, ResidualAssessment]:
        if not risk_entry_ids:
            return {}
        stmt = (
            select(ResidualAssessment)
            .where(
                ResidualAssessment.organization_id == organization_id,
                ResidualAssessment.risk_entry_id.in_(risk_entry_ids),
            )
            .distinct(ResidualAssessment.risk_entry_id)
            .order_by(ResidualAssessment.risk_entry_id, ResidualAssessment.created_at.desc())
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return {row.risk_entry_id: row for row in rows}
