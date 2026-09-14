"""Post-generation compliance checks on RMP analysis outputs.

The Core Logic prompts state a number of hard output requirements — a structured
payload on every PHL, an explicit risk disposition on every hazard in an SRA, all
five hierarchy-of-controls levels ruled in or out — but nothing verified them, so
compliance silently degraded as outputs grew: a single-hazard SRA satisfied them
while a twelve-hazard SRA of the same construction project dropped them.

These checks run on the finished response. They never rewrite the model's
analysis; they report what is missing so the caller can surface it, the same way
`_detect_missing_mandatory_elements` already does for whole-output elements.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from app.models.risk import RISK_MATRIX, RiskLevel
from app.utils.part139 import PART_139_SECTIONS

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ComplianceIssue:
    """One unmet output requirement, with enough detail to act on."""

    label: str
    detail: str


# --- Structured payload (Sub-Prompt 2) ---------------------------------------

# The model wraps the Risk Register payload in this block. It is stripped from
# the rendered chat bubble, so absence is invisible to the user unless flagged.
_RR_PAYLOAD_RE = re.compile(
    r"<rr_payload>\s*(?:```[a-zA-Z]*\s*)?(.*?)(?:\s*```)?\s*</rr_payload>",
    re.IGNORECASE | re.DOTALL,
)


def extract_rr_payload(content: str) -> dict[str, object] | list[object] | None:
    """Return the parsed `<rr_payload>` JSON, or None when absent/unparseable.

    Unparseable is treated as absent on purpose: a payload that cannot be read
    is no more usable for Risk Register ingestion than a missing one, and both
    should surface the same way.
    """
    match = _RR_PAYLOAD_RE.search(content)
    if not match:
        return None
    raw = match.group(1).strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("rr_payload_unparseable", payload_length=len(raw))
        return None
    if isinstance(parsed, dict | list):
        return parsed
    return None


# --- Hazard sections ----------------------------------------------------------

# Outputs head each hazard as "H3 – Title", "Hazard 3 – Title", "Hazard H3 –
# Title", or with a project prefix welded on ("TWVH3 – Title", "PVD-H3 –
# Title") — all of these appear across real outputs — optionally behind
# markdown heading/bold markers. The prefix must be upper-case: under
# IGNORECASE a lower-case run would let an ordinary heading such as "Length 3"
# read as hazard 3.
_HAZARD_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[ \t]*"
    r"(?:hazard[ \t]*H?|(?-i:[A-Z]{1,6}[-_]?H)|H)[ \t]*\.?[ \t]*(\d{1,2})\b",
    re.IGNORECASE | re.MULTILINE,
)


# Some outputs number hazards plainly ("2. Aircraft/Vehicle Conflicts …") with no
# H prefix. Bare numbering is too common to trust on its own, so a numbered
# section only counts as a hazard when it carries risk-scoring language.
_BARE_NUMBERED_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[ \t]*(\d{1,2})[.)][ \t]+\S",
    re.MULTILINE,
)
# Cell labels are likelihood-letter then severity-number ("C2"). The reversed
# order is accepted here on purpose: this decides only whether a numbered section
# is about risk scoring, and an output still written the old way is scoring text
# either way. Flagging the wrong order is _has_matrix_cell_notation's job.
_SCORING_SIGNAL_RE = re.compile(
    r"\b[A-E][1-5]\b|\b[1-5][A-E]\b"
    r"|\blikelihood\b|\bseverity\b|\binitial risk\b|\bresidual risk\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HazardSection:
    label: str
    body: str


def _build_sections(
    content: str, matches: list[re.Match[str]], prefix: str = "H"
) -> list[HazardSection]:
    sections: list[HazardSection] = []
    seen: set[str] = set()
    for i, match in enumerate(matches):
        label = f"{prefix}{match.group(1)}"
        # A hazard restated later (e.g. in a summary table) is not a new section.
        if label in seen:
            continue
        seen.add(label)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append(HazardSection(label=label, body=content[match.start() : end]))
    return sections


def split_hazard_sections(content: str) -> list[HazardSection]:
    """Split an analysis output into its per-hazard sections.

    Returns an empty list when the output is not hazard-structured (a general
    answer, or a single-hazard narrative), in which case per-hazard checks are
    skipped rather than reported as failures.
    """
    matches = list(_HAZARD_HEADING_RE.finditer(content))
    if len(matches) >= 2:
        return _build_sections(content, matches)

    # Fall back to bare numbering, but only when most numbered sections actually
    # carry risk scoring — otherwise any ordinary numbered list would qualify.
    numbered = list(_BARE_NUMBERED_HEADING_RE.finditer(content))
    if len(numbered) < 2:
        return []
    candidate = _build_sections(content, numbered)
    scored = sum(1 for s in candidate if _SCORING_SIGNAL_RE.search(s.body))
    if scored * 2 < len(candidate):
        return []
    return candidate


# --- Risk disposition (Sub-Prompt 3) -----------------------------------------

# The spec requires one of three dispositions per hazard. Bare ALARP wording
# ("ALARP: Yes") does not satisfy it, and neither does "acceptable" loose in
# scoring prose ("residual risk is acceptable pending review"). The adjectival
# forms the model emits as a labeled decision — "ALARP Status: Acceptable with
# conditions", "Disposition: Not acceptable", "Unacceptable" — do carry the
# decision and are accepted. Without them every hazard in an SRA written that
# way reads as having no disposition at all.
_DISPOSITION_RE = re.compile(
    r"\baccept(?:able)? with conditions\b"
    r"|\baccept(?:ed)?\b(?![a-z])"
    r"|\b(?:alarp(?: status)?|disposition|status)\s*[:\-–]\s*(?:not )?acceptable\b"
    r"|\bunacceptable\b"
    r"|\breject(?:ed)?\b(?![a-z])"
    r"|\brequires? further mitigation\b",
    re.IGNORECASE,
)


def find_hazards_missing_disposition(sections: list[HazardSection]) -> list[str]:
    """Hazard labels with no Accept / Accept-with-conditions / Reject line."""
    return [s.label for s in sections if not _DISPOSITION_RE.search(s.body)]


# --- Hierarchy of controls (Sub-Prompt 3) ------------------------------------

# All five levels must be considered and explicitly ruled in or out. Avoid and
# Substitute are the ones routinely dropped when they are not an obvious fit.
_HIERARCHY_LEVELS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Avoid/Eliminate", re.compile(r"\b(?:avoid\w*|eliminat\w*)\b", re.IGNORECASE)),
    ("Substitute", re.compile(r"\bsubstitut\w*\b", re.IGNORECASE)),
    ("Engineer", re.compile(r"\bengineer\w*\b", re.IGNORECASE)),
    ("Administrative", re.compile(r"\badministrativ\w*\b", re.IGNORECASE)),
    ("PPE", re.compile(r"\bPPE\b|\bpersonal protective equipment\b", re.IGNORECASE)),
)


def find_incomplete_hierarchy(sections: list[HazardSection]) -> dict[str, list[str]]:
    """Map each hazard label to the hierarchy levels it never mentions."""
    incomplete: dict[str, list[str]] = {}
    for section in sections:
        missing = [name for name, pattern in _HIERARCHY_LEVELS if not pattern.search(section.body)]
        if missing:
            incomplete[section.label] = missing
    return incomplete


# --- Risk band consistency (Sub-Prompt 3) ------------------------------------

# Cell labels are likelihood-letter then severity-number ("C2"), matching the
# Risk Register matrix: A1 is Frequent/Catastrophic, E5 is Extremely
# Improbable/Minimal. The reversed order is not a valid label. The PVD outputs
# reviewed on 2026-09-02 wrote "3B" against a likelihood scale the matrix does
# not have (3 = "Occasional"), and the same cell carried High in one project and
# Medium in another; a reversed label is therefore reported, never interpreted.
MATRIX_CELL_RE = re.compile(r"\b[A-E][1-5]\b")
_REVERSED_CELL_RE = re.compile(r"\b[1-5][A-E]\b")

# Infrastructure designators share the cell-label shape — "Taxiway A1" and
# "Gate B2" both read as valid matrix cells — so an SRA that names one while
# rendering no scores at all would satisfy the notation check. A designator is
# always introduced by its facility noun, so a candidate is rejected when one
# leads into it (directly, or across a run like "Taxiways A1, B2").
_DESIGNATOR_LEAD_IN_RE = re.compile(
    r"(?:taxiway|twy|tw|runway|rwy|gate|stand|apron|ramp|connector|exit)s?\.?\s*"
    r"(?:(?:[A-E][1-5]|[1-5][A-E])\s*(?:,|/|&|and|or|-|–|through)\s*)*\Z",
    re.IGNORECASE,
)
# Widest lead-in we look back over: the facility noun plus a short designator run.
_DESIGNATOR_LOOKBACK_CHARS = 48

# The band the model states for a cell follows it closely: "C2 (High)",
# "C2 – High", "C2 (Remote / Hazardous) — High", "Initial Risk: C2, High (row C
# Remote, column 2 Hazardous)". The first band word within a short span on the
# same sentence is taken as the stated band; the span stops at a sentence end or
# at another cell label, and a band that opens a "High to Medium" pair is skipped,
# so a comparison ("C2 to D2, from High to Medium") is not read as a band for
# the second cell.
_BAND_AFTER_CELL_RE = re.compile(
    r"[^\n.;]{0,40}?\b(high|medium|low)\b(?!\s+to\s+(?:high|medium|low)\b)",
    re.IGNORECASE,
)

# Cell E1 (Extremely Improbable / Catastrophic) is the one cell where operator
# matrices legitimately differ; the Risk Register renders it split. Either
# band is accepted there.
_SPLIT_CELL_BANDS: dict[str, frozenset[RiskLevel]] = {
    "E1": frozenset({RiskLevel.HIGH, RiskLevel.MEDIUM}),
}


def is_matrix_cell_label(content: str, match: re.Match[str]) -> bool:
    """False when the candidate is an infrastructure designator, not a cell label."""
    window_start = max(0, match.start() - _DESIGNATOR_LOOKBACK_CHARS)
    return not _DESIGNATOR_LEAD_IN_RE.search(content[window_start : match.start()])


def matrix_bands(cell: str) -> frozenset[RiskLevel]:
    """The band(s) the FAA 5x5 matrix assigns to a letter-first cell label.

    Severity is displayed 1=Catastrophic … 5=Minimal but stored 1=Minimal …
    5=Catastrophic, so the label's digit is flipped before the lookup.
    """
    if cell in _SPLIT_CELL_BANDS:
        return _SPLIT_CELL_BANDS[cell]
    likelihood, displayed_severity = cell[0], int(cell[1])
    return frozenset({RISK_MATRIX[likelihood][6 - displayed_severity]})


def find_band_mismatches(content: str) -> list[str]:
    """Cells whose stated band disagrees with the matrix, e.g. "C2 stated Medium (matrix: High)".

    Each distinct cell/band pair is reported once, in order of first appearance.
    A cell with no band stated alongside it is not reported here; the
    alphanumeric label alone is compliant.
    """
    mismatches: list[str] = []
    seen: set[tuple[str, str]] = set()
    for match in MATRIX_CELL_RE.finditer(content):
        if not is_matrix_cell_label(content, match):
            continue
        band_match = _BAND_AFTER_CELL_RE.match(content, match.end())
        if band_match is None or MATRIX_CELL_RE.search(
            band_match.group(0)[: -len(band_match.group(1))]
        ):
            continue
        cell = match.group(0)
        stated = RiskLevel(band_match.group(1).lower())
        if stated in matrix_bands(cell) or (cell, stated) in seen:
            continue
        seen.add((cell, stated))
        expected = " or ".join(sorted(b.value.capitalize() for b in matrix_bands(cell)))
        mismatches.append(f"{cell} stated {stated.value.capitalize()} (matrix: {expected})")
    return mismatches


def find_reversed_cell_labels(content: str) -> list[str]:
    """Distinct number-first labels ("3B") that are not infrastructure designators."""
    found = {
        m.group(0) for m in _REVERSED_CELL_RE.finditer(content) if is_matrix_cell_label(content, m)
    }
    return sorted(found)


# --- Named infrastructure grounding ------------------------------------------

# Matches "Taxiway V", "Taxiways E, M, T and V", "TW A1", "Runway 13R-31L".
# The `(?![A-Za-z])` guard is load-bearing: under IGNORECASE a bare letter class
# also matches the first letter of a connector word, so "E, M, T, and V" would
# otherwise stop at "T" (consuming the "a" of "and") and silently lose "V".
_DESIGNATOR = r"[A-Za-z][0-9]{0,2}(?![A-Za-z])"
# Repeats so an Oxford-comma list ("E, M, T, and V") reads as one run rather
# than terminating at the ", and " pair.
_CONNECTOR = r"(?:\s*(?:,|/|&|and|or|-|–|through))+\s*"
_TAXIWAY_RUN_RE = re.compile(
    rf"\b(?:taxiway|twy|tw)s?\.?\s+(({_DESIGNATOR})(?:{_CONNECTOR}{_DESIGNATOR})*)",
    re.IGNORECASE,
)
_RUNWAY_RUN_RE = re.compile(
    r"\b(?:runway|rwy)s?\.?\s+((?:\d{1,2}[LRC]?)(?:\s*(?:,|/|&|and|or|-|–)\s*\d{1,2}[LRC]?)*)\b",
    re.IGNORECASE,
)
_DESIGNATOR_SPLIT_RE = re.compile(r"\s*(?:,|/|&|and|or|-|–|through)\s*", re.IGNORECASE)

# Words that follow "taxiway" in ordinary prose and are not designators.
_NOT_DESIGNATORS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "closure",
        "closures",
        "edge",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
        "safety",
        "shoulder",
        "system",
        "the",
        "to",
        "with",
    }
)


def _normalize_designator(token: str) -> str:
    """Zero-pad runway numbers so "Runway 5-23" and "Runway 05-23" compare equal.

    Both spellings are in everyday use (FAA drops the leading zero, ICAO keeps
    it), and treating them as different names reports a real runway as invented.
    """
    if token[0].isdigit():
        digits = token.rstrip("LRC")
        suffix = token[len(digits) :]
        return f"{int(digits):02d}{suffix}"
    return token


def _designators(text: str, pattern: re.Pattern[str]) -> set[str]:
    found: set[str] = set()
    for match in pattern.finditer(text):
        for token in _DESIGNATOR_SPLIT_RE.split(match.group(1)):
            token = token.strip().upper()
            if not token or token.lower() in _NOT_DESIGNATORS:
                continue
            found.add(_normalize_designator(token))
    return found


def find_unsupported_infrastructure(content: str, retrieved_text: str) -> list[str]:
    """Named taxiways/runways in the output that the retrieved source never names.

    Guards against the failure where an otherwise well-grounded analysis invents
    one infrastructure detail (a taxiway that does not exist at the airport) and
    then carries it through downstream hazard narratives.

    Returns an empty list when there is no retrieved text to check against —
    absence of evidence is not evidence of fabrication, and a grounding miss is
    reported separately.
    """
    if not retrieved_text.strip():
        return []

    unsupported: list[str] = []
    for kind, pattern in (("Taxiway", _TAXIWAY_RUN_RE), ("Runway", _RUNWAY_RUN_RE)):
        in_output = _designators(content, pattern)
        in_source = _designators(retrieved_text, pattern)
        if not in_source:
            # The source names none of this kind at all; the output may be
            # drawing on the user's prompt rather than the corpus. Stay quiet.
            continue
        unsupported.extend(f"{kind} {designator}" for designator in sorted(in_output - in_source))
    return unsupported


# --- Source closure status -----------------------------------------------------

# Language a CSPP uses when a surface stops being an operating surface. The PVD
# South Cargo Ramp CSPP decommissioned Taxiway E in Phase 1 Work Area B; the
# analysis named Taxiway E alongside the active taxiways as if nothing changed.
_CLOSURE_TERM_RE = re.compile(
    r"\bdecommission\w*\b"
    r"|\bpermanent(?:ly)?\s+clos\w+\b"
    r"|\bclos\w+\s+permanently\b"
    r"|\bpermanent\s+closure\b"
    r"|\b(?:removed|taken)\s+(?:out\s+of|from)\s+service\b"
    r"|\bdemolish\w*\b"
    r"|\babandon\w*\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _closure_designators(text: str) -> dict[str, str]:
    """Designators named in the same sentence as closure language, with their kind."""
    closed: dict[str, str] = {}
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if not _CLOSURE_TERM_RE.search(sentence):
            continue
        for kind, pattern in (("Taxiway", _TAXIWAY_RUN_RE), ("Runway", _RUNWAY_RUN_RE)):
            for designator in _designators(sentence, pattern):
                closed.setdefault(f"{kind} {designator}", kind)
    return closed


def find_unreflected_closures(content: str, retrieved_text: str) -> list[str]:
    """Surfaces the source closes or decommissions that the output names without that status.

    A surface the source never closes, or one the output never names, is not
    reported: the first is not a closure and the second is a coverage question
    for the analyst. What is reported is the specific failure of naming a
    decommissioned surface as though it were still an ordinary active one.
    """
    if not retrieved_text.strip():
        return []
    closed_in_source = _closure_designators(retrieved_text)
    if not closed_in_source:
        return []
    named_in_output = {
        f"{kind} {designator}"
        for kind, pattern in (("Taxiway", _TAXIWAY_RUN_RE), ("Runway", _RUNWAY_RUN_RE))
        for designator in _designators(content, pattern)
    }
    reflected_in_output = set(_closure_designators(content))
    return sorted(
        name
        for name in closed_in_source
        if name in named_in_output and name not in reflected_in_output
    )


# --- Regulatory citation titles -----------------------------------------------

# A Part 139 section cited with a title: "14 CFR §139.329 (Traffic control)",
# "§139.329 – Pedestrians and ground vehicles", "14 CFR 139.311: Marking and
# lighting". Paragraph references after the number ("(b)(2)") are stepped over.
# Two PVD projects cited §139.329 as "Traffic and wind direction indicators" —
# the title of §139.323 — across several sessions: the number was right for the
# ground-vehicle hazards it backed, the title was drawn from memory.
_PART139_CITATION_RE = re.compile(
    r"(?:14\s*CFR\s*)?(?:Part\s*139\s*)?§?\s*139\.(?P<section>\d{1,3})(?:\([a-z0-9]{1,3}\))*"
    r"\s*(?:\((?P<paren>[^()\n]{3,120})\)|[-–—:]\s*(?P<dash>[^\n;.]{3,120}))",
    re.IGNORECASE,
)
# A stated title often carries a gloss after a dash or colon ("Paved areas – FOD
# control"); only the part before it is the title.
_TITLE_GLOSS_SPLIT_RE = re.compile(r"\s+[-–—:]\s+|:\s+")
_TITLE_TOKEN_RE = re.compile(r"[a-z]+")
# Words too common across Part 139 titles to show that two titles are the same.
_TITLE_STOPWORDS = frozenset({"and", "the", "for", "with", "from", "into", "other", "airport"})


def _title_tokens(title: str) -> set[str]:
    stated = _TITLE_GLOSS_SPLIT_RE.split(title.strip(), maxsplit=1)[0]
    return {
        token
        for token in _TITLE_TOKEN_RE.findall(stated.lower())
        if len(token) >= 3 and token not in _TITLE_STOPWORDS
    }


def find_mistitled_citations(content: str) -> list[str]:
    """Part 139 citations whose stated title belongs to no such section.

    A title is accepted when it shares at least one significant word with the
    official title, so a shortened or glossed title ("Marking and lighting",
    "Paved areas – FOD control") passes and only a title taken from a different
    section, or a section that does not exist, is reported.
    """
    findings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for match in _PART139_CITATION_RE.finditer(content):
        section = f"139.{match.group('section')}"
        stated = (match.group("paren") or match.group("dash") or "").strip()
        stated_tokens = _title_tokens(stated)
        if not stated_tokens:
            continue
        official = PART_139_SECTIONS.get(section)
        if official is None:
            finding = f"§{section} is not a section of Part 139"
        elif stated_tokens & _title_tokens(official):
            continue
        else:
            finding = f"§{section} cited as '{stated}' (official title: {official})"
        key = (section, stated.lower())
        if key in seen:
            continue
        seen.add(key)
        findings.append(finding)
    return findings


# --- Aggregation --------------------------------------------------------------


def check_analysis_output(
    content: str,
    *,
    is_sra: bool,
    is_phl: bool,
    is_analysis: bool = False,
    retrieved_text: str = "",
) -> list[ComplianceIssue]:
    """Run every applicable output requirement check and collect what failed.

    `is_analysis` covers every formal RMP analysis (System Analysis included),
    for checks that apply to any output that cites regulation.
    """
    issues: list[ComplianceIssue] = []

    if is_sra or is_phl or is_analysis:
        mistitled = find_mistitled_citations(content)
        if mistitled:
            issues.append(
                ComplianceIssue(
                    label="Regulatory Citation Titles",
                    detail=(
                        "; ".join(mistitled)
                        + ". Correct the title, not the section number, unless the "
                        "section itself is wrong for the finding it supports."
                    ),
                )
            )

    if is_phl and extract_rr_payload(content) is None:
        issues.append(
            ComplianceIssue(
                label="Structured Risk Register Payload",
                detail=(
                    "No usable <rr_payload> JSON block was produced, so this hazard "
                    "list cannot be ingested into the Risk Register without re-entry."
                ),
            )
        )

    if is_sra:
        sections = split_hazard_sections(content)
        if sections:
            missing_disposition = find_hazards_missing_disposition(sections)
            if missing_disposition:
                issues.append(
                    ComplianceIssue(
                        label="Per-Hazard Risk Disposition",
                        detail=(
                            "No explicit 'Accept', 'Accept with conditions', or "
                            "'Reject / requires further mitigation' decision for: "
                            + ", ".join(missing_disposition)
                            + ". ALARP wording does not satisfy this requirement."
                        ),
                    )
                )

            incomplete = find_incomplete_hierarchy(sections)
            if incomplete:
                detail = "; ".join(
                    f"{label} (missing {', '.join(levels)})"
                    for label, levels in sorted(incomplete.items())
                )
                issues.append(
                    ComplianceIssue(
                        label="Hierarchy of Controls Coverage",
                        detail=(
                            "All five levels must be ruled in or out with a stated "
                            f"reason. Levels never addressed — {detail}."
                        ),
                    )
                )

    if is_sra or is_phl:
        mismatches = find_band_mismatches(content)
        if mismatches:
            issues.append(
                ComplianceIssue(
                    label="Risk Band Consistency",
                    detail=(
                        "The stated band disagrees with the FAA 5x5 matrix for: "
                        + "; ".join(mismatches)
                        + ". The matrix is the only authority for the band — correct "
                        "the band or the score, not the matrix."
                    ),
                )
            )

        reversed_labels = find_reversed_cell_labels(content)
        if reversed_labels:
            issues.append(
                ComplianceIssue(
                    label="Matrix Cell Notation",
                    detail=(
                        "Cell labels are written number-first ("
                        + ", ".join(reversed_labels)
                        + "). Likelihood is the letter A-E and severity the number 1-5 "
                        "(e.g. C2 = Remote / Hazardous), so these scores cannot be "
                        "checked against the matrix and must be re-rendered."
                    ),
                )
            )

        unreflected = find_unreflected_closures(content, retrieved_text)
        if unreflected:
            issues.append(
                ComplianceIssue(
                    label="Source Closure Status Not Reflected",
                    detail=(
                        "The source document closes or decommissions "
                        + ", ".join(unreflected)
                        + ", but this output names the surface without that status. "
                        "A closure or decommissioning changes the hazard picture "
                        "(lighting and signage circuits, ALCS updates, marking "
                        "removal, pilot and driver familiarity) and must be "
                        "assessed as such."
                    ),
                )
            )

    unsupported = find_unsupported_infrastructure(content, retrieved_text)
    if unsupported:
        issues.append(
            ComplianceIssue(
                label="Unverified Infrastructure References",
                detail=(
                    "These named locations do not appear in the retrieved source "
                    "material and must be confirmed against the project documents "
                    "before use: " + ", ".join(unsupported) + "."
                ),
            )
        )

    return issues


def build_compliance_notice(issues: list[ComplianceIssue]) -> str:
    """Render the in-body notice appended when output requirements were not met."""
    body = "\n".join(f"- **{issue.label}** — {issue.detail}" for issue in issues)
    return (
        "\n\n---\n\n"
        "### Output Compliance Notice\n\n"
        "RMP checked this output against the Core Logic output requirements and "
        "found the following gaps. Treat it as draft pending review:\n\n"
        f"{body}\n\n"
        "Recommended next step: regenerate the output, or have the SMS Manager "
        "supply the missing elements before this is used for the Risk Register "
        "or an Implementation Plan."
    )
