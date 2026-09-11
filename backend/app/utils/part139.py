"""Official section titles of 14 CFR Part 139.

The single source for Part 139 section titles in RMP. The prompts render this
table so the model cites from it rather than from memory, and the output
compliance check verifies cited titles against it. Titles are verbatim from the
eCFR (structure as of 2026-09-01); when Part 139 is amended, update this table
and both consumers follow.
"""

from collections.abc import Mapping

PART_139_SUBPARTS: tuple[tuple[str, Mapping[str, str]], ...] = (
    (
        "Subpart A — General",
        {
            "139.1": "Applicability",
            "139.3": "Delegation of authority",
            "139.5": "Definitions",
            "139.7": "Methods and procedures for compliance",
        },
    ),
    (
        "Subpart B — Certification",
        {
            "139.101": "General requirements",
            "139.103": "Application for certificate",
            "139.105": "Inspection authority",
            "139.107": "Issuance of certificate",
            "139.109": "Duration of certificate",
            "139.111": "Exemptions",
            "139.113": "Deviations",
        },
    ),
    (
        "Subpart C — Airport Certification Manual",
        {
            "139.201": "General requirements",
            "139.203": "Contents of Airport Certification Manual",
            "139.205": "Amendment of Airport Certification Manual",
        },
    ),
    (
        "Subpart D — Operations",
        {
            "139.301": "Records",
            "139.303": "Personnel",
            "139.305": "Paved areas",
            "139.307": "Unpaved areas",
            "139.309": "Safety areas",
            "139.311": "Marking, signs, and lighting",
            "139.313": "Snow and ice control",
            "139.315": "Aircraft rescue and firefighting: Index determination",
            "139.317": "Aircraft rescue and firefighting: Equipment and agents",
            "139.319": "Aircraft rescue and firefighting: Operational requirements",
            "139.321": "Handling and storing of hazardous substances and materials",
            "139.323": "Traffic and wind direction indicators",
            "139.325": "Airport emergency plan",
            "139.327": "Self-inspection program",
            "139.329": "Pedestrians and ground vehicles",
            "139.331": "Obstructions",
            "139.333": "Protection of NAVAIDS",
            "139.335": "Public protection",
            "139.337": "Wildlife hazard management",
            "139.339": "Airport condition reporting",
            "139.341": "Identifying, marking, and lighting construction and other unserviceable areas",
            "139.343": "Noncomplying conditions",
        },
    ),
    (
        "Subpart E — Airport Safety Management System",
        {
            "139.401": "General requirements",
            "139.402": "Components of Airport Safety Management System",
            "139.403": "Airport Safety Management System implementation",
        },
    ),
)

PART_139_SECTIONS: Mapping[str, str] = {
    section: title for _, sections in PART_139_SUBPARTS for section, title in sections.items()
}


def render_part139_reference() -> str:
    """The citation reference block embedded in every RMP system prompt."""
    lines = [
        "PART 139 CITATION REFERENCE",
        "Cite 14 CFR Part 139 sections by number with their official titles exactly "
        "as listed below. Never paraphrase a title, never attach the title of a "
        "different section, and never invent a section. If no section here covers a "
        "topic, cite the applicable Advisory Circular instead. Vehicle and pedestrian "
        "control on the movement area is §139.329; wind cones and segmented circles "
        "are §139.323.",
    ]
    for heading, sections in PART_139_SUBPARTS:
        lines.append(heading)
        lines.extend(f"§{section} {title}" for section, title in sections.items())
    return "\n".join(lines) + "\n"
