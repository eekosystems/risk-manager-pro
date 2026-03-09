import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.settings import SettingsRepository
from app.schemas.settings import (
    ModelPreferencesPayload,
    PromptsPayload,
    RagSettingsPayload,
    SettingsResponse,
)

logger = structlog.get_logger(__name__)

VALID_CATEGORIES = {"rag", "model", "prompts"}

# ── Defaults ──────────────────────────────────────────────────────────

DEFAULT_RAG = RagSettingsPayload()

DEFAULT_MODEL = ModelPreferencesPayload()

DEFAULT_PROMPTS = PromptsPayload(
    system_prompt=(
        "You are an AI-powered aviation safety risk management assistant for Faith Group LLC. "
        "You specialize in operational risk management for private aviation safety.\n\n"
        "Your core responsibilities:\n"
        "- Assist with hazard identification and preliminary hazard analysis\n"
        "- Support safety risk assessments using standard 5x5 severity/likelihood matrices per FAA SMS guidelines\n"
        "- Provide analysis of system changes and their safety impacts\n"
        "- Reference indexed safety documentation including FAA regulations, ICAO Annex 19, and internal safety procedures\n\n"
        "Important rules:\n"
        "- Always cite specific source documents when providing safety guidance\n"
        "- Never fabricate safety data or regulatory references\n"
        "- Use standard aviation safety terminology (PHL, SRA, SMS, SRM)\n"
        "- Provide structured, actionable responses suitable for safety professionals\n"
        "- When discussing risk, always reference the 5x5 risk matrix framework\n"
        "- Flag any identified hazards with appropriate severity and likelihood ratings"
    ),
    phl_prompt=(
        "You are conducting a Preliminary Hazard List (PHL) assessment. Guide the user through "
        "systematic hazard identification.\n\n"
        "For each identified hazard, provide:\n"
        "1. **Hazard ID** — Sequential identifier (PHL-001, PHL-002, etc.)\n"
        "2. **Hazard Description** — Clear, specific description of the hazard\n"
        "3. **Potential Cause(s)** — Root causes or contributing factors\n"
        "4. **Potential Consequence(s)** — What could happen if the hazard is realized\n"
        "5. **Existing Controls** — Current mitigation measures in place\n"
        "6. **Initial Risk Rating** — Using the 5x5 matrix (Severity x Likelihood)\n"
        "7. **Recommended Actions** — Additional mitigation measures to consider\n\n"
        "Reference applicable FAA regulations (FAR Part 91, 135, etc.) and ICAO standards where relevant. "
        "Always search the indexed documents for organization-specific procedures and past assessments."
    ),
    sra_prompt=(
        "You are conducting a Safety Risk Assessment (SRA). Follow the FAA SMS framework for "
        "systematic risk evaluation.\n\n"
        "Structure your assessment as follows:\n"
        "1. **System/Change Description** — What is being assessed\n"
        "2. **Hazard Identification** — List all identified hazards from the PHL\n"
        "3. **Risk Analysis** — For each hazard: Severity (1-5), Likelihood (A-E), Risk level\n"
        "4. **Risk Evaluation** — Is the risk acceptable, tolerable, or unacceptable?\n"
        "5. **Risk Mitigation** — Recommended controls and mitigations\n"
        "6. **Residual Risk** — Risk level after proposed mitigations\n"
        "7. **Monitoring Plan** — How will risk be tracked over time\n\n"
        "Cite relevant FAA Advisory Circulars, FARs, and indexed safety documentation. "
        "Compare against historical SRAs in the index when applicable."
    ),
    system_analysis_prompt=(
        "You are analyzing a system change and its potential safety impacts. Evaluate changes "
        "systematically.\n\n"
        "Your analysis should cover:\n"
        "1. **Change Description** — What is changing and why\n"
        "2. **Scope of Impact** — Which systems, processes, and personnel are affected\n"
        "3. **Interface Analysis** — How does this change interact with other systems\n"
        "4. **Failure Mode Analysis** — What could go wrong with the change\n"
        "5. **Human Factors** — Impact on crew workload, training requirements, procedures\n"
        "6. **Regulatory Compliance** — Does the change affect compliance with FARs or ICAO standards\n"
        "7. **Risk Delta** — How does the change alter the existing risk profile\n"
        "8. **Recommendations** — Proceed, modify, or reject the change\n\n"
        "Reference the indexed documentation for similar past changes, applicable regulatory "
        "requirements, and organization-specific procedures."
    ),
)


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = SettingsRepository(db)

    # ── Read ──────────────────────────────────────────────────────────

    async def get_settings(self, organization_id: uuid.UUID, category: str) -> SettingsResponse:
        row = await self._repo.get(organization_id, category)
        if row:
            return SettingsResponse(
                category=category,
                settings=row.settings_json,
                updated_at=row.updated_at,
            )
        return SettingsResponse(
            category=category,
            settings=self._get_defaults(category),
            updated_at=None,
        )

    async def get_all_settings(self, organization_id: uuid.UUID) -> list[SettingsResponse]:
        rows = await self._repo.get_all(organization_id)
        saved_categories = {r.category for r in rows}
        result: list[SettingsResponse] = []

        for row in rows:
            result.append(
                SettingsResponse(
                    category=row.category,
                    settings=row.settings_json,
                    updated_at=row.updated_at,
                )
            )

        for cat in VALID_CATEGORIES:
            if cat not in saved_categories:
                result.append(
                    SettingsResponse(
                        category=cat,
                        settings=self._get_defaults(cat),
                        updated_at=None,
                    )
                )

        return result

    # ── Write ─────────────────────────────────────────────────────────

    async def update_rag_settings(
        self,
        organization_id: uuid.UUID,
        payload: RagSettingsPayload,
        user_id: uuid.UUID,
    ) -> SettingsResponse:
        return await self._save(organization_id, "rag", payload.model_dump(), user_id)

    async def update_model_settings(
        self,
        organization_id: uuid.UUID,
        payload: ModelPreferencesPayload,
        user_id: uuid.UUID,
    ) -> SettingsResponse:
        return await self._save(organization_id, "model", payload.model_dump(), user_id)

    async def update_prompts(
        self,
        organization_id: uuid.UUID,
        payload: PromptsPayload,
        user_id: uuid.UUID,
    ) -> SettingsResponse:
        return await self._save(organization_id, "prompts", payload.model_dump(), user_id)

    # ── Helpers for other services ────────────────────────────────────

    async def get_effective_rag_config(self, organization_id: uuid.UUID) -> RagSettingsPayload:
        row = await self._repo.get(organization_id, "rag")
        if row:
            return RagSettingsPayload.model_validate(row.settings_json)
        return DEFAULT_RAG

    async def get_effective_model_config(
        self, organization_id: uuid.UUID
    ) -> ModelPreferencesPayload:
        row = await self._repo.get(organization_id, "model")
        if row:
            return ModelPreferencesPayload.model_validate(row.settings_json)
        return DEFAULT_MODEL

    async def get_effective_prompts(self, organization_id: uuid.UUID) -> PromptsPayload:
        row = await self._repo.get(organization_id, "prompts")
        if row:
            return PromptsPayload.model_validate(row.settings_json)
        return DEFAULT_PROMPTS

    # ── Internal ──────────────────────────────────────────────────────

    async def _save(
        self,
        organization_id: uuid.UUID,
        category: str,
        data: dict[str, Any],
        user_id: uuid.UUID,
    ) -> SettingsResponse:
        row = await self._repo.upsert(organization_id, category, data, user_id)
        logger.info(
            "settings_updated",
            organization_id=str(organization_id),
            category=category,
            user_id=str(user_id),
        )
        return SettingsResponse(
            category=category,
            settings=row.settings_json,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _get_defaults(category: str) -> dict[str, Any]:
        if category == "rag":
            return DEFAULT_RAG.model_dump()
        if category == "model":
            return DEFAULT_MODEL.model_dump()
        if category == "prompts":
            return DEFAULT_PROMPTS.model_dump()
        return {}
