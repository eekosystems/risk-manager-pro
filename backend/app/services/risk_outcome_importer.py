"""Background scanner for per-airport `/risk-outcome/` PDFs.

Design for scale
----------------
The portfolio spans ~18 client airports (ABQ, BNA, CLT, COS, DEN, GEG, GSN,
HOU, IAH, IND, LAS, OAK, PHX, PIT, PVD, RDU, SAT, SEA) and each has its own
`/risk-outcome/` folder of hazard PDFs. A cold LLM-extraction sweep across
every PDF takes minutes and costs real money, so two behaviors make that
usable:

1. The scan runs in the background as a fire-and-forget task. The endpoint
   returns whatever is in the cache right now plus a `status` + `progress`
   field; the frontend polls until the scan finishes.
2. Per-file caching keyed by `drive_item_id` + `size` + `content_type` means
   unchanged PDFs are never re-extracted. Only new or modified files cost an
   LLM call on subsequent scans.

The top-level cache (`_summary`) aggregates every known hazard and is safe to
read concurrently while a scan is in flight.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from app.core.config import settings
from app.services.document_processor import DocumentProcessor
from app.services.sharepoint_crawler import is_risk_outcome_folder, normalize_folder_name

if TYPE_CHECKING:
    from app.services.openai_client import AzureOpenAIClient
    from app.services.sharepoint_crawler import SharePointCrawler, SharePointFile

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Public data shape
# ---------------------------------------------------------------------------


@dataclass
class SharePointRisk:
    airport_identifier: str
    hazard: str
    severity: int  # 1..5
    likelihood: str  # "A".."E"
    risk_level: str  # "low" | "medium" | "high" | "extreme"
    source_file: str
    source_url: str | None
    # Document-level metadata stamped onto every row from the same source file.
    report_year: int | None = None
    matrix_size: str | None = None  # "4x4" | "5x5" | "6x6" | "unknown"
    # Result of the import-rule classifier. Stamped in BOTH shadow and enforce
    # modes so it is always visible in the UI / logs. In shadow mode every row
    # is still kept; in enforce mode the importer routes rows by this label.
    import_classification: str = "clean"


@dataclass
class SharePointParseNote:
    airport_identifier: str
    source_file: str
    message: str


@dataclass
class SharePointRiskSummary:
    airports: list[str]
    risks: list[SharePointRisk]
    notes: list[SharePointParseNote]
    generated_at: float
    status: str  # "idle" | "scanning" | "ready"
    scanned: int  # files processed so far
    total: int  # files expected
    last_scan_completed_at: float | None
    # Rows that pass extraction but fail import rules (4x4 post-2018, unknown
    # year, etc.). Empty list in shadow mode — everything still flows through
    # `risks`. Populated only when settings.risk_import_enforce is True.
    risks_flagged_for_review: list[SharePointRisk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalization helpers (severity/likelihood value aliases)
# ---------------------------------------------------------------------------


_SEVERITY_ALIASES: dict[str, int] = {
    "1": 1, "e": 1, "minimal": 1, "negligible": 1,
    "2": 2, "d": 2, "minor": 2,
    "3": 3, "c": 3, "major": 3, "moderate": 3,
    "4": 4, "b": 4, "hazardous": 4, "critical": 4,
    "5": 5, "a": 5, "catastrophic": 5, "severe": 5,
}  # fmt: skip

_LIKELIHOOD_ALIASES: dict[str, str] = {
    "a": "A", "5": "A", "frequent": "A",
    "b": "B", "4": "B", "probable": "B", "occasional": "B",
    "c": "C", "3": "C", "remote": "C",
    "d": "D", "2": "D", "extremely remote": "D", "improbable": "D",
    "e": "E", "1": "E", "extremely improbable": "E",
}  # fmt: skip

_RISK_LEVEL_ALIASES: dict[str, str] = {
    "low": "low", "green": "low",
    "medium": "medium", "med": "medium", "moderate": "medium", "yellow": "medium",
    "high": "high", "orange": "high",
    "extreme": "extreme", "red": "extreme", "critical": "extreme",
}  # fmt: skip

# FAA 8040.4B 5x5 — mirrors app.models.risk.RISK_MATRIX (duplicated to
# avoid a circular import).
_RISK_MATRIX: dict[str, dict[int, str]] = {
    "A": {1: "medium", 2: "high", 3: "high", 4: "high", 5: "high"},
    "B": {1: "low", 2: "medium", 3: "high", 4: "high", 5: "high"},
    "C": {1: "low", 2: "low", 3: "medium", 4: "high", 5: "high"},
    "D": {1: "low", 2: "low", 3: "medium", 4: "medium", 5: "high"},
    "E": {1: "low", 2: "low", 3: "low", 4: "low", 5: "medium"},
}


def _compute_risk_level(severity: int, likelihood: str) -> str:
    return _RISK_MATRIX.get(likelihood, {}).get(severity, "low")


def _normalize_severity(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        iv = int(value)
        return iv if 1 <= iv <= 5 else None
    s = str(value).strip().lower()
    if not s:
        return None
    if s in _SEVERITY_ALIASES:
        return _SEVERITY_ALIASES[s]
    for alias, sev in _SEVERITY_ALIASES.items():
        if alias in s:
            return sev
    return None


def _normalize_likelihood(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if s in _LIKELIHOOD_ALIASES:
        return _LIKELIHOOD_ALIASES[s]
    for alias, code in _LIKELIHOOD_ALIASES.items():
        if alias in s:
            return code
    return None


def _normalize_risk_level(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    for alias, level in _RISK_LEVEL_ALIASES.items():
        if alias in s:
            return level
    return None


def _airport_from_segments(segments: list[str]) -> str | None:
    """Return the airport folder name for a file path under the configured root.

    The real SharePoint layout nests projects and sometimes sub-projects
    between the airport folder and the Risk Outcome folder, e.g.

        RMP Master Directory / Airport - Safety Risk Management Documents /
            ABQ / ABQ - 362-001 - SRMP / Risk Outcome / *.pdf

        CLT / CLT - 405-005 - Taxiway Nomenclature Change / Reports /
            Risk Outcome / *.pdf

    So we identify the airport as the segment directly AFTER the configured
    airport-root path (`settings.sharepoint_airport_root_folder`), and only
    if a Risk Outcome folder exists somewhere deeper in the same path.
    """
    # The file must live under a Risk Outcome folder somewhere in its chain.
    if not any(is_risk_outcome_folder(s) for s in segments):
        return None

    root_parts = [
        normalize_folder_name(s)
        for s in (settings.sharepoint_airport_root_folder or "").strip("/").split("/")
        if s
    ]
    if not root_parts:
        # No configured root — fall back to the top-level folder.
        return segments[0] if segments else None

    normalized = [normalize_folder_name(s) for s in segments]
    # Find the configured root prefix as a contiguous run of segments.
    for i in range(len(normalized) - len(root_parts) + 1):
        if normalized[i : i + len(root_parts)] == root_parts:
            airport_idx = i + len(root_parts)
            if airport_idx < len(segments):
                return segments[airport_idx]
            return None
    return None


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You extract hazards verbatim from aviation safety risk management "
    "documents. You do not paraphrase, summarize, rewrite, shorten, or "
    "interpret. You only return a hazard if its severity AND likelihood "
    "are both explicitly stated in the source document alongside the "
    "hazard. If anything is ambiguous, implied, or must be inferred, you "
    "skip that hazard. Return ONLY a JSON object matching the requested "
    "shape. No commentary, no code fences."
)

_USER_TEMPLATE = """\
Extract hazards from the following risk register / SRMD / SRMP document.

