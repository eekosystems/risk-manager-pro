"""Importing SharePoint SRMD hazards onto the Risk Register.

Import creates one RMP-validated entry per (airport, hazard) with the
report's initial cell, residual cell and verbatim mitigations. It never
duplicates and never touches an entry already on the register, and a client
organization only ever receives its own airport's hazards.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.risk import (
    Mitigation,
    RecordSource,
    RiskEntry,
    RiskLevel,
    RiskStatus,
    ValidationStatus,
)
from app.models.user import User
from app.services.risk_outcome_importer import SharePointRisk
from app.services.srmd_import import SrmdImportService, srmd_ref
from tests.conftest import make_test_organization, make_test_user


async def _seed(
    db: AsyncSession, *, is_platform: bool = True, slug: str = "fg"
) -> tuple[Organization, User]:
    org = make_test_organization(org_id=uuid.uuid4(), slug=slug, is_platform=is_platform)
    db.add(org)
    user = make_test_user()
    db.add(user)
    await db.flush()
    return org, user


def _hazard(
    hazard: str = "Contractors and Haul Rts. - Accident between AC and Veh.",
    airport: str = "DEN",
    mitigations: list[str] | None = None,
) -> SharePointRisk:
    return SharePointRisk(
        airport_identifier=airport,
        hazard=hazard,
        severity=4,
        likelihood="C",
        risk_level="high",
        source_file="DEN SRMD 2024.pdf",
        source_url="https://sharepoint.example/den-srmd.pdf",
        residual_severity=4,
        residual_likelihood="E",
        residual_risk_level="medium",
        mitigations=["Escort haul vehicles", "Issue NOTAM"] if mitigations is None else mitigations,
    )


async def _entries(db: AsyncSession, org_id: uuid.UUID) -> list[RiskEntry]:
    result = await db.execute(select(RiskEntry).where(RiskEntry.organization_id == org_id))
    return list(result.scalars().all())


async def test_import_creates_validated_entry_with_cells_and_mitigations(
    db_session: AsyncSession,
) -> None:
    org, user = await _seed(db_session)

    created, already = await SrmdImportService(db_session).import_hazards([_hazard()], org, user.id)

    assert already == 0
    [entry] = created
    assert (entry.likelihood, entry.severity, entry.risk_level) == ("C", 4, RiskLevel.HIGH)
    assert (entry.residual_likelihood, entry.residual_severity) == ("E", 4)
    assert entry.residual_risk_level == RiskLevel.MEDIUM
    assert entry.validation_status == ValidationStatus.RMP_VALIDATED
    assert entry.source == RecordSource.SHAREPOINT_SRMD
    assert entry.status == RiskStatus.MITIGATING
    assert entry.source_document_name == "DEN SRMD 2024.pdf"
    assert entry.source_document_url == "https://sharepoint.example/den-srmd.pdf"
    assert entry.srmd_ref == srmd_ref("DEN", entry.hazard)
    mitigations = (
        await db_session.execute(select(Mitigation).where(Mitigation.risk_entry_id == entry.id))
    ).scalars()
    assert sorted(m.title for m in mitigations) == ["Escort haul vehicles", "Issue NOTAM"]


async def test_reimport_skips_existing_and_keeps_edits(db_session: AsyncSession) -> None:
    org, user = await _seed(db_session)
    service = SrmdImportService(db_session)
    [entry], _ = await service.import_hazards([_hazard()], org, user.id)
    entry.residual_likelihood = "D"
    await db_session.flush()

    created, already = await service.import_hazards(
        [_hazard(), _hazard(hazard="Construction site entry", mitigations=[])], org, user.id
    )

    assert already == 1
    assert [c.hazard for c in created] == ["Construction site entry"]
    assert created[0].status == RiskStatus.OPEN
    entries = await _entries(db_session, org.id)
    assert len(entries) == 2
    assert entry.residual_likelihood == "D"


async def test_same_hazard_differently_cased_is_one_entry(db_session: AsyncSession) -> None:
    org, user = await _seed(db_session)

    created, _ = await SrmdImportService(db_session).import_hazards(
        [_hazard(hazard="FOD - Clean Soil"), _hazard(hazard="  fod - clean soil ")], org, user.id
    )

    assert len(created) == 1


async def test_client_org_receives_only_its_airport(db_session: AsyncSession) -> None:
    org, user = await _seed(db_session, is_platform=False, slug="den")

    created, _ = await SrmdImportService(db_session).import_hazards(
        [_hazard(airport="DEN"), _hazard(airport="SEA")], org, user.id
    )

    assert [c.airport_identifier for c in created] == ["DEN"]
