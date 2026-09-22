"""Tests for post-generation output compliance checks.

Fixtures mirror the structure of real PVD CSPP analysis outputs (hazard headings,
control blocks, scoring lines) without reproducing client content.
"""

import json

from app.services.output_compliance import (
    build_compliance_notice,
    check_analysis_output,
    extract_rr_payload,
    find_band_mismatches,
    find_hazards_missing_disposition,
    find_incomplete_hierarchy,
    find_misordered_hierarchy,
    find_missing_layer_residuals,
    find_mistitled_citations,
    find_reversed_cell_labels,
    find_unreflected_closures,
    find_unsupported_infrastructure,
    matrix_bands,
    split_hazard_sections,
)

COMPLIANT_HAZARD = """
H1 – Vehicle Incursion Into Active Movement Area
Primary Worst Credible Outcome A construction vehicle enters an active taxiway.
Initial Risk
• Initial cell: C2 – High.
Controls (Hierarchy of Controls)
• Avoid/Eliminate: not feasible; the work cannot be relocated off the airfield.
• Substitute: ruled out; no lower-hazard construction method available.
• Engineer: barricades and low-profile lighting at all access points. Residual after this tier: D2 – Medium.
• Administrative: escort procedures and daily briefings. Residual after this tier: D2 – Medium.
• PPE: high-visibility vests required for all personnel. Residual after this tier: D2 – Medium.
Residual Risk
• Residual cell: D2 – Medium.
Disposition: Accept with conditions, subject to the escort procedure being audited weekly.
"""

