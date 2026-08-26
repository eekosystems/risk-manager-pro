"""Detection of FAA 5x5 matrix notation in SRA output.

An SRA that renders only qualitative bands ("High", "Medium") is non-compliant,
so the detector decides whether the alphanumeric cell label actually made it
into the response. Cell labels are likelihood-letter then severity-number
("C2"), the same way the Risk Register matrix reads.
"""

import pytest

from app.services.chat import _has_matrix_cell_notation


@pytest.mark.parametrize(
    "content",
    [
        "Initial Risk: C2 (High / Hazardous)",
        "Residual Risk: E5 (Low)",
        "Initial Risk: A1 (Frequent / Catastrophic) — High",
        "Likelihood: C, Severity: 2",
        "Likelihood C and Severity 3 give a Medium band.",
    ],
)
def test_cell_labels_and_scoring_prose_are_detected(content: str) -> None:
    assert _has_matrix_cell_notation(content) is True


@pytest.mark.parametrize(
    "content",
    [
        "Initial risk is High and residual risk is Medium.",
        "The hazard was scored as Hazardous and Remote.",
    ],
)
def test_qualitative_bands_alone_are_not_notation(content: str) -> None:
    assert _has_matrix_cell_notation(content) is False


@pytest.mark.parametrize(
    "content",
    [
        "Taxiway A1 was closed for construction.",
        "Taxiways A1, B2 and C3 are affected by the closure.",
        "Runway B1 hold position markings are faded.",
        "Gate B2 congestion during the peak bank.",
    ],
)
def test_infrastructure_designators_are_not_cell_labels(content: str) -> None:
    """A designator like Taxiway A1 has the shape of a cell label but scores nothing."""
    assert _has_matrix_cell_notation(content) is False


def test_a_designator_does_not_mask_a_real_score_elsewhere() -> None:
    content = "Taxiway A1 conflict with construction vehicles scored C2 (High)."

    assert _has_matrix_cell_notation(content) is True


def test_the_english_article_after_likelihood_is_not_a_likelihood_value() -> None:
    """In "the likelihood a vehicle enters", the "a" is an article, not a rating."""
    content = "This raises the likelihood a vehicle enters the RSA unescorted."

    assert _has_matrix_cell_notation(content) is False


def test_reversed_cell_order_is_not_accepted() -> None:
    """Writing 1A instead of A1 inverts the score, so it must be flagged."""
    assert _has_matrix_cell_notation("Initial Risk: 1A") is False