STRICT RULES — no exceptions:
1. Return the hazard text EXACTLY as it appears in the document. Do not
   paraphrase, shorten, reword, summarize, rewrite, or clean up wording.
   Copy the hazard description verbatim, character for character.
2. Only include a hazard if BOTH its severity AND its likelihood are
   EXPLICITLY stated in the document alongside (or in the same table row
   as) the hazard. If either field is missing, implied, inferred from
   context, or requires any judgment on your part, SKIP that hazard
   entirely — do not include it in the output.
3. Do NOT reverse-engineer severity or likelihood from a stated risk
   level. If the source provides only a risk level (Low/Medium/High/
   Extreme) and not both an explicit severity and an explicit likelihood,
   SKIP that hazard.
4. Report severity and likelihood by their DESCRIPTIVE NAME, not the
   number/letter the document happens to use. Different documents number
   the scales in opposite directions; the descriptive name is unambiguous.
   - severity must be one of: Catastrophic, Hazardous, Major, Minor, Minimal
     (synonyms: Negligible = Minimal; Critical = Hazardous; Severe = Catastrophic;
     Moderate = Major)
   - likelihood must be one of: Frequent, Probable, Remote, Extremely Remote,
     Extremely Improbable
     (synonyms: Occasional = Probable; Improbable = Extremely Remote)
   If the document only shows a number/letter without a descriptive label,
   use the document's own legend / scoring table to translate. If the
   legend is missing or ambiguous, SKIP the hazard.