NONCOMPLIANT_HAZARD = """
H2 – Mis-Marked Closures and Barricades
Primary Worst Credible Outcome An aircraft taxis into an active construction zone.
Initial Risk
• Initial cell: C2 – High.
Controls
• Engineer: barricades with retroreflective markers.
• Administrative: daily inspection of closure markings.
Residual Risk
• Residual cell: D2 – Medium.
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


def test_bare_numbered_hazards_scored_in_cell_notation_are_sectioned() -> None:
    """Scores now read letter-then-number ("C2"); sectioning must follow."""
    content = (
        "Preliminary Hazard List\n"
        "1. Mis-Marked Closures\nLikelihood C, Severity 2 – C2.\n"
        "2. Aircraft/Vehicle Conflicts\nInitial risk B3.\n"
    )

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_project_prefixed_hazard_ids_are_sectioned() -> None:
    """Real outputs weld a project code onto the id: "TWVH1 – …", "PVD-H2 – …"."""
    content = "TWVH1 – Aircraft Entering Closed TW V\nbody\nTWVH2 – Vehicle Intrusion\nbody\n"

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]

    content = "PVD-H1 – A\nbody\nPVD-H2 – B\nbody\n"

    assert [s.label for s in split_hazard_sections(content)] == ["H1", "H2"]


def test_an_ordinary_word_ending_in_h_is_not_a_hazard_id() -> None:
    """Only an upper-case prefix counts, so "Length 3" is not hazard 3."""
    content = "Length 3 of the taxiway\nbody\nLength 4 of the apron\nbody\n"

    assert split_hazard_sections(content) == []


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


def test_labeled_acceptable_status_counts_as_a_disposition() -> None:
    """Two of three reviewed SRAs wrote the decision as an ALARP Status value."""
    sections = split_hazard_sections(
        "H1 – A\nALARP Status: Acceptable with conditions – subject to review.\n"
        "H2 – B\nALARP: Acceptable with conditions.\n"
        "H3 – C\nDisposition: Not acceptable; further mitigation required.\n"
        "H4 – D\nOutcome: Unacceptable at current controls.\n"
    )

    assert find_hazards_missing_disposition(sections) == []


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


def test_a_level_ruled_out_on_its_own_line_counts_as_addressed() -> None:
    """Explicitly ruling a level out satisfies the requirement."""
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: not feasible.\n- Substitute: none available.\n"
        "- Engineer: x. Residual: D2 – Medium.\n- Administrative: y. Residual: D3 – Medium.\n"
        "- PPE: none required.\n"
        "H2 – B\nEngineer: barrier only.\n"
    )

    incomplete = find_incomplete_hierarchy(sections)

    assert "H1" not in incomplete
    assert incomplete["H2"] == ["Avoid/Eliminate", "Substitute", "Administrative", "PPE"]


def test_a_one_line_summary_naming_the_tiers_is_not_addressed() -> None:
    """The abbreviated form names every tier yet gives none its own line."""
    sections = split_hazard_sections(
        "H1 – A\nControls (hierarchy of controls summary): elimination and substitution "
        "are not practical here; engineering (barricades), administrative (escort "
        "procedures) and PPE (hi-vis) controls apply.\nResidual Risk: D3 – Medium.\n"
        "H2 – B\nAvoid: not feasible. Substitute: none. Engineer: x. Administrative: y. "
        "PPE: vests.\n"
    )

    incomplete = find_incomplete_hierarchy(sections)

    assert incomplete["H1"] == [
        "Avoid/Eliminate",
        "Substitute",
        "Engineer",
        "Administrative",
        "PPE",
    ]
    assert incomplete["H2"] == ["Substitute", "Engineer", "Administrative", "PPE"]


def test_tier_labels_are_recognised_as_bullets_headings_bold_and_table_rows() -> None:
    sections = split_hazard_sections(
        "H1 – A\n1. Avoid/Eliminate — not applicable; the circuit must be de-energised.\n"
        "#### Substitution\nNot applicable — no lower-hazard method.\n"
        "**Engineering controls:** portable lighting. Residual: D2 – Medium.\n"
        "| Administrative | NOTAM and daily brief | D3 – Medium |\n"
        "- PPE (Tier 5): hi-vis vests. Residual after this tier: D3 – Medium.\n"
        "H2 – B\nEngineer: barrier only.\n"
    )

    assert "H1" not in find_incomplete_hierarchy(sections)
    assert "H1" not in find_missing_layer_residuals(sections)


def test_a_merged_tier_label_addresses_neither_tier() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: not applicable.\n- Substitute: not applicable.\n"
        "- Engineer / Administrative: barricades and escorts. Residual: D2 – Medium.\n"
        "- PPE: vests. Residual: D2 – Medium.\n"
        "H2 – B\nEngineer: barrier only.\n"
    )

    assert find_incomplete_hierarchy(sections)["H1"] == ["Engineer", "Administrative"]


def test_reports_hazards_whose_tiers_are_out_of_order() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: n/a.\n- Substitute: n/a.\n- Engineer: x. Residual: D2.\n"
        "- Administrative: y. Residual: D2.\n- PPE: z. Residual: D2.\n"
        "H2 – B\n- Engineer: x. Residual: D2.\n- Avoid/Eliminate: n/a.\n- Substitute: n/a.\n"
        "- PPE: z. Residual: D2.\n- Administrative: y. Residual: D2.\n"
        "H3 – C\n- Engineer: x.\n- Avoid/Eliminate: n/a.\n"
    )

    # H3 is incomplete, not misordered: order is only judged on a full set.
    assert find_misordered_hierarchy(sections) == ["H2"]


# --- Residual risk per control layer -----------------------------------------


def test_reports_applied_tiers_with_no_residual_cell() -> None:
    sections = split_hazard_sections(COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD)

    unscored = find_missing_layer_residuals(sections)

    assert "H1" not in unscored
    assert unscored["H2"] == ["Engineer"]


def test_ruled_out_tiers_need_no_residual() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: Not applicable — the work cannot move.\n"
        "- Substitute: ruled out.\n- Engineer: N/A\n"
        "- Administrative: escorts. Residual after this tier: D2 – Medium.\n"
        "- PPE: no additional PPE required.\n"
        "H2 – B\n- Engineer: barrier.\n"
    )

    assert find_missing_layer_residuals(sections) == {"H2": ["Engineer"]}


def test_a_bare_label_reads_its_statement_from_the_next_line() -> None:
    sections = split_hazard_sections(
        "H1 – A\n#### Avoid/Eliminate\nNot applicable — the vault cannot be relocated.\n"
        "#### Substitute\nNot applicable.\n#### Engineer\nBarricades.\nResidual: D2 – Medium.\n"
        "#### Administrative\nEscorts.\n#### PPE\nNot applicable.\n"
        "H2 – B\n- Engineer: barrier.\n"
    )

    assert find_missing_layer_residuals(sections)["H1"] == ["Administrative"]


def test_the_initial_cell_on_a_tier_line_is_not_its_residual() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: n/a.\n- Substitute: n/a.\n"
        "- Engineer: barricades reduce the initial C2 exposure.\n"
        "- Administrative: escorts (initial C2 → D2).\n- PPE: n/a.\n"
        "H2 – B\n- Engineer: barrier.\n"
    )

    assert find_missing_layer_residuals(sections)["H1"] == ["Engineer"]


def test_a_residual_per_layer_table_can_supply_the_cells() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: n/a.\n- Substitute: n/a.\n- Engineer: barricades.\n"
        "- Administrative: escorts.\n- PPE: vests.\n"
        "| Layer | Residual |\n| Engineer | D2 – Medium |\n| Administrative | D3 – Medium |\n"
        "| PPE | D3 – Medium |\n"
        "H2 – B\n- Engineer: barrier.\n"
    )

    assert "H1" not in find_missing_layer_residuals(sections)


def test_an_infrastructure_designator_is_not_a_residual_cell() -> None:
    sections = split_hazard_sections(
        "H1 – A\n- Avoid/Eliminate: n/a.\n- Substitute: n/a.\n"
        "- Engineer: barricades at Taxiway B2.\n- Administrative: n/a.\n- PPE: n/a.\n"
        "H2 – B\n- Engineer: barrier.\n"
    )

    assert find_missing_layer_residuals(sections)["H1"] == ["Engineer"]


def test_sra_issues_name_the_affected_hazards() -> None:
    issues = check_analysis_output(
        COMPLIANT_HAZARD + NONCOMPLIANT_HAZARD, is_sra=True, is_phl=False
    )

    labels = {i.label for i in issues}
    assert labels == {
        "Per-Hazard Risk Disposition",
        "Hierarchy of Controls Coverage",
        "Residual Risk Per Control Layer",
    }
    for label in labels:
        issue = next(i for i in issues if i.label == label)
        assert "H2" in issue.detail
        assert "H1" not in issue.detail


def test_sra_issue_names_out_of_order_tiers() -> None:
    content = COMPLIANT_HAZARD + (
        "\nH2 – Reordered\n- PPE: vests. Residual: D2 – Medium.\n- Avoid/Eliminate: n/a.\n"
        "- Substitute: n/a.\n- Engineer: x. Residual: D2 – Medium.\n"
        "- Administrative: y. Residual: D2 – Medium.\nDisposition: Accept.\n"
    )

    issues = check_analysis_output(content, is_sra=True, is_phl=False)

    assert [i.label for i in issues] == ["Hierarchy of Controls Coverage"]
    assert "tiers out of order in H2" in issues[0].detail


# --- Risk band consistency ----------------------------------------------------


def test_matrix_bands_follow_the_risk_register_matrix() -> None:
    # C2 is Remote / Hazardous; the displayed severity 2 is stored as 4.
    assert matrix_bands("C2") == {"high"}
    assert matrix_bands("D2") == {"medium"}
    assert matrix_bands("E2") == {"medium"}
    assert matrix_bands("E3") == {"low"}
    assert matrix_bands("A1") == {"high"}


def test_split_cell_d1_accepts_either_band() -> None:
    assert find_band_mismatches("Residual: E1 – High.\nResidual: E1 – Medium.") == []


def test_band_matching_the_matrix_is_not_reported() -> None:
    content = (
        "Initial Risk: C2 (Remote / Hazardous) — High.\n"
        "Residual Risk: D2 – Medium (row D Extremely Remote, column 2 Hazardous).\n"
        "| E5 | Low |"
    )

    assert find_band_mismatches(content) == []


def test_band_disagreeing_with_the_matrix_is_reported_once() -> None:
    """The PVD defect: the same cell was High in one project and Medium in another."""
    content = (
        "H1 – Lighting\nInitial risk cell: C2, Medium (row C Remote, column 2 Hazardous).\n"
        "H2 – Markings\nInitial risk cell: C2, Medium.\n"
        "H3 – NOTAMs\nInitial risk cell: C2, High.\n"
    )

    assert find_band_mismatches(content) == ["C2 stated Medium (matrix: High)"]


def test_band_is_not_read_across_a_sentence_or_another_cell() -> None:
    content = (
        "Residual: C2 (Remote / Hazardous). Risk is as low as reasonably practicable.\n"
        "Reduced from C2 to D2, taking the band from High to Medium.\n"
    )

    assert find_band_mismatches(content) == []


def test_a_designator_is_not_read_as_a_cell() -> None:
    assert find_band_mismatches("Taxiway C2 carries high traffic at night.") == []
    assert find_reversed_cell_labels("Gates 3B and 4A remain open; Runway 5A is closed.") == []


def test_number_first_labels_are_reported_not_interpreted() -> None:
    content = (
        "Initial risk cell: 3B, High (row 3 Occasional, column B Hazardous). Residual 2B, Medium."
    )

    assert find_reversed_cell_labels(content) == ["2B", "3B"]
    assert find_band_mismatches(content) == []


def test_band_and_notation_issues_are_raised_on_sra_and_phl_outputs() -> None:
    content = "Initial risk cell: C2 – Medium. Residual risk cell: 2B – Medium."

    for flags in ({"is_sra": True, "is_phl": False}, {"is_sra": False, "is_phl": True}):
        issues = check_analysis_output("<rr_payload>{}</rr_payload>" + content, **flags)
        labels = [i.label for i in issues]
        assert labels == ["Risk Band Consistency", "Matrix Cell Notation"]
        assert "C2 stated Medium (matrix: High)" in issues[0].detail
        assert "2B" in issues[1].detail


def test_band_checks_do_not_run_on_general_answers() -> None:
    content = "Initial risk cell: C2 – Medium. Residual risk cell: 2B – Medium."

    assert check_analysis_output(content, is_sra=False, is_phl=False) == []


# --- Regulatory citation titles -----------------------------------------------


def test_a_title_from_another_section_is_reported() -> None:
    """The PVD failure: §139.329 carrying §139.323's title, and a paraphrase of neither."""
    content = (
        "• 14 CFR §139.329 (Traffic and wind direction indicators – safe operations).\n"
        "• 14 CFR §139.329 (Traffic control).\n"
        "• 14 CFR §139.329 (Traffic control).\n"
    )

    assert find_mistitled_citations(content) == [
        "§139.329 cited as 'Traffic and wind direction indicators – safe operations' "
        "(official title: Pedestrians and ground vehicles)",
        "§139.329 cited as 'Traffic control' (official title: Pedestrians and ground vehicles)",
    ]


