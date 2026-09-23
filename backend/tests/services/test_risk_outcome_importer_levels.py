"""Risk band for SharePoint-imported hazards.

The Risk Register plots every hazard on the FG 5x5 by its likelihood/severity
cell, so the band on the hazard's badge must come from that same cell. A band
the source document states under its own matrix must never override it.
"""

from typing import Any

import pytest

from app.services import risk_outcome_importer
from app.services.risk_outcome_importer import (
    _extract_risks_via_llm,
    _risk_from_dict,
)


def _cached_row(severity: int, likelihood: str, risk_level: str) -> dict[str, Any]:
    return {
        "airport_identifier": "DEN",
        "hazard": "FOD - Clean Soil hauled into site",
        "severity": severity,
        "likelihood": likelihood,
        "risk_level": risk_level,
        "source_file": "srmd.pdf",
        "source_url": None,
    }


@pytest.mark.parametrize(
    ("severity", "likelihood", "stale", "level"),
    [
        (1, "D", "medium", "low"),
        (2, "D", "medium", "low"),
        (3, "D", "low", "medium"),
        (5, "A", "low", "high"),
    ],
)
def test_cached_row_band_follows_the_matrix(
    severity: int, likelihood: str, stale: str, level: str
) -> None:
    assert _risk_from_dict(_cached_row(severity, likelihood, stale)).risk_level == level


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


async def test_stated_band_does_not_override_the_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    risks, notes = await _extract(
        monkeypatch,
        [
            {
                "hazard": "FOD",
                "severity": "Minor",
                "likelihood": "Extremely Remote",
                "risk_level": "Medium",
            }
        ],
    )
    assert [r.risk_level for r in risks] == ["low"]
    assert len(notes) == 1
    assert "stated risk level medium" in notes[0].message
    assert "D4 (low)" in notes[0].message


async def test_matching_stated_band_adds_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    risks, notes = await _extract(
        monkeypatch,
        [
            {
                "hazard": "FOD",
                "severity": "Catastrophic",
                "likelihood": "Frequent",
                "risk_level": "High",
            }
        ],
    )
    assert [r.risk_level for r in risks] == ["high"]
    assert notes == []
