"""Validation of the SP3 residual re-assessment answer.

Nothing the model returns reaches a user as a proposal unless it has all five
tiers in order, a residual cell after each applied tier, residuals that never
get worse layer by layer, and citations limited to documents actually
retrieved. The band always comes from the FG 5x5.
"""

from typing import Any

import pytest

from app.models.risk import RiskLevel
from app.services.residual_reassessment_engine import (
    ERROR_INSUFFICIENT_BASIS,
    ERROR_INVALID_RESULT,
    Cell,
    ReassessmentRejectedError,
    parse_cell,
    parse_reassessment,
)

# C2 in FAA notation: Remote / Hazardous (stored severity 4) -- High.
INITIAL = Cell(likelihood="C", severity=4)


def _tier(name: str, cell: str | None) -> dict[str, Any]:
    if cell is None:
        return {
            "tier": name,
            "applied": False,
            "controls": "Not applicable -- no recorded mitigation at this tier",
            "residual_cell": None,
        }
    return {"tier": name, "applied": True, "controls": f"{name} control", "residual_cell": cell}


def _payload(*cells: str | None, **overrides: Any) -> dict[str, Any]:
    names = ["Avoid/Eliminate", "Substitute", "Engineer", "Administrative", "PPE"]
    payload: dict[str, Any] = {
        "tiers": [_tier(name, cell) for name, cell in zip(names, cells, strict=True)],
        "alarp_status": "ALARP achieved; AE acceptance not required",
        "rationale": "Barricades and NOTAM reduce exposure.",
        "sources": ["DEN SRMD 2024.pdf"],
        "insufficient_basis": False,
    }
    payload.update(overrides)
    return payload


def test_residual_is_the_cell_after_the_last_applied_tier() -> None:
    parsed = parse_reassessment(
        _payload(None, None, "D2", "D3", None), INITIAL, {"DEN SRMD 2024.pdf"}
    )

    assert parsed.residual == Cell(likelihood="D", severity=3)
    assert parsed.residual.label == "D3"
    engineer = parsed.result.tiers[2]
    assert (engineer.residual_likelihood, engineer.residual_severity) == ("D", 4)
    assert engineer.residual_risk_level == RiskLevel.MEDIUM
    assert [t.applied for t in parsed.result.tiers] == [False, False, True, True, False]


def test_no_applied_tier_leaves_the_initial_cell() -> None:
    parsed = parse_reassessment(_payload(None, None, None, None, None), INITIAL, set())
    assert parsed.residual == INITIAL


def test_band_comes_from_the_matrix_not_the_model() -> None:
    payload = _payload(None, None, "E2", None, None)
    payload["tiers"][2]["residual_risk_level"] = "low"
    parsed = parse_reassessment(payload, INITIAL, set())
    assert parsed.result.tiers[2].residual_risk_level == RiskLevel.MEDIUM


def test_uncited_sources_are_dropped() -> None:
    parsed = parse_reassessment(
        _payload(None, None, "D2", None, None, sources=["DEN SRMD 2024.pdf", "Invented.pdf"]),
        INITIAL,
        {"DEN SRMD 2024.pdf"},
    )
    assert parsed.result.sources == ["DEN SRMD 2024.pdf"]


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (None, "not a JSON object"),
        (_payload(None, None, "D2", None, None, tiers=[]), "all five hierarchy tiers"),
        (_payload(None, None, "B2", None, None), "worse"),
        (_payload(None, None, "D2", "D1", None), "worse"),
        (_payload(None, None, "D2", "2D", None), "no valid residual cell"),
        (_payload(None, None, "D2", None, None, alarp_status=""), "ALARP"),
    ],
)
def test_malformed_answers_are_rejected(payload: dict[str, Any] | None, reason: str) -> None:
    with pytest.raises(ReassessmentRejectedError) as exc:
        parse_reassessment(payload, INITIAL, set())
    assert exc.value.code == ERROR_INVALID_RESULT
    assert reason in exc.value.detail


def test_tiers_out_of_order_are_rejected() -> None:
    payload = _payload(None, None, "D2", None, None)
    payload["tiers"][0], payload["tiers"][1] = payload["tiers"][1], payload["tiers"][0]
    with pytest.raises(ReassessmentRejectedError, match="expected tier Avoid/Eliminate"):
        parse_reassessment(payload, INITIAL, set())


def test_insufficient_basis_is_its_own_failure() -> None:
    with pytest.raises(ReassessmentRejectedError) as exc:
        parse_reassessment(
            _payload(None, None, None, None, None, insufficient_basis=True), INITIAL, set()
        )
    assert exc.value.code == ERROR_INSUFFICIENT_BASIS


@pytest.mark.parametrize(
    ("label", "cell"),
    [("A1", Cell("A", 5)), ("e5", Cell("E", 1)), (" D3 ", Cell("D", 3))],
)
def test_cell_labels_read_letter_first_faa_severity(label: str, cell: Cell) -> None:
    assert parse_cell(label) == cell


@pytest.mark.parametrize("label", ["1A", "F2", "A6", "", None, 3])
def test_invalid_cell_labels(label: object) -> None:
    assert parse_cell(label) is None
