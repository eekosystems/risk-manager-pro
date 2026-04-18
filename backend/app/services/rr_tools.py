"""Tool definitions + dispatcher for Sub-Prompt 4 (Risk Register) chat mode.

The Risk Register chat conversation walks the user through the 8-step
hazard entry flow defined in Sub-Prompt 4. Once enough fields are
captured, the LLM is expected to call `save_risk_register_record` to
persist the record to `risk_entries` (and the 5x5 matrix renders the
new dot without a page refresh, since the existing Risk Register page
polls via React Query).

These tools are passed to the model only when function_type=risk_register.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from app.models.risk import (
    HazardCategory5M,
    HazardCategoryICAO,
    Likelihood,
    OperationalDomain,
    RecordSource,
    RecordStatus,
    RiskLevel,
    RiskMatrixApplied,
    Severity,
    ValidationStatus,
)
from app.schemas.risk import (
    CreateMitigationRequest,
    CreateRiskEntryRequest,
)

if TYPE_CHECKING:
    import uuid

    from app.services.risk import RiskService
    from app.services.sharepoint_crawler import SharePointCrawler

logger = structlog.get_logger(__name__)


RR_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_risk_registry",
            "description": (
                "Look up prior risk registry files for an airport from Faith "
                "Group's SharePoint. Each client airport has a `risk-outcome` "
                "subfolder containing its historical risk register documents. "
                "Call this early in the conversation — as soon as the user "
                "tells you which airport they're working on — so you can cite "
                "analogous prior risks. Returns file names, modified dates, "
                "and SharePoint URLs; optionally filters by hazard keywords."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_identifier": {
                        "type": "string",
                        "description": (
                            "ICAO/FAA code (e.g., KSFO) or airport folder name. "
                            "Matched case-insensitively against the parent folder "
                            "above `/risk-outcome/` in SharePoint."
                        ),
                    },
                    "hazard_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional keywords to narrow results (substring match "
                            "against file names). Keep to 1-3 terms; omit to list "
                            "all files."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max files to return (default 10).",
                        "default": 10,
                    },
                },
                "required": ["airport_identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_risk_register_record",
            "description": (
                "Persist a completed hazard record to the Airport Risk Register. "
                "Call this ONLY after you have captured the Sub-Prompt 4 required "
                "fields from the user: hazard description, credible outcome, "
                "operational domain, 5M category, severity, likelihood, and "
                "existing controls. Optional: sub-location, ICAO category, "
                "mitigation actions, ACM cross-reference. On success the record "
                "appears on the 5x5 risk matrix and in the Risk Register list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the record (≤500 chars).",
                    },
                    "airport_identifier": {
                        "type": "string",
                        "description": "ICAO/FAA code for the airport (e.g., KSFO).",
                    },
                    "hazard": {
                        "type": "string",
                        "description": "Plain-language description of the hazard.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Longer narrative description of the context.",
                    },
                    "potential_credible_outcome": {
                        "type": "string",
                        "description": (
                            "Worst credible outcome if the hazard manifests, vetted "
                            "with the user for credibility (not worst possible)."
                        ),
                    },
                    "operational_domain": {
                        "type": "string",
                        "enum": [d.value for d in OperationalDomain],
                    },
                    "sub_location": {
                        "type": "string",
                        "description": "Airport-specific sub-location (e.g., Gate 1A, Fuel Farm).",
                    },
                    "hazard_category_5m": {
                        "type": "string",
                        "enum": [c.value for c in HazardCategory5M],
                        "description": "FAA 5M primary category.",
                    },
                    "hazard_category_icao": {
                        "type": "string",
                        "enum": [c.value for c in HazardCategoryICAO],
                        "description": (
                            "ICAO secondary category. If omitted, the default for "
                            "the chosen 5M category is applied."
                        ),
                    },
                    "severity": {
                        "type": "integer",
                        "enum": [s.value for s in Severity],
                        "description": "Severity score 1-5 (1=Minimal, 5=Catastrophic).",
                    },
                    "likelihood": {
                        "type": "string",
                        "enum": [lv.value for lv in Likelihood],
                        "description": "Likelihood score A-E (A=Frequent, E=Extremely Improbable).",
                    },
                    "risk_matrix_applied": {
                        "type": "string",
                        "enum": [m.value for m in RiskMatrixApplied],
                        "default": "faa_5x5",
                    },
                    "existing_controls": {
                        "type": "string",
                        "description": (
                            "Narrative of controls already in place. 'None' if no "
                            "controls exist."
                        ),
                    },
                    "residual_risk_level": {
                        "type": "string",
                        "enum": [lv.value for lv in RiskLevel],
                        "description": "Post-mitigation risk level (blank if not yet assessed).",
                    },
                    "record_status": {
                        "type": "string",
                        "enum": [s.value for s in RecordStatus],
                        "default": "open",
                    },
                    "validation_status": {
                        "type": "string",
                        "enum": [s.value for s in ValidationStatus],
                        "default": "pending",
                    },
                    "acm_cross_reference": {
                        "type": "string",
                        "description": "ACM section + amendment status (Part 139 only).",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Free-text additional context.",
                    },
                    "mitigations": {
                        "type": "array",
                        "description": (
                            "Optional mitigation actions. Each requires what/who/when "
                            "(description/assignee/due_date) per Sub-Prompt 4 §Step 7."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "assignee": {"type": "string"},
                                "due_date": {
                                    "type": "string",
                                    "description": "ISO-8601 date string.",
                                },
                                "verification_method": {"type": "string"},
                            },
                            "required": ["title", "description"],
                        },
                    },
                },
                "required": [
                    "title",
                    "airport_identifier",
                    "hazard",
                    "description",
                    "potential_credible_outcome",
                    "operational_domain",
                    "hazard_category_5m",
                    "severity",
                    "likelihood",
                    "existing_controls",
                ],
            },
        },
    },
]


async def execute_tool_call(
    *,
    tool_call: dict[str, Any],
    risk_service: RiskService,
    sharepoint: SharePointCrawler,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> str:
    """Execute one LLM tool call. Returns a JSON string for the tool result.

    The return value is fed back to the model via a `role="tool"` message.
    On success, returns a success envelope including the saved record id so
    the model can tell the user "Saved as RR-<id>". On failure, returns an
    error envelope so the model can apologize and ask for corrections.
    """
    name = tool_call["name"]
    raw_args = tool_call["arguments"] or "{}"

    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError as exc:
        logger.error("rr_tool_bad_json", name=name, error=str(exc))
        return json.dumps({"ok": False, "error": f"Invalid JSON arguments: {exc}"})

    if name == "save_risk_register_record":
        return await _save_risk_register_record(
            args=args,
            risk_service=risk_service,
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
        )

    if name == "search_risk_registry":
        return await _search_risk_registry(args=args, sharepoint=sharepoint)

    return json.dumps({"ok": False, "error": f"Unknown tool: {name}"})


async def _search_risk_registry(
    *,
    args: dict[str, Any],
    sharepoint: SharePointCrawler,
) -> str:
    """List files from the `/risk-outcome/` folder for the given airport.

    Returns file metadata (name, size, folder_path, web_url) as a JSON envelope.
    Applies optional keyword filtering on file names. Credential / config
    errors are surfaced gracefully so the LLM can tell the user the lookup
    failed without crashing the conversation.
    """
    airport = args.get("airport_identifier")
    if not airport:
        return json.dumps({"ok": False, "error": "airport_identifier is required"})

    keywords_raw = args.get("hazard_keywords") or []
    keywords = [str(k).lower() for k in keywords_raw if str(k).strip()]
    limit = int(args.get("limit") or 10)

    try:
        files = await sharepoint.list_risk_outcome_files(airport_identifier=airport)
    except RuntimeError as exc:
        logger.warning("rr_search_sharepoint_unavailable", error=str(exc))
        return json.dumps(
            {
                "ok": False,
                "error": (
                    f"SharePoint lookup unavailable: {exc}. Proceed with the "
                    "conversation using the user's input and any indexed knowledge."
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001 — surface to LLM
        logger.error("rr_search_sharepoint_failed", airport=airport, exc_info=True)
        return json.dumps(
            {"ok": False, "error": f"SharePoint lookup failed: {exc}"}
        )

    if keywords:
        files = [
            f for f in files if any(k in f.name.lower() for k in keywords)
        ]

    files_sorted = sorted(files, key=lambda f: f.name.lower())[:limit]

    return json.dumps(
        {
            "ok": True,
            "airport_identifier": airport,
            "match_count": len(files_sorted),
            "files": [
                {
                    "name": f.name,
                    "folder_path": f.folder_path,
                    "size_bytes": f.size,
                    "web_url": f.web_url,
                    "content_type": f.content_type,
                }
                for f in files_sorted
            ],
            "note": (
                "These files live in the airport's /risk-outcome/ folder in "
                "SharePoint. Cite file names to the user when referencing "
                "prior risk history; they can open the files via the web_url."
            ),
        }
    )


async def _save_risk_register_record(
    *,
    args: dict[str, Any],
    risk_service: RiskService,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> str:
    """Validate and persist a risk record via RiskService."""
    mitigations_payload = args.pop("mitigations", None) or []

    # Map LLM args to CreateRiskEntryRequest. Pydantic handles enum coercion
    # from string values; missing optional fields default in the schema.
    try:
        create_payload = CreateRiskEntryRequest(
            title=args["title"],
            description=args["description"],
            hazard=args["hazard"],
            severity=args["severity"],
            likelihood=args["likelihood"],
            function_type="risk_register",
            conversation_id=conversation_id,
            notes=args.get("notes"),
            airport_identifier=args.get("airport_identifier"),
            potential_credible_outcome=args.get("potential_credible_outcome"),
            operational_domain=args.get("operational_domain"),
            sub_location=args.get("sub_location"),
            hazard_category_5m=args.get("hazard_category_5m"),
            hazard_category_icao=args.get("hazard_category_icao"),
            risk_matrix_applied=args.get("risk_matrix_applied", "faa_5x5"),
            existing_controls=args.get("existing_controls"),
            residual_risk_level=args.get("residual_risk_level"),
            record_status=args.get("record_status", "open"),
            validation_status=args.get("validation_status", "pending"),
            source=RecordSource.RMP_SP4,
            acm_cross_reference=args.get("acm_cross_reference"),
        )
    except (KeyError, ValueError) as exc:
        logger.warning("rr_tool_validation_failed", error=str(exc))
        return json.dumps(
            {
                "ok": False,
                "error": f"Validation failed: {exc}. Ask the user for the missing field.",
            }
        )

    try:
        entry = await risk_service.create_risk_entry(
            payload=create_payload,
            user_id=user_id,
            organization_id=organization_id,
        )
    except Exception as exc:  # noqa: BLE001 — surface to LLM
        logger.error("rr_tool_create_failed", exc_info=True)
        return json.dumps(
            {"ok": False, "error": f"Database error while saving: {exc}"}
        )

    created_mitigations: list[dict[str, Any]] = []
    for m in mitigations_payload:
        try:
            mit_payload = CreateMitigationRequest(**m)
        except (TypeError, ValueError) as exc:
            logger.warning("rr_tool_mitigation_invalid", error=str(exc), payload=m)
            continue
        try:
            mit = await risk_service.create_mitigation(
                risk_id=entry.id,
                organization_id=organization_id,
                payload=mit_payload,
            )
            created_mitigations.append({"id": str(mit.id), "title": mit.title})
        except Exception as exc:  # noqa: BLE001 — partial failure shouldn't drop the record
            logger.error("rr_tool_mitigation_create_failed", exc_info=True)
            created_mitigations.append(
                {"title": m.get("title"), "error": str(exc)}
            )

    logger.info(
        "rr_tool_record_saved",
        record_id=str(entry.id),
        mitigation_count=len(created_mitigations),
        airport=entry.airport_identifier,
        risk_level=entry.risk_level.value,
    )

    return json.dumps(
        {
            "ok": True,
            "record_id": str(entry.id),
            "risk_level": entry.risk_level.value,
            "severity": int(entry.severity),
            "likelihood": entry.likelihood,
            "mitigations": created_mitigations,
            "message": (
                f"Record saved. Risk level: {entry.risk_level.value}. "
                f"The 5x5 matrix on the Risk Register page will reflect this "
                f"hazard on the next refresh."
            ),
        }
    )