def test_shortened_and_glossed_titles_are_accepted() -> None:
    content = (
        "• 14 CFR §139.311 (Marking and lighting).\n"
        "• 14 CFR §139.305 (Paved areas – FOD control).\n"
        "• 14 CFR §139.319 – Aircraft rescue and firefighting\n"
        "• 14 CFR 139.327: Self-inspection program\n"
        "• §139.325 (Airport emergency plan – security coordination)\n"
        "• 14 CFR §139.323 (Traffic and wind direction indicators).\n"
    )

    assert find_mistitled_citations(content) == []


def test_paragraph_references_and_bare_numbers_are_not_titles() -> None:
    content = (
        "Confidential reporting per §139.402(c)(2) and §139.402(b).\n"
        "See 14 CFR §139.309 and AC 150/5370-2G.\n"
        "§139.402(c) (Safety assurance) applies."
    )

    assert find_mistitled_citations(content) == []


def test_a_section_that_does_not_exist_is_reported() -> None:
    assert find_mistitled_citations("• 14 CFR §139.330 (Vehicle operations).") == [
        "§139.330 is not a section of Part 139"
    ]


def test_citation_titles_are_checked_on_every_analysis_output() -> None:
    content = "Regulatory Citations\n• 14 CFR §139.329 (Traffic control)."

    for flags in (
        {"is_sra": True, "is_phl": False},
        {"is_sra": False, "is_phl": True, "is_analysis": True},
        {"is_sra": False, "is_phl": False, "is_analysis": True},
    ):
        issues = check_analysis_output("<rr_payload>{}</rr_payload>" + content, **flags)
        assert [i.label for i in issues] == ["Regulatory Citation Titles"]
        assert "Pedestrians and ground vehicles" in issues[0].detail

    assert check_analysis_output(content, is_sra=False, is_phl=False) == []


