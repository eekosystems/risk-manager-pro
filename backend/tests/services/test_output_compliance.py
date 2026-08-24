"""Tests for post-generation output compliance checks.

Fixtures mirror the structure of real PVD CSPP analysis outputs (hazard headings,
control blocks, scoring lines) without reproducing client content.
"""

import json

from app.services.output_compliance import (
    build_compliance_notice,
    check_analysis_output,
    extract_rr_payload,
    find_hazards_missing_disposition,
    find_incomplete_hierarchy,
    find_unsupported_infrastructure,
    split_hazard_sections,
)

COMPLIANT_HAZARD = """
H1 – Vehicle Incursion Into Active Movement Area
Primary Worst Credible Outcome A construction vehicle enters an active taxiway.
Initial Risk
• Initial cell: 3B – High.
Controls (Hierarchy of Controls)
• Avoid/Eliminate: not feasible; the work cannot be relocated off the airfield.
• Substitute: ruled out; no lower-hazard construction method available.
• Engineer: barricades and low-profile lighting at all access points.
• Administrative: escort procedures and daily briefings.
• PPE: high-visibility vests required for all personnel.
Residual Risk
• Residual cell: 2C – Medium.
Disposition: Accept with conditions, subject to the escort procedure being audited weekly.
"""

NONCOMPLIANT_HAZARD = """
H2 – Mis-Marked Closures and Barricades
Primary Worst Credible Outcome An aircraft taxis into an active construction zone.
Initial Risk
• Initial cell: 3B – High.
Controls
• Engineer: barricades with retroreflective markers.
• Administrative: daily inspection of closure markings.
Residual Risk
• Residual cell: 2B – Medium.
ALARP: risk is as low as reasonably practicable given the phasing constraints.
"""


# --- Structured payload -------------------------------------------------------


def test_extracts_payload_from_rr_payload_block() -> None:
    content = 'Summary text.\n<rr_payload>{"hazards": [{"id": "H1"}]}</rr_payload>'

    payload = extract_rr_payload(content)

    assert payload == {"hazards": [{"id": "H1"}]}


def test_extracts_payload_wrapped_in_a_fenced_code_block() -> None:
    """The model sometimes wraps the block in ```json despite instructions."""
    content = '<rr_payload>\n```json\n{"hazards": []}\n```\n</rr_payload>'

    assert extract_rr_payload(content) == {"hazards": []}


def test_missing_payload_returns_none() -> None:
    assert extract_rr_payload("A hazard list with no payload block.") is None


def test_unparseable_payload_is_treated_as_missing() -> None:
    assert extract_rr_payload("<rr_payload>{not valid json</rr_payload>") is None


def test_phl_without_payload_is_flagged() -> None:
    issues = check_analysis_output("Hazard list prose only.", is_sra=False, is_phl=True)

    assert [i.label for i in issues] == ["Structured Risk Register Payload"]


def test_phl_with_payload_is_not_flagged() -> None:
    content = "Hazards.\n<rr_payload>" + json.dumps({"hazards": [1]}) + "</rr_payload>"

    assert check_analysis_output(content, is_sra=False, is_phl=True) == []


def test_payload_is_not_required_on_an_sra() -> None:
    assert check_analysis_output(COMPLIANT_HAZARD, is_sra=True, is_phl=False) == []


# --- Hazard sectioning --------------------------------------------------------


def test_splits_numbered_hazard_sections() -> None:
    sections = split_hazard_sections(COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD)

    assert [s.label for s in sections] == ["H1", "H2"]
    assert "Accept with conditions" in sections[0].body
    assert "Accept with conditions" not in sections[1].body


def test_recognizes_the_long_hazard_heading_form() -> None:
    content = "Hazard 1 – Slips\nbody one\nHazard 2 – Falls\nbody two\n"

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_single_hazard_output_is_not_sectioned() -> None:
    """One narrative hazard must not be treated as a per-hazard structure."""
    assert split_hazard_sections("H1 – Only hazard\nbody") == []


def test_a_hazard_restated_in_a_summary_does_not_create_a_second_section() -> None:
    content = "H1 – A\nbody\nH2 – B\nbody\nH1 – A (summary row)\n"

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_recognizes_the_hazard_h1_heading_form() -> None:
    """Real outputs also head sections "Hazard H1 – Title"."""
    content = "Hazard H1 – Passenger Exposure\nbody\nHazard H2 – V/PD in Work Area\nbody\n"

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_bare_numbered_hazards_with_scoring_are_sectioned() -> None:
    """One PHL format numbers hazards plainly, with no H prefix."""
    content = (
        "Preliminary Hazard List\n"
        "1. Mis-Marked Closures\nLikelihood 3, Severity B – 3B.\n"
        "2. Aircraft/Vehicle Conflicts\nInitial risk 2C.\n"
    )

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_a_plain_numbered_list_is_not_mistaken_for_hazards() -> None:
    """Guards the bare-numbering fallback against ordinary prose lists."""
    content = (
        "Mandatory Process\n"
        "1. Retrieve the correct risk matrix.\n"
        "2. Search indexed FG SRM documents.\n"
        "3. Assign categories.\n"
    )

    assert split_hazard_sections(content) == []


# --- Disposition --------------------------------------------------------------


def test_hazard_without_a_disposition_is_reported() -> None:
    sections = split_hazard_sections(COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD)

    assert find_hazards_missing_disposition(sections) == ["H2"]


