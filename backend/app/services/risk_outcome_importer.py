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
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from app.services.document_processor import DocumentProcessor

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
    for i, seg in enumerate(segments):
        if seg.lower() == "risk-outcome" and i > 0:
            return segments[i - 1]
    return None


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are extracting structured risk register entries from aviation safety "
    "documents. Given the text of one PDF, return ONLY a JSON object of the "
    "exact shape described — no prose, no commentary, no code fences."
)

_USER_TEMPLATE = """\
Extract every hazard listed in the following risk register document. Return
ONLY this JSON shape (no prose):

{{
  "risks": [
    {{
      "hazard": "short description (required, under 250 chars)",
      "severity": <integer 1-5, where 1=Minimal and 5=Catastrophic>,
      "likelihood": "<letter A-E, where A=Frequent and E=Extremely Improbable>",
      "risk_level": "<low | medium | high | extreme — optional>"
    }}
  ]
}}

Rules:
- Only include entries that clearly represent an individual hazard with an
  assessed severity AND likelihood. Skip summaries, headers, narrative, and
  table-of-contents entries.
- If the document uses a different scoring scheme, translate to the FAA
  1-5 / A-E convention.
- Return {{"risks": []}} if no hazards are found.

Document text:
---
{document_text}
---

Return ONLY the JSON object.
"""


_MAX_PDF_CHARS = 40_000
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
    truncated = text if len(text) <= _MAX_PDF_CHARS else text[:_MAX_PDF_CHARS]
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(document_text=truncated)},
    ]
    try:
        raw = await openai_client.chat_completion(
            messages,
            temperature=0.0,
            max_tokens=4000,
            json_mode=True,
        )
    except Exception as exc:  # noqa: BLE001
        return [], [
            SharePointParseNote(
                airport_identifier=airport,
                source_file=source_file,
                message=f"LLM extraction failed: {exc}",
            )
        ]
    payload = _parse_json_payload(raw)
    if payload is None or not isinstance(payload.get("risks"), list):
        return [], [
            SharePointParseNote(
                airport_identifier=airport,
                source_file=source_file,
                message="LLM did not return a {risks:[...]} object",
            )
        ]
    risks: list[SharePointRisk] = []
    notes: list[SharePointParseNote] = []
    for idx, row in enumerate(payload["risks"]):
        if not isinstance(row, dict):
            continue
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
        hazard_text = str(row.get("hazard") or "").strip() or f"Hazard {idx + 1}"
        risk_level = _normalize_risk_level(row.get("risk_level")) or _compute_risk_level(
            severity, likelihood
        )
        risks.append(
            SharePointRisk(
                airport_identifier=airport,
                hazard=hazard_text[:500],
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
    return risks, notes


# ---------------------------------------------------------------------------
# Per-file cache entry
# ---------------------------------------------------------------------------


@dataclass
class _FileCacheEntry:
    risks: list[SharePointRisk]
    notes: list[SharePointParseNote]
    cache_key: str  # drive_item_id + size + content_type
    cached_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class RiskOutcomeImporter:
    def __init__(
        self,
        crawler: SharePointCrawler,
        openai_client: AzureOpenAIClient,
        stale_after_seconds: float = 3600.0,  # 1 hour — when to auto-rescan
    ) -> None:
        self._crawler = crawler
        self._openai = openai_client
        self._stale_after = stale_after_seconds

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
        """
        async with self._lock:
            needs_scan = force or (
                self._status != "scanning"
                and (
                    self._last_completed is None
                    or (time.time() - self._last_completed) > self._stale_after
                )
            )
            if needs_scan and (self._scan_task is None or self._scan_task.done()):
                self._status = "scanning"
                self._scanned = 0
                self._notes = []
                self._scan_task = asyncio.create_task(self._run_scan())
            return self._build_summary_locked()

    def _build_summary_locked(self) -> SharePointRiskSummary:
        risks: list[SharePointRisk] = []
        notes: list[SharePointParseNote] = list(self._notes)
        for entry in self._file_cache.values():
            risks.extend(entry.risks)
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
            cache_key = f"{f.drive_item_id}:{f.size}:{f.content_type}"
            fresh_ids.add(f.drive_item_id)
            existing = self._file_cache.get(f.drive_item_id)
            if existing is not None and existing.cache_key == cache_key:
                continue  # unchanged — keep cached entry
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
                try:
                    data = await self._crawler.download_file(f)
                    text = await DocumentProcessor._extract_text_in_thread(data, f.content_type)
                    risks, notes = await _extract_risks_via_llm(
                        text=text,
                        airport=airport,
                        source_file=f.name,
                        source_url=f.web_url or None,
                        openai_client=self._openai,
                    )
                except Exception as exc:  # noqa: BLE001
                    risks = []
                    notes = [
                        SharePointParseNote(
                            airport_identifier=airport,
                            source_file=f.name,
                            message=f"scan failed: {exc}",
                        )
                    ]
                async with self._lock:
                    self._file_cache[f.drive_item_id] = _FileCacheEntry(
                        risks=risks,
                        notes=notes,
                        cache_key=f"{f.drive_item_id}:{f.size}:{f.content_type}",
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