# --- Source closure status ----------------------------------------------------

CSPP_WITH_DECOMMISSIONING = (
    "Work Area A lies south and west of Taxiways T, M, and E. "
    "In Phase 1 Work Area B, Taxiway E will be decommissioned and closed permanently, "
    "including disconnecting its lighting and signage circuit and updating the "
    "Airfield Lighting Control System. Taxiway T remains open throughout."
)


def test_a_decommissioned_surface_named_as_active_is_reported() -> None:
    """The PVD failure: Taxiway E listed with the active taxiways, no closure hazard."""
    output = (
        "Hazard 1 – Aircraft / vehicle conflict at work area interfaces (Taxiways T, M, E).\n"
        "Taxiway lights obscured or de-energized and NOTAM'd out of service."
    )

    assert find_unreflected_closures(output, CSPP_WITH_DECOMMISSIONING) == ["Taxiway E"]


def test_an_output_that_reflects_the_closure_is_not_reported() -> None:
    output = (
        "Hazard 1 – Interfaces with Taxiways T and M.\n"
        "Hazard 2 – Permanent decommissioning of Taxiway E in Phase 1 Work Area B: "
        "lighting circuit disconnection and ALCS update."
    )

    assert find_unreflected_closures(output, CSPP_WITH_DECOMMISSIONING) == []


