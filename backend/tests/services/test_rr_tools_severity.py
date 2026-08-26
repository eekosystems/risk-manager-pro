"""Severity translation at the Risk Register tool boundary.

Analysis outputs and the Risk Register matrix both label severity by column,
1-Catastrophic through 5-Minimal. Storage runs the other way. This is the one
place the two conventions meet, so getting it wrong plots a Catastrophic hazard
in the Minimal corner.
"""

import pytest

from app.models.risk import RiskLevel, compute_risk_level
from app.services.rr_tools import _display_severity_to_stored


@pytest.mark.parametrize(
    ("displayed", "stored"),
    [(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)],
)
def test_display_severity_maps_to_stored(displayed: int, stored: int) -> None:
    assert _display_severity_to_stored(displayed) == stored


def test_conversion_is_its_own_inverse() -> None:
    for value in range(1, 6):
        assert _display_severity_to_stored(_display_severity_to_stored(value)) == value


@pytest.mark.parametrize("bad", [0, 6, -1, 99])
def test_out_of_range_severity_is_rejected(bad: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        _display_severity_to_stored(bad)


def test_non_numeric_severity_is_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        _display_severity_to_stored("catastrophic")


@pytest.mark.parametrize(
    ("cell", "expected_band"),
    [
        # Read straight off the Risk Register matrix: rows A-E, columns 1-5.
        ("A1", RiskLevel.HIGH),  # Frequent + Catastrophic
        ("A5", RiskLevel.LOW),  # Frequent + Minimal
        ("E1", RiskLevel.MEDIUM),  # Extremely Improbable + Catastrophic
        ("E5", RiskLevel.LOW),  # Extremely Improbable + Minimal
        ("C2", RiskLevel.HIGH),  # Remote + Hazardous
        ("C4", RiskLevel.LOW),  # Remote + Minor
        ("B3", RiskLevel.MEDIUM),  # Probable + Major
        ("D2", RiskLevel.MEDIUM),  # Extremely Remote + Hazardous
    ],
)
def test_matrix_cell_labels_land_in_the_band_the_chart_shows(
    cell: str, expected_band: RiskLevel
) -> None:
    """A cell label written in an SRA must score the same as the chart cell."""
    likelihood, displayed_severity = cell[0], int(cell[1])

    stored_severity = _display_severity_to_stored(displayed_severity)

    assert compute_risk_level(stored_severity, likelihood) is expected_band