def test_alarp_language_alone_does_not_satisfy_the_disposition_requirement() -> None:
    sections = split_hazard_sections(
        "H1 – A\nALARP achieved.\nH2 – B\nRisk is as low as reasonably practicable.\n"
    )

    assert find_hazards_missing_disposition(sections) == ["H1", "H2"]


def test_acceptable_does_not_count_as_an_accept_disposition() -> None:
    """ "Acceptable"/"acceptance" are scoring prose, not a decision."""
    sections = split_hazard_sections(
        "H1 – A\nResidual risk is acceptable pending review.\nH2 – B\nRisk acceptance criteria met.\n"
    )

    assert find_hazards_missing_disposition(sections) == ["H1", "H2"]


def test_reject_disposition_is_recognized() -> None:
    sections = split_hazard_sections(
        "H1 – A\nDisposition: Reject — requires further mitigation.\nH2 – B\nAccept.\n"
    )

    assert find_hazards_missing_disposition(sections) == []


# --- Hierarchy of controls ----------------------------------------------------


def test_reports_the_hierarchy_levels_a_hazard_never_addresses() -> None:
    sections = split_hazard_sections(COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD)

    incomplete = find_incomplete_hierarchy(sections)

    assert "H1" not in incomplete
    assert incomplete["H2"] == ["Avoid/Eliminate", "Substitute", "PPE"]


def test_a_level_ruled_out_in_words_still_counts_as_addressed() -> None:
    """Explicitly ruling a level out satisfies the requirement."""
    sections = split_hazard_sections(
        "H1 – A\nAvoid: not feasible. Substitute: none available. Engineer: x. "
        "Administrative: y. PPE: none required.\n"
        "H2 – B\nEngineer only.\n"
    )

    incomplete = find_incomplete_hierarchy(sections)

    assert "H1" not in incomplete
    assert incomplete["H2"] == ["Avoid/Eliminate", "Substitute", "Administrative", "PPE"]


def test_sra_issues_name_the_affected_hazards() -> None:
    issues = check_analysis_output(
        COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD, is_sra=True, is_phl=False
    )

    labels = {i.label for i in issues}
    assert labels == {"Per-Hazard Risk Disposition", "Hierarchy of Controls Coverage"}
    disposition = next(i for i in issues if i.label == "Per-Hazard Risk Disposition")
    assert "H2" in disposition.detail
    assert "H1" not in disposition.detail


# --- Infrastructure grounding -------------------------------------------------


def test_taxiway_absent_from_the_source_is_flagged() -> None:
    """The PVD failure: an invented taxiway in an otherwise grounded analysis."""
    output = "Movement area: Taxiway T, Taxiway V, Taxiway M, Taxiway Y."
    source = "The project affects Taxiways E, M, T, and V during Phase 1."

    assert find_unsupported_infrastructure(output, source) == ["Taxiway Y"]


def test_taxiways_named_in_a_list_in_the_source_are_accepted() -> None:
    output = "Work occurs on Taxiway E and Taxiway M."
    source = "Taxiways E, M, T and V are within the project limits."

    assert find_unsupported_infrastructure(output, source) == []


def test_runway_designators_are_checked_too() -> None:
    output = "Operations continue on Runway 16-34 and Runway 09-27."
    source = "The airport operates Runway 16-34 as its primary runway."

    assert find_unsupported_infrastructure(output, source) == ["Runway 09", "Runway 27"]


def test_runway_numbers_match_with_or_without_a_leading_zero() -> None:
    """FAA drops the leading zero, ICAO keeps it; both name the same runway."""
    output = "Construction is adjacent to Runway 5-23."
    source = "Runway 05-23 remains open throughout the project."

    assert find_unsupported_infrastructure(output, source) == []


def test_no_retrieved_text_means_no_infrastructure_claims_are_made() -> None:
    """A grounding miss is reported separately; don't double-report it here."""
    assert find_unsupported_infrastructure("Taxiway Y is closed.", "") == []


def test_source_naming_no_taxiways_suppresses_the_check() -> None:
    """Avoids false positives when the corpus simply doesn't discuss taxiways."""
    output = "Taxiway Y is closed."
    source = "This document covers terminal escalator maintenance procedures."

    assert find_unsupported_infrastructure(output, source) == []


def test_prose_after_taxiway_is_not_read_as_a_designator() -> None:
    output = "Taxiway closures are coordinated. The taxiway is active."
    source = "Taxiway E is closed."

    assert find_unsupported_infrastructure(output, source) == []


# --- Notice rendering ---------------------------------------------------------


def test_notice_lists_every_issue_and_marks_the_output_as_draft() -> None:
    issues = check_analysis_output(
        NONCOMPLIANT_HAZARD + COMPLIANT_HAZARD, is_sra=True, is_phl=False
    )

    notice = build_compliance_notice(issues)

    assert "Output Compliance Notice" in notice
    assert "draft pending review" in notice
    assert "Per-Hazard Risk Disposition" in notice
    assert "Hierarchy of Controls Coverage" in notice


def test_compliant_output_produces_no_issues() -> None:
    content = (
        COMPLIANT_HAZARD
        + "\nH3 – Second Hazard\n"
        + "Avoid: not feasible. Substitute: none. Engineer: barrier. "
        + "Administrative: briefing. PPE: vests.\nDisposition: Accept.\n"
    )

    assert check_analysis_output(content, is_sra=True, is_phl=False) == []
