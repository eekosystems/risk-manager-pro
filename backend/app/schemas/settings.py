import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── RAG Settings ──────────────────────────────────────────────────────


class RagSettingsPayload(BaseModel):
    chunk_size: int = Field(512, ge=100, le=4000)
    chunk_overlap: int = Field(50, ge=0, le=500)
    top_k: int = Field(5, ge=1, le=20)
    score_threshold: float = Field(0.01, ge=0.0, le=1.0)
    search_type: str = Field("hybrid", pattern=r"^(hybrid|vector|keyword)$")
    embedding_model: str = Field("text-embedding-3-small")
    rerank_enabled: bool = True
    max_context_tokens: int = Field(4096, ge=512, le=16384)


# ── Model Preferences ────────────────────────────────────────────────


class ModelPreferencesPayload(BaseModel):
    chat_model: str = Field("gpt-4o")
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_output_tokens: int = Field(4096, ge=256, le=16384)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    frequency_penalty: float = Field(0.0, ge=0.0, le=2.0)
    presence_penalty: float = Field(0.0, ge=0.0, le=2.0)
    stream_responses: bool = True


# ── Prompts ───────────────────────────────────────────────────────────


class PromptsPayload(BaseModel):
    system_prompt: str = Field(..., min_length=1, max_length=200000)
    phl_prompt: str = Field(..., min_length=1, max_length=200000)
    sra_prompt: str = Field(..., min_length=1, max_length=200000)
    system_analysis_prompt: str = Field(..., min_length=1, max_length=200000)
    document_interpretation_prompt: str = Field(..., min_length=1, max_length=200000)
    risk_register_prompt: str = Field(..., min_length=1, max_length=200000)
    indexing_instructions: str = Field(..., min_length=1, max_length=80000)


# ── QA/QC Settings ────────────────────────────────────────────────────


class DeliveryMode(enum.StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    BOTH = "both"


class DigestFrequency(enum.StrEnum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"


class QaqcSettingsPayload(BaseModel):
    reviewer_user_ids: list[str] = Field(default_factory=list)

    notify_on_chat: bool = True
    notify_on_risk_created: bool = True
    notify_on_risk_updated: bool = True
    notify_on_mitigation_created: bool = True
    notify_on_document_indexed: bool = False

    delivery_mode: DeliveryMode = DeliveryMode.BOTH
    digest_frequency: DigestFrequency = DigestFrequency.IMMEDIATE
    digest_send_hour_utc: int = Field(13, ge=0, le=23)


# ── Generic Settings Response ─────────────────────────────────────────


class SettingsResponse(BaseModel):
    category: str
    settings: dict[str, Any]
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