5. Do NOT invent, combine, or synthesize hazards. Every returned row must
   correspond to a single hazard entry present in the source text.

Return ONLY this JSON shape (no prose):

{{
  "risks": [
    {{
      "hazard": "<verbatim hazard text as it appears in the document>",
      "severity": "<Catastrophic | Hazardous | Major | Minor | Minimal>",
      "likelihood": "<Frequent | Probable | Remote | Extremely Remote | Extremely Improbable>",
      "risk_level": "<low | medium | high | extreme — include ONLY if explicitly stated in the source, otherwise omit>"
    }}
  ]
}}

If no hazards in the document meet all of the rules above, return
{{"risks": []}}.

Document text (may be a chunk of a longer document):
---
{document_text}
---

Return ONLY the JSON object.
"""


# Per-chunk cap. Azure OpenAI gpt-4o has a 128k-token window (~450k chars);
# 90k chars per chunk leaves plenty of room for the prompt + JSON response.
_MAX_CHARS_PER_CHUNK = 90_000
_MAX_PARALLEL_EXTRACTIONS = 4


def _parse_json_payload(raw: str) -> dict[str, Any] | None:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def _chunk_text(text: str, chunk_chars: int = _MAX_CHARS_PER_CHUNK) -> list[str]:
    """Split long text into chunks at paragraph boundaries where possible.

    Most SRMDs are multi-section; splitting on double-newlines keeps a
    logical section intact within a chunk, which helps the model reason
    about hazards in context rather than mid-sentence.
    """
    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > chunk_chars:
        # Find a paragraph break within the last ~10% of the chunk window.
        break_hint = remaining.rfind("\n\n", chunk_chars - chunk_chars // 10, chunk_chars)
        split_at = break_hint if break_hint > 0 else chunk_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining.strip():
        chunks.append(remaining)
    return chunks


async def _extract_risks_from_chunk(
    *,
    chunk: str,
    airport: str,
    source_file: str,
    chunk_idx: int,
    chunk_total: int,
    openai_client: AzureOpenAIClient,
) -> tuple[list[dict[str, Any]], str | None]:
    """Ask the LLM for hazards in one chunk. Returns (rows, error_message)."""
    if not chunk.strip():
        return [], None
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(document_text=chunk)},
    ]
    try:
        raw = await openai_client.chat_completion(
            messages,
            temperature=0.0,
            max_tokens=8000,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        return [], (f"LLM extraction failed on chunk {chunk_idx + 1}/{chunk_total}: {exc}")
    payload = _parse_json_payload(raw)
    if payload is None or not isinstance(payload.get("risks"), list):
        return [], (
            f"LLM did not return a {{risks:[...]}} object on chunk {chunk_idx + 1}/{chunk_total}"
        )
    return [r for r in payload["risks"] if isinstance(r, dict)], None


async def _extract_risks_via_llm(
    *,
    text: str,
    airport: str,
    source_file: str,
    source_url: str | None,
    openai_client: AzureOpenAIClient,
) -> tuple[list[SharePointRisk], list[SharePointParseNote]]:
    if not text.strip():
        return [], [
            SharePointParseNote(
                airport_identifier=airport,
                source_file=source_file,
                message="empty text extraction",
            )
        ]

    chunks = _chunk_text(text)
    chunk_total = len(chunks)
    raw_rows: list[dict[str, Any]] = []
    notes: list[SharePointParseNote] = []

    # Run chunks sequentially per file (outer semaphore in _run_scan bounds
    # concurrency across files) to keep token usage predictable.
    for idx, chunk in enumerate(chunks):
        rows, err = await _extract_risks_from_chunk(
            chunk=chunk,
            airport=airport,
            source_file=source_file,
            chunk_idx=idx,
            chunk_total=chunk_total,
            openai_client=openai_client,
        )
        raw_rows.extend(rows)
        if err:
            notes.append(
                SharePointParseNote(
                    airport_identifier=airport,
                    source_file=source_file,
                    message=err,
                )
            )

    # Deduplicate on (hazard-normalized, severity, likelihood) so chunks with
    # overlapping context don't double-count hazards that span a chunk boundary.
    seen: set[tuple[str, int, str]] = set()
    risks: list[SharePointRisk] = []
    for idx, row in enumerate(raw_rows):
        severity = _normalize_severity(row.get("severity"))
        likelihood = _normalize_likelihood(row.get("likelihood"))
        if severity is None or likelihood is None:
            notes.append(
                SharePointParseNote(
                    airport_identifier=airport,
                    source_file=source_file,
                    message=f"row {idx} missing normalizable severity/likelihood",
                )
            )
            continue
        hazard_text = str(row.get("hazard") or "").strip()
        if not hazard_text:
            notes.append(
                SharePointParseNote(
                    airport_identifier=airport,
                    source_file=source_file,
                    message=f"row {idx} missing hazard text",
                )
            )
            continue
        dedup_key = (hazard_text.lower()[:120], severity, likelihood)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        risk_level = _normalize_risk_level(row.get("risk_level")) or _compute_risk_level(
            severity, likelihood
        )
        risks.append(
            SharePointRisk(
                airport_identifier=airport,
                hazard=hazard_text,
                severity=severity,
                likelihood=likelihood,
                risk_level=risk_level,
                source_file=source_file,
                source_url=source_url,
            )
        )

    if not risks and not notes:
        notes.append(
            SharePointParseNote(
                airport_identifier=airport,
                source_file=source_file,
                message="LLM returned zero hazards",
            )
        )
    logger.info(
        "risk_outcome_file_extracted",
        airport=airport,
        source_file=source_file,
        chunks=chunk_total,
        text_chars=len(text),
        risks_extracted=len(risks),
    )
    return risks, notes


# ---------------------------------------------------------------------------
# Document metadata extraction (report year + matrix size)
# ---------------------------------------------------------------------------


_METADATA_SYSTEM_PROMPT = (
    "You read aviation safety risk-management documents and report two facts: "
    "the report's publication or revision year, and the size of the risk "
    "scoring matrix the document uses (4x4, 5x5, or 6x6). Return ONLY a JSON "
    "object — no commentary, no code fences."
)

_METADATA_USER_TEMPLATE = """\
Identify the following from this risk register / SRMD / SRMP document:

