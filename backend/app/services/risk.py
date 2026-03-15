import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.risk import (
    Mitigation,
    MitigationStatus,
    RiskEntry,
    RiskStatus,
    compute_risk_level,
)
from app.repositories.risk import RiskRepository
from app.schemas.risk import (
    CreateMitigationRequest,
    CreateRiskEntryRequest,
    UpdateMitigationRequest,
    UpdateRiskEntryRequest,
)

logger = structlog.get_logger(__name__)


class RiskService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = RiskRepository(db)

    # --- Risk Entries ---

    async def create_risk_entry(
        self,
        payload: CreateRiskEntryRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> RiskEntry:
        risk_level = compute_risk_level(payload.severity, payload.likelihood)

        entry = await self._repo.create(
            organization_id=organization_id,
            created_by=user_id,
            title=payload.title,
            description=payload.description,
            hazard=payload.hazard,
            severity=payload.severity,
            likelihood=payload.likelihood,
            risk_level=risk_level,
            function_type=payload.function_type,
            conversation_id=payload.conversation_id,
            notes=payload.notes,
        )

        logger.info(
            "risk_entry_created",
            risk_id=str(entry.id),
            risk_level=risk_level.value,
            severity=payload.severity,
            likelihood=payload.likelihood,
        )
        return entry

    async def get_risk_entry(
        self, risk_id: uuid.UUID, organization_id: uuid.UUID
    ) -> RiskEntry:
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))
        return entry

    async def list_risk_entries(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[list[RiskEntry], int]:
        return await self._repo.list_for_organization(
            organization_id, skip, limit, status=status, risk_level=risk_level
        )

    async def update_risk_entry(
        self,
        risk_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: UpdateRiskEntryRequest,
    ) -> RiskEntry:
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))

        updates = payload.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(entry, field, value)

        # Recompute risk level if severity or likelihood changed
        if "severity" in updates or "likelihood" in updates:
            entry.risk_level = compute_risk_level(entry.severity, entry.likelihood)

        # Auto-transition status when risk is fully mitigated
        if "status" not in updates and entry.status == RiskStatus.OPEN:
            mitigations = entry.mitigations
            if mitigations and all(m.status == MitigationStatus.COMPLETED for m in mitigations):
                entry.status = RiskStatus.MITIGATING

        await self._repo.update(entry)

        logger.info(
            "risk_entry_updated",
            risk_id=str(risk_id),
            updated_fields=list(updates.keys()),
        )
        return entry

    async def delete_risk_entry(
        self, risk_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        deleted = await self._repo.delete(risk_id, organization_id)
        if not deleted:
            raise NotFoundError("RiskEntry", str(risk_id))
        logger.info("risk_entry_deleted", risk_id=str(risk_id))

    # --- Mitigations ---

    async def create_mitigation(
        self,
        risk_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: CreateMitigationRequest,
    ) -> Mitigation:
        # Verify the risk entry exists and belongs to the org
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))

        mitigation = await self._repo.create_mitigation(
            risk_entry_id=risk_id,
            title=payload.title,
            description=payload.description,
            assignee=payload.assignee,
            due_date=payload.due_date,
        )

        # Transition risk to mitigating if it was open
        if entry.status == RiskStatus.OPEN:
            entry.status = RiskStatus.MITIGATING
            await self._repo.update(entry)

        logger.info(
            "mitigation_created",
            mitigation_id=str(mitigation.id),
            risk_id=str(risk_id),
        )
        return mitigation

    async def update_mitigation(
        self,
        risk_id: uuid.UUID,
        mitigation_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: UpdateMitigationRequest,
    ) -> Mitigation:
        # Verify risk entry belongs to org
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))

        mitigation = await self._repo.get_mitigation_by_id(mitigation_id, risk_id)
        if not mitigation:
            raise NotFoundError("Mitigation", str(mitigation_id))

        updates = payload.model_dump(exclude_unset=True)

        if "status" in updates:
            await self._repo.update_mitigation_status(mitigation, updates.pop("status"))

        for field, value in updates.items():
            setattr(mitigation, field, value)

        await self._repo.update_mitigation(mitigation)

        logger.info(
            "mitigation_updated",
            mitigation_id=str(mitigation_id),
            risk_id=str(risk_id),
        )
        return mitigation

    async def delete_mitigation(
        self,
        risk_id: uuid.UUID,
        mitigation_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))

        deleted = await self._repo.delete_mitigation(mitigation_id, risk_id)
        if not deleted:
            raise NotFoundError("Mitigation", str(mitigation_id))

        logger.info(
            "mitigation_deleted",
            mitigation_id=str(mitigation_id),
            risk_id=str(risk_id),
        )
