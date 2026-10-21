"""Residual risk at the Risk Register tool boundary.

The chat used to hand over a residual band with no cell, so the register
showed only the initial cell. The tool now takes the residual cell in the
same column numbering as the initial one, inverts it for storage, and lets
the service compute the band.
"""

import json
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from app.models.risk import RiskLevel
from app.services.rr_tools import execute_tool_call
from tests.conftest import ORGANIZATION_ID, make_test_user

if TYPE_CHECKING:
    from app.schemas.risk import CreateRiskEntryRequest


def _save_call(**extra: object) -> dict[str, str]:
    args: dict[str, object] = {
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
        **extra,
    }
    return {"id": "call_1", "name": "save_risk_register_record", "arguments": json.dumps(args)}


def _service(entry: SimpleNamespace | None = None) -> AsyncMock:
    service = AsyncMock()
    service.create_risk_entry.return_value = entry or SimpleNamespace(
        id=uuid.uuid4(),
        severity=4,
        likelihood="C",
        risk_level=RiskLevel.HIGH,
        residual_severity=None,
        residual_likelihood=None,
        residual_risk_level=None,
        ae_review_required=True,
        airport_identifier="SUS",
    )
    return service


async def _run(service: AsyncMock, call: dict[str, str]) -> dict[str, object]:
    raw = await execute_tool_call(
        tool_call=call,
        risk_service=service,
        sharepoint=AsyncMock(),
        audit=None,
        user=make_test_user(),
        organization_id=ORGANIZATION_ID,
        conversation_id=uuid.uuid4(),
    )
    result: dict[str, object] = json.loads(raw)
    return result


async def test_residual_cell_is_inverted_like_the_initial_cell() -> None:
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        severity=4,
        likelihood="C",
        risk_level=RiskLevel.HIGH,
        residual_severity=4,
        residual_likelihood="E",
        residual_risk_level=RiskLevel.MEDIUM,
        ae_review_required=True,
        airport_identifier="SUS",
    )
    service = _service(entry)

    result = await _run(
        service,
        _save_call(residual_severity=2, residual_likelihood="E", disposition="accept"),
    )

    payload: CreateRiskEntryRequest = service.create_risk_entry.call_args.kwargs["payload"]
    assert (payload.residual_severity, payload.residual_likelihood) == (4, "E")
    assert payload.disposition == "accept"
    assert (result["residual_cell"], result["residual_risk_level"]) == ("E2", "medium")
    assert result["ae_review_required"] is True


async def test_half_a_residual_cell_is_sent_back_for_correction() -> None:
    service = _service()

    result = await _run(service, _save_call(residual_likelihood="E"))

    assert result["ok"] is False
    assert "residual_severity and residual_likelihood go together" in str(result["error"])
    service.create_risk_entry.assert_not_called()


async def test_a_band_without_a_cell_is_ignored() -> None:
    service = _service()

    result = await _run(service, _save_call(residual_risk_level="high"))

    assert result["ok"] is True
    payload: CreateRiskEntryRequest = service.create_risk_entry.call_args.kwargs["payload"]
    assert (payload.residual_severity, payload.residual_likelihood) == (None, None)
    assert result["residual_cell"] is None


async def test_source_document_name_is_carried_to_the_record() -> None:
    service = _service()

    await _run(service, _save_call(source_document_name="SUS Taxiway Alpha CSPP.pdf"))

    payload: CreateRiskEntryRequest = service.create_risk_entry.call_args.kwargs["payload"]
    assert payload.source_document_name == "SUS Taxiway Alpha CSPP.pdf"


async def test_chat_saved_record_is_pending_whatever_the_model_says() -> None:
    service = _service()

    result = await _run(service, _save_call(validation_status="rmp_validated"))

    assert result["ok"] is True
    payload: CreateRiskEntryRequest = service.create_risk_entry.call_args.kwargs["payload"]
    assert payload.validation_status == "pending"
