"""Residual cell and mitigations extracted from SRMD reports.

The Risk Register shows each SRMD hazard's initial risk, residual risk and
mitigations side by side, so the importer keeps the residual pair and the
verbatim mitigation list the document states instead of discarding them.
"""

from typing import Any

import pytest

from app.services import risk_outcome_importer
from app.services.risk_outcome_importer import _extract_risks_via_llm, _risk_from_dict


async def _extract(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> Any:
    async def fake_chunk(**_: Any) -> tuple[list[dict[str, Any]], None]:
        return rows, None

    monkeypatch.setattr(risk_outcome_importer, "_extract_risks_from_chunk", fake_chunk)
    return await _extract_risks_via_llm(
        text="SRMD body",
        airport="DEN",
        source_file="srmd.pdf",
        source_url=None,
        openai_client=None,  # type: ignore[arg-type]
    )


async def test_residual_pair_and_mitigations_are_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    risks, notes = await _extract(
        monkeypatch,
        [
            {
                "hazard": "Contractors and Haul Rts. - Accident between AC and Veh.",
                "severity": "Hazardous",
                "likelihood": "Remote",
                "residual_severity": "Hazardous",
                "residual_likelihood": "Extremely Improbable",
                "mitigations": [
                    "Escort all haul vehicles across the movement area",
                    "  ",
                    "escort all haul vehicles across the movement area",
                    "Issue NOTAM for haul route",
                ],
            }
        ],
    )
    assert notes == []
    [risk] = risks
    assert (risk.residual_likelihood, risk.residual_severity) == ("E", 4)
    assert risk.residual_risk_level == "medium"
    assert risk.mitigations == [
        "Escort all haul vehicles across the movement area",
        "Issue NOTAM for haul route",
    ]


async def test_half_a_residual_cell_is_dropped_with_a_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    risks, notes = await _extract(
        monkeypatch,
        [
            {
                "hazard": "FOD",
                "severity": "Minor",
                "likelihood": "Remote",
                "residual_likelihood": "Extremely Remote",
            }
        ],
    )
    [risk] = risks
    assert risk.residual_likelihood is None and risk.residual_severity is None
    assert risk.residual_risk_level is None
    assert "half a residual cell" in notes[0].message


async def test_no_residual_or_mitigations_stated(monkeypatch: pytest.MonkeyPatch) -> None:
    risks, _ = await _extract(
        monkeypatch,
        [{"hazard": "FOD", "severity": "Minor", "likelihood": "Remote", "mitigations": "none"}],
    )
    [risk] = risks
    assert risk.residual_risk_level is None
    assert risk.mitigations == []


def test_cached_row_keeps_residual_and_mitigations() -> None:
    risk = _risk_from_dict(
        {
            "airport_identifier": "DEN",
            "hazard": "FOD",
            "severity": 2,
            "likelihood": "C",
            "risk_level": "medium",
            "source_file": "srmd.pdf",
            "source_url": None,
            "residual_severity": 2,
            "residual_likelihood": "D",
            "residual_risk_level": "medium",
            "mitigations": ["Sweep daily"],
        }
    )
    assert risk.residual_risk_level == "low"
    assert risk.mitigations == ["Sweep daily"]
