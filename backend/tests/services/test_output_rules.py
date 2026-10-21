"""The scoring and accountability rules the SRA checker enforces.

These are the rules the QA analyst typed into the SRA prompt by hand on the
SUS Taxiway Alpha run: severity fixed per hazard, likelihood never rising
between tiers, a High residual carrying the further-mitigation line, a High
initial routed to the Accountable Executive, no Faith Group precedent credited
when none was retrieved, and no owners or dates RMP made up.
"""

from app.services.output_compliance import (
    check_analysis_output,
    find_high_initials_without_ae_review,
    find_high_residuals_without_further_mitigation,
    find_invented_due_dates,
    find_invented_owners,
    find_likelihood_increases,
    find_severity_drift,
    find_unsupported_fg_claims,
    hazard_scores,
    split_hazard_sections,
)

CLEAN_HAZARD = """
H1 – Haul Trucks Crossing Taxiway Alpha
Primary Worst Credible Outcome Collision between a haul truck and a taxiing aircraft.
Initial Risk
• Initial cell: C2 – High. Accountable Executive review required before work begins.
Controls (Hierarchy of Controls)
• Avoid/Eliminate: not feasible; the haul route must cross the taxiway.
• Substitute: ruled out; no alternative haul route exists.
• Engineer: flagger-controlled crossing with barricades. Residual after this tier: D2 – Medium.
• Administrative: escort and radio contact with ATCT. Residual after this tier: E2 – Medium.
• PPE: high-visibility vests. Residual after this tier: E2 – Medium.
Residual Risk
• Residual cell: E2 – Medium.
Disposition: Accept with conditions.
Owner: To be assigned by the airport. Due: To be set by the airport.
"""

SEVERITY_DRIFT_HAZARD = """
H2 – FOD From Haul Route
Initial cell: C2 – High. Accountable Executive review required.
• Avoid/Eliminate: not feasible.
• Substitute: ruled out.
• Engineer: covered loads. Residual after this tier: D3 – Medium.
• Administrative: sweeping schedule. Residual after this tier: E3 – Low.
• PPE: not applicable.
Disposition: Accept with conditions.
"""

LIKELIHOOD_RISE_HAZARD = """
H3 – Night Work Lighting
Initial cell: D2 – Medium.
• Avoid/Eliminate: not feasible.
• Substitute: ruled out.
• Engineer: portable lighting. Residual after this tier: E2 – Medium.
• Administrative: inspection before each shift. Residual after this tier: C2 – High.
• PPE: not applicable.
Disposition: Accept with conditions.
"""

HIGH_RESIDUAL_HAZARD = """
H4 – Contractor Escort Conflict
Initial cell: B2 – High. Accountable Executive review required.
• Avoid/Eliminate: not feasible.
• Substitute: ruled out.
• Engineer: not applicable.
• Administrative: escort procedure. Residual after this tier: C2 – High.
• PPE: not applicable.
Disposition: Accept with conditions.
"""


def _sections(text: str):  # noqa: ANN202 - test helper
    return split_hazard_sections(text + "\n" + CLEAN_HAZARD.replace("H1", "H9"))


def test_hazard_scores_reads_initial_and_tier_residuals() -> None:
    [section, _] = _sections(CLEAN_HAZARD.replace("H1", "H8"))

    scores = hazard_scores(section)

    assert scores.initial == "C2"
    assert scores.residuals == ["D2", "E2", "E2"]
    assert scores.final_residual == "E2"


def test_clean_hazard_passes_every_rule() -> None:
    sections = _sections(CLEAN_HAZARD.replace("H1", "H8"))

    assert find_severity_drift(sections) == []
    assert find_likelihood_increases(sections) == []
    assert find_high_residuals_without_further_mitigation(sections) == []
    assert find_high_initials_without_ae_review(sections) == []


def test_severity_that_changes_between_tiers_is_reported() -> None:
    assert find_severity_drift(_sections(SEVERITY_DRIFT_HAZARD)) == ["H2 (C2, D3, E3)"]


def test_likelihood_that_rises_after_a_control_is_reported() -> None:
    assert find_likelihood_increases(_sections(LIKELIHOOD_RISE_HAZARD)) == ["H3 (E2 to C2)"]


def test_high_final_residual_needs_the_further_mitigation_line() -> None:
    assert find_high_residuals_without_further_mitigation(_sections(HIGH_RESIDUAL_HAZARD)) == [
        "H4 (C2)"
    ]
    worded = HIGH_RESIDUAL_HAZARD.replace(
        "Disposition: Accept with conditions.",
        "Disposition: Further mitigation or AE acceptance required.",
    )
    assert find_high_residuals_without_further_mitigation(_sections(worded)) == []


def test_high_initial_needs_ae_review_in_its_own_section() -> None:
    silent = HIGH_RESIDUAL_HAZARD.replace(" Accountable Executive review required.", "")
    assert find_high_initials_without_ae_review(_sections(silent), silent) == ["H4 (B2)"]


def test_closing_ae_review_subsection_counts_when_it_names_the_hazard() -> None:
    silent = HIGH_RESIDUAL_HAZARD.replace(" Accountable Executive review required.", "")
    content = (
        silent
        + "\nF. Accountable Executive Review\nH4 is rated High and is escalated.\n"
        + "G. Audit Trail Entry\n"
    )
    assert find_high_initials_without_ae_review(_sections(silent), content) == []


def test_fg_precedent_claims_are_caught_only_when_positive() -> None:
    claims = find_unsupported_fg_claims(
        "Faith Group has multiple similar taxiway rehab CSPPs in the corpus. "
        "FG weighting: 70%. "
        "No FG SRM precedent identified for this airport. "
        "FG weighting: 0% (no FG document retrieved)."
    )

    assert claims == [
        "Faith Group has multiple similar taxiway rehab CSPPs in the corpus.",
        "FG weighting: 70%.",
    ]


def test_fg_claim_is_an_issue_only_without_an_fg_source() -> None:
    content = "Source Traceability: FG SRM precedent, similar airport, 70% weighted precedent."

    without = check_analysis_output(content, is_sra=True, is_phl=False, has_fg_source=False)
    with_source = check_analysis_output(content, is_sra=True, is_phl=False, has_fg_source=True)

    assert [i.label for i in without] == ["FG Precedent Claimed Without an FG Source"]
    assert with_source == []


def test_invented_owners_and_dates_are_reported_but_placeholders_are_not() -> None:
    content = (
        "| Action | Owner | Due |\n"
        "| Escort procedure | Chief Pilot Liaison / ATCT Coordinator | 12/31/2026 |\n"
        "- Owner: To be assigned by the airport\n"
        "- Due date: TBD\n"
        "- Responsible: Airport Operations Manager\n"
        "- Timeline: before Q2 2027\n"
    )

    assert sorted(find_invented_owners(content)) == [
        "Airport Operations Manager",
        "Chief Pilot Liaison / ATCT Coordinator",
    ]
    assert sorted(find_invented_due_dates(content)) == ["12/31/2026", "before Q2 2027"]


def test_full_check_reports_the_four_tier_rules_together() -> None:
    content = "\n".join([SEVERITY_DRIFT_HAZARD, LIKELIHOOD_RISE_HAZARD, HIGH_RESIDUAL_HAZARD])

    labels = [i.label for i in check_analysis_output(content, is_sra=True, is_phl=False)]

    assert "Severity Changed Between Tiers" in labels
    assert "Likelihood Increased After a Control" in labels
    assert "High Residual Without Further Mitigation Line" in labels
    assert "Owners and Due Dates Assigned by RMP" not in labels
