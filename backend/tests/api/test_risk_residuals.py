"""Risk Register API: SRMD import, mitigation-triggered re-assessment, confirm.

The re-assessment run itself is exercised in the service tests; here the
runner only records what was queued, so these cover the wiring, the audit
trail and the list payload the Risk Register renders.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.risks import _get_residual_assessment_service
from app.models.organization import Organization
from app.models.residual_assessment import ResidualAssessment, ResidualAssessmentStatus
from app.models.risk import RiskEntry, RiskLevel, compute_risk_level
from app.models.user import User
from app.services.residual_assessment import ResidualAssessmentRunner, ResidualAssessmentService
from app.services.risk_outcome_importer import SharePointRisk


class _QueuedRuns(ResidualAssessmentRunner):
    def __init__(self) -> None:
        self.queued: list[uuid.UUID] = []

    async def run(self, assessment_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        self.queued.append(assessment_id)


def _use_queued_runs(app: FastAPI, db_session: AsyncSession) -> _QueuedRuns:
    runs = _QueuedRuns()
    app.dependency_overrides[_get_residual_assessment_service] = lambda: ResidualAssessmentService(
        db_session, runs
    )
    return runs


async def _entry(db: AsyncSession, org: Organization, user: User) -> RiskEntry:
    entry = RiskEntry(
        organization_id=org.id,
        created_by=user.id,
        title="Haul route crossing",
        description="Imported",
        hazard="Haul route crossing",
        severity=4,
        likelihood="C",
        risk_level=compute_risk_level(4, "C"),
        airport_identifier="DEN",
    )
    db.add(entry)
    await db.flush()
    return entry


def _actions(mock_audit_logger: AsyncMock) -> list[str]:
    return [call.kwargs["action"] for call in mock_audit_logger.log.call_args_list]


async def test_adding_a_mitigation_queues_a_reassessment(
    client: AsyncClient,
    test_app: FastAPI,
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
    mock_audit_logger: AsyncMock,
) -> None:
    runs = _use_queued_runs(test_app, db_session)
    entry = await _entry(db_session, test_organization, test_user)

    response = await client.post(
        f"/api/v1/risks/{entry.id}/mitigations",
        json={"title": "Escort haul vehicles", "description": "Escort every crossing"},
    )

    assert response.status_code == 201
    assert _actions(mock_audit_logger) == [
        "mitigation.created",
        "risk.residual_assessment_requested",
    ]

    # The test shares one session across requests; drop what the POST cached.
    db_session.expire(entry)
    listed = (await client.get("/api/v1/risks")).json()["data"]
    [row] = [r for r in listed if r["id"] == str(entry.id)]
    assert [m["title"] for m in row["mitigations"]] == ["Escort haul vehicles"]
    assert row["latest_assessment"]["status"] == "pending"
    assert row["latest_assessment"]["trigger"] == "mitigation.created"
    assert runs.queued == [uuid.UUID(row["latest_assessment"]["id"])]


async def test_confirming_a_proposal_updates_the_residual(
    client: AsyncClient,
    test_app: FastAPI,
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
    mock_audit_logger: AsyncMock,
) -> None:
    _use_queued_runs(test_app, db_session)
    entry = await _entry(db_session, test_organization, test_user)
    proposal = ResidualAssessment(
        organization_id=test_organization.id,
        risk_entry_id=entry.id,
        status=ResidualAssessmentStatus.PROPOSED,
        trigger="mitigation.created",
        requested_by=test_user.id,
        residual_severity=4,
        residual_likelihood="E",
        residual_risk_level=RiskLevel.MEDIUM,
    )
    db_session.add(proposal)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/risks/{entry.id}/residual-assessments/{proposal.id}/confirm"
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "confirmed"
    detail = (await client.get(f"/api/v1/risks/{entry.id}")).json()["data"]
    assert (detail["residual_likelihood"], detail["residual_severity"]) == ("E", 4)
    assert detail["residual_risk_level"] == "medium"
    assert "risk.residual_confirmed" in _actions(mock_audit_logger)

    again = await client.post(
        f"/api/v1/risks/{entry.id}/residual-assessments/{proposal.id}/confirm"
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONFLICT"


async def test_import_srmd_creates_entries_once(
    client: AsyncClient,
    test_app: FastAPI,
    mock_audit_logger: AsyncMock,
) -> None:
    hazard = SharePointRisk(
        airport_identifier="DEN",
        hazard="FOD - Clean Soil hauled into site.",
        severity=2,
        likelihood="D",
        risk_level="low",
        source_file="DEN SRMD.pdf",
        source_url=None,
        mitigations=["Sweep haul route daily"],
    )
    importer = AsyncMock()
    importer.snapshot.return_value = SimpleNamespace(risks=[hazard])
    test_app.state.services.risk_outcome_importer = importer

    first = await client.post("/api/v1/risks/import-srmd")
    second = await client.post("/api/v1/risks/import-srmd")

    assert first.status_code == 201
    assert (first.json()["data"]["imported"], first.json()["data"]["already_imported"]) == (1, 0)
    assert (second.json()["data"]["imported"], second.json()["data"]["already_imported"]) == (0, 1)
    listed = (await client.get("/api/v1/risks")).json()["data"]
    [row] = [r for r in listed if r["source"] == "sharepoint_srmd"]
    assert row["validation_status"] == "rmp_validated"
    assert [m["title"] for m in row["mitigations"]] == ["Sweep haul route daily"]
    assert _actions(mock_audit_logger).count("risk.created") == 1
    assert _actions(mock_audit_logger).count("risk.srmd_imported") == 2
