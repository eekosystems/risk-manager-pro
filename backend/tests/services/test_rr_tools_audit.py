"""Audit trail for records the Risk Register chat saves through tool calls.

A record the model saves is a state change like any other register write, so
it leaves the same `risk.created` and `mitigation.created` entries the
endpoints leave, naming the conversation it came from.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.risk import RiskLevel
from app.services.rr_tools import execute_tool_call
from tests.conftest import ORGANIZATION_ID, make_test_user

_CONVERSATION_ID = uuid.uuid4()


def _save_call(mitigations: list[dict[str, str]] | None = None) -> dict[str, str]:
    args = {
        "title": "Haul route crossing",
        "airport_identifier": "SUS",
        "hazard": "Haul trucks crossing Taxiway Alpha",
        "description": "Rehab contractor haul route crosses the active taxiway.",
        "potential_credible_outcome": "Vehicle/aircraft collision",
        "operational_domain": "movement_area",
        "hazard_category_5m": "human",
        "severity": 2,
        "likelihood": "C",
        "existing_controls": "Escort required",
        "mitigations": mitigations or [],
    }
    return {"id": "call_1", "name": "save_risk_register_record", "arguments": json.dumps(args)}


def _risk_service(entry_id: uuid.UUID, mitigation_id: uuid.UUID) -> AsyncMock:
    service = AsyncMock()
    service.create_risk_entry.return_value = SimpleNamespace(
        id=entry_id,
        severity=4,
        likelihood="C",
        risk_level=RiskLevel.HIGH,
        airport_identifier="SUS",
    )
    service.create_mitigation.return_value = SimpleNamespace(
        id=mitigation_id, title="Escort haul vehicles"
    )
    return service


async def test_saved_record_and_mitigation_are_audited_with_their_chat() -> None:
    entry_id, mitigation_id = uuid.uuid4(), uuid.uuid4()
    user = make_test_user()
    audit = AsyncMock()

    result = json.loads(
        await execute_tool_call(
            tool_call=_save_call(
                [{"title": "Escort haul vehicles", "description": "Escort every crossing"}]
            ),
            risk_service=_risk_service(entry_id, mitigation_id),
            sharepoint=AsyncMock(),
            audit=audit,
            user=user,
            organization_id=ORGANIZATION_ID,
            conversation_id=_CONVERSATION_ID,
        )
    )

    assert result["ok"] is True
    logged = [
        (c.kwargs["action"], c.kwargs["resource_type"], c.kwargs["resource_id"])
        for c in audit.log.call_args_list
    ]
    assert logged == [
        ("risk.created", "risk_entry", str(entry_id)),
        ("mitigation.created", "mitigation", str(mitigation_id)),
    ]
    for call in audit.log.call_args_list:
        assert call.kwargs["user"] is user
        assert call.kwargs["organization_id"] == ORGANIZATION_ID
        assert call.kwargs["metadata"] == {
            "source": "rmp_sp4",
            "conversation_id": str(_CONVERSATION_ID),
        }


async def test_failed_save_leaves_no_audit_entry() -> None:
    service = AsyncMock()
    service.create_risk_entry.side_effect = RuntimeError("db down")
    audit = AsyncMock()

    result = json.loads(
        await execute_tool_call(
            tool_call=_save_call(),
            risk_service=service,
            sharepoint=AsyncMock(),
            audit=audit,
            user=make_test_user(),
            organization_id=ORGANIZATION_ID,
            conversation_id=_CONVERSATION_ID,
        )
    )

    assert result["ok"] is False
    audit.log.assert_not_called()


async def test_save_still_succeeds_without_an_audit_logger() -> None:
    entry_id = uuid.uuid4()

    result = json.loads(
        await execute_tool_call(
            tool_call=_save_call(),
            risk_service=_risk_service(entry_id, uuid.uuid4()),
            sharepoint=AsyncMock(),
            audit=None,
            user=make_test_user(),
            organization_id=ORGANIZATION_ID,
            conversation_id=_CONVERSATION_ID,
        )
    )

    assert (result["ok"], result["record_id"]) == (True, str(entry_id))
