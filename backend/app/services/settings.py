import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.settings import SettingsRepository
from app.schemas.settings import (
    ModelPreferencesPayload,
    PromptsPayload,
    QaqcSettingsPayload,
    RagSettingsPayload,
    SettingsResponse,
)
from app.services.prompts import (
    GENERAL_PROMPT,
    INDEXING_INSTRUCTIONS,
    PHL_PROMPT,
    SRA_PROMPT,
    SYSTEM_ANALYSIS_PROMPT,
)

logger = structlog.get_logger(__name__)

VALID_CATEGORIES = {"rag", "model", "prompts", "qaqc"}

# ── Defaults ──────────────────────────────────────────────────────────

DEFAULT_RAG = RagSettingsPayload()

DEFAULT_MODEL = ModelPreferencesPayload()

DEFAULT_QAQC = QaqcSettingsPayload()

DEFAULT_PROMPTS = PromptsPayload(
    system_prompt=GENERAL_PROMPT,
    phl_prompt=PHL_PROMPT,
    sra_prompt=SRA_PROMPT,
    system_analysis_prompt=SYSTEM_ANALYSIS_PROMPT,
    indexing_instructions=INDEXING_INSTRUCTIONS,
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

    async def update_qaqc_settings(
        self,
        organization_id: uuid.UUID,
        payload: QaqcSettingsPayload,
        user_id: uuid.UUID,
    ) -> SettingsResponse:
        return await self._save(organization_id, "qaqc", payload.model_dump(), user_id)

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

    async def get_effective_qaqc_config(
        self, organization_id: uuid.UUID
    ) -> QaqcSettingsPayload:
        row = await self._repo.get(organization_id, "qaqc")
        if row:
            return QaqcSettingsPayload.model_validate(row.settings_json)
        return DEFAULT_QAQC

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
        if category == "qaqc":
            return DEFAULT_QAQC.model_dump()
        return {}
