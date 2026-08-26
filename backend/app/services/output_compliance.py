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


# --- Aggregation --------------------------------------------------------------


def check_analysis_output(
    content: str,
    *,
    is_sra: bool,
    is_phl: bool,
    retrieved_text: str = "",
) -> list[ComplianceIssue]:
    """Run every applicable output requirement check and collect what failed."""
    issues: list[ComplianceIssue] = []

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