1. report_year — the most recent revision, issue, effective, or publication
   year shown in the document header, footer, signature block, or revision
   history. Must be a 4-digit year between 1990 and 2099. If multiple years
   appear, prefer the most recent one tied to "Revision", "Issued", "Effective",
   "Date Approved", or "Updated". If no clear year is present, return null.

2. matrix_size — the dimension of the severity x likelihood matrix the
   document uses for risk scoring. Look at the matrix legend, scoring tables,
   or the range of severity / likelihood values used. Return one of:
   "4x4", "5x5", "6x6", or "unknown".

Return ONLY this JSON shape:

{{"report_year": <integer or null>, "matrix_size": "4x4" | "5x5" | "6x6" | "unknown"}}

Document text (may be a chunk of a longer document):
---
{document_text}
---

Return ONLY the JSON object.
"""


_YEAR_REGEX = re.compile(r"\b(19[9]\d|20\d{2})\b")
_REVISION_HINT_REGEX = re.compile(
    r"(?:revision|revised|issue(?:d)?|effective|approved|updated|date)"
    r"[\s:.\-]*\D{0,40}\b(19[9]\d|20\d{2})\b",
    re.IGNORECASE,
)


def _regex_year_from_text(text: str) -> int | None:
    """Cheap deterministic fallback when the LLM metadata call yields no year.

    Strategy: prefer a 4-digit year that appears within ~40 chars of a hint
    word (Revision / Issued / Effective / Approved / Updated / Date). If no
    hinted match is found, return the most recent plausible year anywhere in
    the first 8000 chars (likely the title page / header).
    """
    head = text[:8000]
    hinted = [int(m.group(1)) for m in _REVISION_HINT_REGEX.finditer(head)]
    if hinted:
        return max(hinted)
    plain = [int(m.group(1)) for m in _YEAR_REGEX.finditer(head)]
    if not plain:
        return None
    # Cap at a reasonable upper bound to avoid future-dated junk.
    return max(y for y in plain if y <= 2099)


def _normalize_matrix_size(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    s = value.strip().lower().replace(" ", "")
    if s in {"4x4", "5x5", "6x6"}:
        return s
    return "unknown"


async def _extract_doc_metadata(
    *,
    text: str,
    source_file: str,
    openai_client: AzureOpenAIClient,
) -> tuple[int | None, str]:
    """Return (report_year, matrix_size) for one source file.

    Falls back to a regex year scan if the LLM call fails or returns null.
    matrix_size defaults to "unknown" if neither the LLM nor any heuristic
    can place it.
    """
    if not text.strip():
        return None, "unknown"

    # Use the head of the document — title page + first few sections is
    # enough to identify revision year and matrix legend, and keeps cost low.
    head = text[: _MAX_CHARS_PER_CHUNK // 3]
    messages = [
        {"role": "system", "content": _METADATA_SYSTEM_PROMPT},
        {"role": "user", "content": _METADATA_USER_TEMPLATE.format(document_text=head)},
    ]
    report_year: int | None = None
    matrix_size = "unknown"
    try:
        raw = await openai_client.chat_completion(
            messages,
            temperature=0.0,
            max_tokens=200,
            json_mode=True,
        )
        payload = _parse_json_payload(raw) or {}
        year_val = payload.get("report_year")
        if isinstance(year_val, int) and 1990 <= year_val <= 2099:
            report_year = year_val
        matrix_size = _normalize_matrix_size(payload.get("matrix_size"))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "risk_outcome_metadata_extraction_failed",
            source_file=source_file,
            error=str(exc),
        )

    if report_year is None:
        report_year = _regex_year_from_text(text)

    logger.info(
        "risk_outcome_metadata_extracted",
        source_file=source_file,
        report_year=report_year,
        matrix_size=matrix_size,
    )
    return report_year, matrix_size


# ---------------------------------------------------------------------------
# Import-rule classifier
# ---------------------------------------------------------------------------


# Classification labels — keep stable, the frontend / logs key off these.
CLASSIFICATION_CLEAN = "clean"
CLASSIFICATION_DROP_PRE_MIN_YEAR = "drop_pre_min_year"
CLASSIFICATION_DROP_6X6 = "drop_6x6_post_min_year"
CLASSIFICATION_FLAG_4X4 = "flag_4x4_post_min_year"
CLASSIFICATION_FLAG_UNKNOWN_YEAR = "flag_unknown_year"


def _classify_for_import(report_year: int | None, matrix_size: str, min_year: int) -> str:
    """Pure rule engine — deterministic, no I/O.

    Rules (per the product spec):
      • report < min_year (regardless of matrix)        -> drop
      • report >= min_year, matrix=6x6                  -> drop
      • report >= min_year, matrix=4x4                  -> flag for review
      • report >= min_year, matrix=5x5                  -> clean
      • report year unknown                             -> flag for review
      • matrix unknown but year >= min_year             -> clean (give benefit of the doubt;
                                                          the verbatim extractor's strict
                                                          schema already filters non-5x5 values)
    """
    if report_year is None:
        return CLASSIFICATION_FLAG_UNKNOWN_YEAR
    if report_year < min_year:
        return CLASSIFICATION_DROP_PRE_MIN_YEAR
    if matrix_size == "6x6":
        return CLASSIFICATION_DROP_6X6
    if matrix_size == "4x4":
        return CLASSIFICATION_FLAG_4X4
    return CLASSIFICATION_CLEAN


def _apply_import_rules(
    risks: list[SharePointRisk],
    *,
    classification: str,
    enforce: bool,
) -> tuple[list[SharePointRisk], list[SharePointRisk]]:
    """Stamp the classification on every row, then route per the rules.

    Returns (clean, flagged). In shadow mode (enforce=False), every row is
    returned in `clean` regardless of classification — the label is still
    stamped so the UI / logs can show what *would* have happened.
    """
    for r in risks:
        r.import_classification = classification

    if not enforce:
        return risks, []

    if classification in (CLASSIFICATION_DROP_PRE_MIN_YEAR, CLASSIFICATION_DROP_6X6):
        return [], []
    if classification in (CLASSIFICATION_FLAG_4X4, CLASSIFICATION_FLAG_UNKNOWN_YEAR):
        return [], risks
    return risks, []


# ---------------------------------------------------------------------------
# Per-file cache entry
# ---------------------------------------------------------------------------


# Bump this whenever the shape of SharePointRisk or _FileCacheEntry changes
# in a way that requires re-extraction, OR when the LLM extraction prompt
# changes meaning enough that previously-cached rows would now be wrong.
# Cached entries built under an older version are invalidated automatically
# on the next scan.
#   v1: original (hazard, severity, likelihood, risk_level)
#   v2: adds report_year, matrix_size, import_classification + risks_flagged
#   v3: extraction prompt now asks for descriptive severity/likelihood NAMES
#       (Catastrophic..Minimal / Frequent..Extremely Improbable) instead of
#       integers/letters, to defeat documents that use the inverted FAA
#       1=Catastrophic convention vs the codebase's 5=Catastrophic storage.
_CACHE_SCHEMA_VERSION = "v3"


def _build_cache_key(drive_item_id: str, size: int, content_type: str) -> str:
    return f"{_CACHE_SCHEMA_VERSION}:{drive_item_id}:{size}:{content_type}"


@dataclass
class _FileCacheEntry:
    risks: list[SharePointRisk]
    notes: list[SharePointParseNote]
    cache_key: str  # schema version + drive_item_id + size + content_type
    cached_at: float = field(default_factory=time.time)
    # Rows the rule engine routed away from the live register. Empty in shadow
    # mode (every row stays in `risks` regardless of classification).
    risks_flagged: list[SharePointRisk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class RiskOutcomeImporter:
    def __init__(
        self,
        crawler: SharePointCrawler,
        openai_client: AzureOpenAIClient,
        stale_after_seconds: float = 3600.0,  # 1 hour — when to auto-rescan
        empty_retry_after_seconds: float = 120.0,  # rescan sooner if last scan yielded 0 risks
    ) -> None:
        self._crawler = crawler
        self._openai = openai_client
        self._stale_after = stale_after_seconds
        self._empty_retry_after = empty_retry_after_seconds

        # Per-file cache: file_id → entry. Never expires on its own; invalidated
        # only when the cache_key (size/content_type) changes.
        self._file_cache: dict[str, _FileCacheEntry] = {}

        # Summary state (protected by lock).
        self._lock = asyncio.Lock()
        self._scan_task: asyncio.Task[None] | None = None
        self._status: str = "idle"
        self._scanned: int = 0
        self._total: int = 0
        self._airports: list[str] = []
        self._notes: list[SharePointParseNote] = []  # one-off scan notes, not per-file
        self._last_completed: float | None = None

    async def snapshot(self) -> SharePointRiskSummary:
        """Return the current known state without triggering a scan."""
        async with self._lock:
            return self._build_summary_locked()

    async def ensure_scan(self, force: bool = False) -> SharePointRiskSummary:
        """Kick off a background scan if none is running and results are stale.

        Returns immediately with whatever is currently cached plus the scan
        status — the frontend should poll until `status == "ready"`.

        Also auto-retries on short notice when the last scan produced zero
        risks — that almost always signals a silent failure (folder name
        mismatch, LLM rejection, etc.) rather than a genuine empty
        portfolio, so we don't want to wait the full stale_after window.
        """
        async with self._lock:
            now = time.time()
            has_any_risks = any(entry.risks for entry in self._file_cache.values())
            stale_window = self._empty_retry_after if not has_any_risks else self._stale_after
            needs_scan = force or (
                self._status != "scanning"
                and (self._last_completed is None or (now - self._last_completed) > stale_window)
            )
            if needs_scan and (self._scan_task is None or self._scan_task.done()):
                self._status = "scanning"
                self._scanned = 0
                self._notes = []
                self._scan_task = asyncio.create_task(self._run_scan())
            return self._build_summary_locked()

    def _build_summary_locked(self) -> SharePointRiskSummary:
        risks: list[SharePointRisk] = []
        flagged: list[SharePointRisk] = []
        notes: list[SharePointParseNote] = list(self._notes)
        for entry in self._file_cache.values():
            risks.extend(entry.risks)
            flagged.extend(entry.risks_flagged)
            notes.extend(entry.notes)
        return SharePointRiskSummary(
            airports=list(self._airports),
            risks=risks,
            notes=notes,
            generated_at=time.time(),
            status=self._status,
            scanned=self._scanned,
            total=self._total,
            last_scan_completed_at=self._last_completed,
            risks_flagged_for_review=flagged,
        )

    async def _run_scan(self) -> None:
        """Background scan: discover files, extract new/changed PDFs via LLM.

        Runs under an asyncio Task with no lock held; updates progress via
        the lock for each file as it completes.
        """
        try:
            airports = await self._crawler.list_airport_folders()
            files = await self._crawler.list_risk_outcome_files()
        except Exception as exc:  # noqa: BLE001
            logger.error("risk_outcome_scan_discovery_failed", exc_info=True)
            async with self._lock:
                self._airports = []
                self._notes.append(
                    SharePointParseNote(
                        airport_identifier="",
                        source_file="",
                        message=f"SharePoint discovery failed: {exc}",
                    )
                )
                self._status = "ready"
                self._last_completed = time.time()
            return

        # Index files by drive_item_id so we can diff against the per-file cache.
        tasks: list[tuple[str, SharePointFile]] = []
        fresh_ids: set[str] = set()
        for f in files:
            if not f.name.lower().endswith(".pdf"):
                continue
            segments = [s for s in f.folder_path.split("/") if s]
            airport_name = _airport_from_segments(segments)
            if not airport_name:
                continue
            cache_key = _build_cache_key(f.drive_item_id, f.size, f.content_type)
            fresh_ids.add(f.drive_item_id)
            existing = self._file_cache.get(f.drive_item_id)
            if existing is not None and existing.cache_key == cache_key:
                continue  # unchanged AND on the current schema version
            tasks.append((airport_name, f))

        # Evict cache entries for files that are no longer present.
        async with self._lock:
            stale = [fid for fid in self._file_cache if fid not in fresh_ids]
            for fid in stale:
                del self._file_cache[fid]
            self._airports = sorted(
                {
                    *airports,
                    *{
                        _airport_from_segments([s for s in f.folder_path.split("/") if s]) or ""
                        for f in files
                    },
                }
                - {""}
            )
            self._scanned = 0
            self._total = len(tasks)

        sem = asyncio.Semaphore(_MAX_PARALLEL_EXTRACTIONS)

        async def process(airport: str, f: SharePointFile) -> None:
            async with sem:
                clean: list[SharePointRisk] = []
                flagged: list[SharePointRisk] = []
                try:
                    data = await self._crawler.download_file(f)
                    text = await DocumentProcessor._extract_text_in_thread(data, f.content_type)
                    report_year, matrix_size = await _extract_doc_metadata(
                        text=text,
                        source_file=f.name,
                        openai_client=self._openai,
                    )
                    risks, notes = await _extract_risks_via_llm(
                        text=text,
                        airport=airport,
                        source_file=f.name,
                        source_url=f.web_url or None,
                        openai_client=self._openai,
                    )
                    for r in risks:
                        r.report_year = report_year
                        r.matrix_size = matrix_size
                    classification = _classify_for_import(
                        report_year, matrix_size, settings.risk_import_min_year
                    )
                    clean, flagged = _apply_import_rules(
                        risks,
                        classification=classification,
                        enforce=settings.risk_import_enforce,
                    )
                    logger.info(
                        "risk_outcome_file_classified",
                        airport=airport,
                        source_file=f.name,
                        report_year=report_year,
                        matrix_size=matrix_size,
                        classification=classification,
                        rows_extracted=len(risks),
                        rows_clean=len(clean),
                        rows_flagged=len(flagged),
                        rows_dropped=len(risks) - len(clean) - len(flagged),
                        enforce=settings.risk_import_enforce,
                    )
                    if classification != CLASSIFICATION_CLEAN:
                        notes.append(
                            SharePointParseNote(
                                airport_identifier=airport,
                                source_file=f.name,
                                message=(
                                    f"import rule: {classification} "
                                    f"(year={report_year}, matrix={matrix_size}); "
                                    f"{'enforced' if settings.risk_import_enforce else 'shadow mode — kept anyway'}"
                                ),
                            )
                        )
                except Exception as exc:  # noqa: BLE001
                    notes = [
                        SharePointParseNote(
                            airport_identifier=airport,
                            source_file=f.name,
                            message=f"scan failed: {exc}",
                        )
                    ]
                async with self._lock:
                    self._file_cache[f.drive_item_id] = _FileCacheEntry(
                        risks=clean,
                        notes=notes,
                        cache_key=_build_cache_key(f.drive_item_id, f.size, f.content_type),
                        risks_flagged=flagged,
                    )
                    self._scanned += 1

        await asyncio.gather(*[process(a, f) for a, f in tasks])

        async with self._lock:
            self._status = "ready"
            self._last_completed = time.time()
            logger.info(
                "risk_outcome_scan_complete",
                airports=len(self._airports),
                files_indexed=len(self._file_cache),
                files_extracted_this_scan=len(tasks),
            )

    # Legacy method name kept for the existing endpoint signature.
    async def scan_all(self, force_refresh: bool = False) -> SharePointRiskSummary:
        return await self.ensure_scan(force=force_refresh)
