import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.conversation import FunctionType


class CitationSchema(BaseModel):
    source: str
    source_type: str = "client"
    section: str | None = None
    content: str
    chunk_id: str | None = None
    rank: int | None = None
    match_tier: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: uuid.UUID | None = None
    function_type: FunctionType = FunctionType.GENERAL
    routing_locked: bool = False
    recent_upload_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationSchema] | None = None
    created_at: datetime
    # Structured hazard payload parsed out of the model's `<rr_payload>` block
    # on PHL outputs. Null when the output produced none. Exposed so Risk
    # Register ingestion and exports can consume it without re-parsing prose.
    rr_payload: dict[str, Any] | list[Any] | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _lift_rr_payload(cls, data: Any) -> Any:
        """Surface the stored payload when validating a Message ORM row.

        `rr_payload` lives inside `metadata_json`, so plain attribute mapping
        would silently drop it and every conversation fetch would report null.
        """
        metadata = getattr(data, "metadata_json", None)
        if metadata is None or not isinstance(metadata, dict):
            return data
        payload = metadata.get("rr_payload")
        if not isinstance(payload, dict | list):
            return data
        return {
            "id": data.id,
            "role": data.role,
            "content": data.content,
            "citations": data.citations,
            "created_at": data.created_at,
            "rr_payload": payload,
        }


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: MessageResponse
    title: str
    routed_function_type: FunctionType


class ConversationListItem(BaseModel):
    id: uuid.UUID
    title: str
    function_type: FunctionType
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str
    function_type: FunctionType
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = {"from_attributes": True}


class EmailChatMessageRequest(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=50000)
