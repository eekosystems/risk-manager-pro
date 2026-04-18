import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.risk import (
    AirportSubLocation,
    Mitigation,
    MitigationStatus,
    RiskEntry,
    RiskStatus,
    compute_risk_level,
    default_icao_for_5m,
    record_status_from_legacy,
)
from app.repositories.risk import RiskRepository
from app.schemas.risk import (
    CreateMitigationRequest,
    CreateRiskEntryRequest,
    UpdateMitigationRequest,
    UpdateRiskEntryRequest,
)
from app.services.rr_sync import RRSyncService, _snapshot_entry, compute_entry_diff

logger = structlog.get_logger(__name__)


class RiskService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RiskRepository(db)
        self._sync = RRSyncService(db)

    # --- Risk Entries ---

    async def create_risk_entry(
        self,
        payload: CreateRiskEntryRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> RiskEntry:
        risk_level = compute_risk_level(payload.severity, payload.likelihood)

        # If 5M category is supplied without ICAO, fill in the default mapping.
        icao = payload.hazard_category_icao
        if payload.hazard_category_5m is not None and icao is None:
            icao = default_icao_for_5m(payload.hazard_category_5m)

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
            airport_identifier=payload.airport_identifier,
            potential_credible_outcome=payload.potential_credible_outcome,
            operational_domain=payload.operational_domain,
            sub_location=payload.sub_location,
            hazard_category_5m=payload.hazard_category_5m,
            hazard_category_icao=icao,
            risk_matrix_applied=payload.risk_matrix_applied,
            existing_controls=payload.existing_controls,
            residual_risk_level=payload.residual_risk_level,
            record_status=payload.record_status,
            validation_status=payload.validation_status,
            source=payload.source,
            acm_cross_reference=payload.acm_cross_reference,
        )

        # Persist the sub-location into the airport's library for future suggestions.
        if payload.airport_identifier and payload.sub_location:
            await self._upsert_sub_location(
                organization_id, payload.airport_identifier, payload.sub_location
            )

        # Enqueue a sync push to the counterpart RR instance.
        await self._sync.enqueue_create_push(entry=entry, creator_user_id=user_id)

        logger.info(
            "risk_entry_created",
            risk_id=str(entry.id),
            risk_level=risk_level.value,
            severity=payload.severity,
            likelihood=payload.likelihood,
            airport=payload.airport_identifier,
            source=payload.source.value,
        )
        return entry

    async def get_risk_entry(self, risk_id: uuid.UUID, organization_id: uuid.UUID) -> RiskEntry:
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
        user_id: uuid.UUID | None = None,
    ) -> RiskEntry:
        entry = await self._repo.get_by_id(risk_id, organization_id)
        if not entry:
            raise NotFoundError("RiskEntry", str(risk_id))

        updates = payload.model_dump(exclude_unset=True)
        before = _snapshot_entry(entry)

        # Enforce closure approval gate before any state change.
        moving_to_closed = (
            updates.get("record_status") == "closed" or updates.get("status") == "closed"
        )
        if moving_to_closed:
            await self._sync.assert_closure_allowed(entry.id)

        for field, value in updates.items():
            setattr(entry, field, value)

        # Recompute risk level if severity or likelihood changed
        if "severity" in updates or "likelihood" in updates:
            entry.risk_level = compute_risk_level(entry.severity, entry.likelihood)

        # Fill in ICAO mapping from 5M when 5M was set without ICAO.
        if (
            "hazard_category_5m" in updates
            and "hazard_category_icao" not in updates
            and entry.hazard_category_5m is not None
        ):
            entry.hazard_category_icao = default_icao_for_5m(entry.hazard_category_5m)

        # Legacy status ↔ record_status sync (both directions).
        if "status" in updates and "record_status" not in updates:
            entry.record_status = record_status_from_legacy(entry.status)

        # Auto-transition status when risk is fully mitigated
        if "status" not in updates and entry.status == RiskStatus.OPEN:
            mitigations = entry.mitigations
            if mitigations and all(m.status == MitigationStatus.COMPLETED for m in mitigations):
                entry.status = RiskStatus.MITIGATING
                entry.record_status = record_status_from_legacy(entry.status)

        await self._repo.update(entry)

        # Enqueue a sync diff on the counterpart instance (if this is a dual record).
        if user_id is not None:
            diff = compute_entry_diff(before, entry)
            if diff:
                await self._sync.enqueue_update_push(
                    entry=entry, diff=diff, initiator_user_id=user_id
                )

        logger.info(
            "risk_entry_updated",
            risk_id=str(risk_id),
            updated_fields=list(updates.keys()),
        )
        return entry

    async def delete_risk_entry(self, risk_id: uuid.UUID, organization_id: uuid.UUID) -> None:
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
            verification_method=payload.verification_method,
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

    # --- Airport Sub-Location Library (Sub-Prompt 4 §Step 3a) ---

    async def list_sub_locations(
        self, organization_id: uuid.UUID, airport_identifier: str
    ) -> list[AirportSubLocation]:
        stmt = (
            select(AirportSubLocation)
            .where(
                AirportSubLocation.organization_id == organization_id,
                AirportSubLocation.airport_identifier == airport_identifier,
            )
            .order_by(AirportSubLocation.name.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_sub_location(
        self,
        organization_id: uuid.UUID,
        airport_identifier: str,
        name: str,
    ) -> AirportSubLocation:
        """Insert a sub-location into the airport's library if not already present."""
        stmt = select(AirportSubLocation).where(
            AirportSubLocation.organization_id == organization_id,
            AirportSubLocation.airport_identifier == airport_identifier,
            AirportSubLocation.name == name,
        )
        existing = (await self._db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
        row = AirportSubLocation(
            organization_id=organization_id,
            airport_identifier=airport_identifier,
            name=name,
        )
        self._db.add(row)
        await self._db.flush()
        return row
