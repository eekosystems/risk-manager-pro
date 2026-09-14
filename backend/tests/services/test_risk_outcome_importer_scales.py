"""Scale parsing at the SharePoint import boundary.

Client documents print the FAA 5x5 the FAA way: severity 1 is Catastrophic,
likelihood A is Frequent. Storage keeps severity the other way (5 =
Catastrophic), so a digit read straight through lands a Catastrophic hazard in
the Minimal column. Names are unambiguous and must win over any symbol that
happens to sit beside them.
"""

import pytest

from app.services.risk_outcome_importer import (
    _normalize_likelihood,
    _normalize_severity,
)


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        ("Catastrophic", 5),
        ("Hazardous", 4),
        ("Major", 3),
        ("Minor", 2),
        ("Minimal", 1),
        ("Negligible", 1),
        ("Critical", 4),
        ("Severe", 5),
        ("Moderate", 3),
    ],
)
def test_severity_names_map_to_stored_scale(value: str, stored: int) -> None:
    assert _normalize_severity(value) == stored


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        ("Catastrophic (1)", 5),
        ("Hazardous (2)", 4),
        ("1 - Catastrophic", 5),
        ("5 Minimal", 1),
        ("Sev 2 Hazardous", 4),
    ],
)
def test_name_beside_a_digit_is_read_by_name(value: str, stored: int) -> None:
    assert _normalize_severity(value) == stored


@pytest.mark.parametrize(
    ("value", "stored"),
    [("1", 5), ("2", 4), ("3", 3), ("4", 2), ("5", 1), (1, 5), (5, 1), (2.0, 4)],
)
def test_bare_severity_digit_reads_the_faa_way(value: object, stored: int) -> None:
    assert _normalize_severity(value) == stored


@pytest.mark.parametrize(("value", "stored"), [("A", 5), ("c", 3), ("E", 1)])
def test_letter_severity_treats_a_as_most_severe(value: str, stored: int) -> None:
    assert _normalize_severity(value) == stored


@pytest.mark.parametrize("value", [None, "", "   ", "unknown", "6", "f", True])
def test_unreadable_severity_is_skipped(value: object) -> None:
    assert _normalize_severity(value) is None


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("Frequent", "A"),
        ("Probable", "B"),
        ("Occasional", "B"),
        ("Remote", "C"),
        ("Extremely Remote", "D"),
        ("Improbable", "D"),
        ("Extremely Improbable", "E"),
        ("C - Remote", "C"),
        ("Remote (C)", "C"),
        ("a", "A"),
        ("E", "E"),
        ("5", "A"),
        ("1", "E"),
    ],
)
def test_likelihood_values(value: str, code: str) -> None:
    assert _normalize_likelihood(value) == code


def test_longer_likelihood_name_wins_over_its_substring() -> None:
    # "improbable" contains "probable" and "extremely remote" contains "remote".
    assert _normalize_likelihood("extremely improbable") == "E"
    assert _normalize_likelihood("improbable") == "D"
    assert _normalize_likelihood("extremely remote") == "D"


@pytest.mark.parametrize("value", [None, "", "never", "6"])
def test_unreadable_likelihood_is_skipped(value: object) -> None:
    assert _normalize_likelihood(value) is None