def test_a_closed_surface_the_output_never_names_is_not_reported() -> None:
    output = "Hazard 1 – FOD from demolition near Taxiway T."

    assert find_unreflected_closures(output, CSPP_WITH_DECOMMISSIONING) == []


def test_a_surface_the_source_keeps_open_is_not_a_closure() -> None:
    source = "Taxiway T remains open. Taxiway E is closed permanently in Phase 1."

    assert find_unreflected_closures("Taxiways T and E interface.", source) == ["Taxiway E"]


def test_closure_check_needs_source_text() -> None:
    assert find_unreflected_closures("Taxiway E is active.", "") == []


def test_closure_issue_is_raised_on_analysis_outputs() -> None:
    output = "<rr_payload>{}</rr_payload>\nInterfaces: Taxiways T, M, E."

    issues = check_analysis_output(
        output, is_sra=False, is_phl=True, retrieved_text=CSPP_WITH_DECOMMISSIONING
    )

    assert [i.label for i in issues] == ["Source Closure Status Not Reflected"]
    assert "Taxiway E" in issues[0].detail


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
        + "- Avoid/Eliminate: not feasible.\n- Substitute: none.\n"
        + "- Engineer: barrier. Residual after this tier: D2 – Medium.\n"
        + "- Administrative: briefing. Residual after this tier: D3 – Medium.\n"
        + "- PPE: vests. Residual after this tier: D3 – Medium.\nDisposition: Accept.\n"
    )

    assert check_analysis_output(content, is_sra=True, is_phl=False) == []
