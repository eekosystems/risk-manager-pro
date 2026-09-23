"""Import SharePoint SRMD hazards into the Risk Register as risk entries.

The risk-outcome scan extracts hazards from each airport's SRMD reports but
keeps them only in its cache, where nothing can be edited. Importing turns
each (airport, hazard) into a risk entry carrying the report's initial cell,
residual cell and verbatim mitigations, so mitigations become editable and
can drive an SP3 residual re-assessment.

Import only ever creates: an (airport, hazard) that is already on the
register is left untouched, so later edits are never overwritten by a
re-scan of the source report.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog

from app.models.risk import (
    RecordSource,
    RecordStatus,
    RiskMatrixApplied,
    RiskStatus,
    ValidationStatus,
    compute_risk_level,
)
from app.repositories.risk import RiskRepository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.organization import Organization
    from app.models.risk import RiskEntry
    from app.services.risk_outcome_importer import SharePointRisk

logger = structlog.get_logger(__name__)

_TITLE_MAX = 500
_SOURCE_NAME_MAX = 500


def srmd_ref(airport_identifier: str, hazard: str) -> str:
    """Stable key for one hazard at one airport.

    Normalized the same way the scan's summary dedups across reports, so one
    register entry stands for the row the Risk Register shows.
    """
    key = f"{airport_identifier.strip().upper()}\n{hazard.lower().strip()[:120]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def hazards_visible_to(
    organization: Organization, hazards: list[SharePointRisk]
) -> list[SharePointRisk]:
    """The platform organization sees every airport; a client only its own.

    A client airport's organization slug is its airport identifier, the same
    convention the dual-register sync uses to route records.
    """
    if organization.is_platform:
        return hazards
    slug = (organization.slug or "").lower()
    return [h for h in hazards if h.airport_identifier.lower() == slug]


class SrmdImportService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = RiskRepository(db)

    async def import_hazards(
        self,
        hazards: list[SharePointRisk],
        organization: Organization,
        user_id: uuid.UUID,
    ) -> tuple[list[RiskEntry], int]:
        """Create a risk entry per new hazard. Returns (created, already_imported)."""
        by_ref: dict[str, SharePointRisk] = {}
        for hazard in hazards_visible_to(organization, hazards):
            by_ref.setdefault(srmd_ref(hazard.airport_identifier, hazard.hazard), hazard)

        existing = await self._repo.existing_srmd_refs(organization.id, list(by_ref))
        created: list[RiskEntry] = []
        for ref, hazard in by_ref.items():
            if ref in existing:
                continue
            created.append(await self._create_entry(ref, hazard, organization.id, user_id))

        logger.info(
            "srmd_hazards_imported",
            organization_id=str(organization.id),
            imported=len(created),
            already_imported=len(existing),
        )
        return created, len(existing)

    async def _create_entry(
        self,
        ref: str,
        hazard: SharePointRisk,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> RiskEntry:
        residual_level = (
            compute_risk_level(hazard.residual_severity, hazard.residual_likelihood)
            if hazard.residual_severity is not None and hazard.residual_likelihood is not None
            else None
        )
        entry = await self._repo.create(
            organization_id=organization_id,
            created_by=user_id,
            title=hazard.hazard[:_TITLE_MAX],
            description=f"Imported from SharePoint SRMD report {hazard.source_file}.",
            hazard=hazard.hazard,
            severity=hazard.severity,
            likelihood=hazard.likelihood,
            risk_level=compute_risk_level(hazard.severity, hazard.likelihood),
            status=RiskStatus.MITIGATING if hazard.mitigations else RiskStatus.OPEN,
            function_type="risk_register",
            airport_identifier=hazard.airport_identifier,
            risk_matrix_applied=RiskMatrixApplied.FAA_5X5,
            residual_severity=hazard.residual_severity if residual_level else None,
            residual_likelihood=hazard.residual_likelihood if residual_level else None,
            residual_risk_level=residual_level,
            record_status=RecordStatus.OPEN,
            validation_status=ValidationStatus.RMP_VALIDATED,
            source=RecordSource.SHAREPOINT_SRMD,
            srmd_ref=ref,
            source_document_name=hazard.source_file[:_SOURCE_NAME_MAX],
            source_document_url=hazard.source_url,
        )
        for text in hazard.mitigations:
            await self._repo.create_mitigation(
                risk_entry_id=entry.id,
                title=text[:_TITLE_MAX],
                description=text,
            )
        return entry
