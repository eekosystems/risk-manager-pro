"""Risk Register fields the register filters and the chat fill in.

The residual risk is a matrix cell whose band is computed server-side, the
SRA disposition is a column rather than Notes text, and a High initial or
residual risk flags the record for Accountable Executive review unless a
user says otherwise.
"""

import uuid
from unittest.mock import AsyncMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.models.organization import Organization
from app.models.user import User


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Haul trucks crossing Taxiway Alpha",
        "description": "Rehab contractor haul route crosses the active taxiway.",
        "hazard": "Haul trucks crossing Taxiway Alpha",
        "severity": 4,
        "likelihood": "C",
        "airport_identifier": "SUS",
    }
    base.update(overrides)
    return base


async def test_residual_band_follows_the_cell_and_high_flags_ae_review(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/risks",
        json=_payload(
            residual_severity=4,
            residual_likelihood="E",
            disposition="further_mitigation_required",
        ),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert (data["risk_level"], data["residual_risk_level"]) == ("high", "medium")
    assert data["disposition"] == "further_mitigation_required"
    assert data["ae_review_required"] is True


async def test_half_a_residual_cell_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/risks", json=_payload(residual_likelihood="E"))

    assert response.status_code == 422


async def test_low_risk_needs_no_ae_review_unless_the_residual_is_high(
    client: AsyncClient,
) -> None:
    low = await client.post("/api/v1/risks", json=_payload(severity=1, likelihood="E"))
    high_residual = await client.post(
        "/api/v1/risks",
        json=_payload(severity=1, likelihood="E", residual_severity=5, residual_likelihood="A"),
    )

    assert low.json()["data"]["ae_review_required"] is False
    assert high_residual.json()["data"]["ae_review_required"] is True


async def test_register_filters_records_awaiting_ae_review(client: AsyncClient) -> None:
    high = (await client.post("/api/v1/risks", json=_payload())).json()["data"]["id"]
    await client.post("/api/v1/risks", json=_payload(severity=1, likelihood="E"))

    listed = (await client.get("/api/v1/risks", params={"ae_review_required": "true"})).json()

    assert [r["id"] for r in listed["data"]] == [high]
    assert listed["meta"]["total"] == 1


async def test_user_override_holds_until_a_band_changes(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/risks", json=_payload())).json()["data"]
    risk_id = created["id"]

    cleared = await client.patch(f"/api/v1/risks/{risk_id}", json={"ae_review_required": False})
    retitled = await client.patch(f"/api/v1/risks/{risk_id}", json={"title": "Renamed"})
    regraded = await client.patch(f"/api/v1/risks/{risk_id}", json={"likelihood": "A"})

    assert cleared.json()["data"]["ae_review_required"] is False
    assert retitled.json()["data"]["ae_review_required"] is False
    assert regraded.json()["data"]["ae_review_required"] is True


async def test_detail_carries_the_latest_assessment_slot(client: AsyncClient) -> None:
    risk_id = (await client.post("/api/v1/risks", json=_payload())).json()["data"]["id"]

    detail = (await client.get(f"/api/v1/risks/{risk_id}")).json()["data"]

    assert detail["latest_assessment"] is None
    assert detail["ae_review_required"] is True


def _metadata(mock_audit_logger: AsyncMock, action: str) -> dict[str, object]:
    [call] = [c for c in mock_audit_logger.log.call_args_list if c.kwargs["action"] == action]
    metadata: dict[str, object] = call.kwargs["metadata"]
    return metadata


async def test_update_audit_row_carries_before_and_after_values(
    client: AsyncClient, mock_audit_logger: AsyncMock
) -> None:
    risk_id = (await client.post("/api/v1/risks", json=_payload())).json()["data"]["id"]

    await client.patch(
        f"/api/v1/risks/{risk_id}",
        json={"likelihood": "E", "residual_severity": 4, "residual_likelihood": "E"},
    )

    metadata = _metadata(mock_audit_logger, "risk.updated")
    assert metadata["changes"] == {
        "likelihood": {"old": "C", "new": "E"},
        "risk_level": {"old": "high", "new": "medium"},
        "residual_severity": {"old": None, "new": 4},
        "residual_likelihood": {"old": None, "new": "E"},
        "residual_risk_level": {"old": None, "new": "medium"},
        "ae_review_required": {"old": True, "new": False},
    }


async def test_risk_audit_rows_name_the_originating_chat(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
    mock_audit_logger: AsyncMock,
) -> None:
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        organization_id=test_organization.id,
        title="Hazard entry",
        function_type=FunctionType.RISK_REGISTER,
    )
    db_session.add(conversation)
    await db_session.flush()
    conversation_id = str(conversation.id)
    created = await client.post(
        "/api/v1/risks", json=_payload(conversation_id=conversation_id, source="rmp_sp4")
    )
    assert created.status_code == 201
    risk_id = created.json()["data"]["id"]
    await client.patch(f"/api/v1/risks/{risk_id}", json={"title": "Renamed"})
    await client.delete(f"/api/v1/risks/{risk_id}")

    for action in ("risk.created", "risk.updated", "risk.deleted"):
        assert _metadata(mock_audit_logger, action)["conversation_id"] == conversation_id
    assert _metadata(mock_audit_logger, "risk.deleted")["title"] == "Renamed"


async def test_mitigation_update_audit_row_carries_before_and_after_values(
    client: AsyncClient, mock_audit_logger: AsyncMock
) -> None:
    risk_id = (await client.post("/api/v1/risks", json=_payload())).json()["data"]["id"]
    mitigation = await client.post(
        f"/api/v1/risks/{risk_id}/mitigations",
        json={"title": "Escort", "description": "Escort", "assignee": "Chief Pilot Liaison"},
    )
    mitigation_id = mitigation.json()["data"]["id"]

    await client.patch(
        f"/api/v1/risks/{risk_id}/mitigations/{mitigation_id}",
        json={"assignee": None, "due_date": "2026-12-31T00:00:00"},
    )

    metadata = _metadata(mock_audit_logger, "mitigation.updated")
    assert metadata["risk_id"] == risk_id
    assert metadata["changes"] == {
        "assignee": {"old": "Chief Pilot Liaison", "new": None},
        "due_date": {"old": None, "new": "2026-12-31T00:00:00"},
    }
