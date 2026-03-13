import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.conversation import FunctionType


class CitationSchema(BaseModel):
    source: str
    section: str | None = None
    content: str
    score: float | None = None
    chunk_id: str | None = None
    rank: int | None = None
    match_tier: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: uuid.UUID | None = None
    function_type: FunctionType = FunctionType.GENERAL


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationSchema] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: MessageResponse
    title: str


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
