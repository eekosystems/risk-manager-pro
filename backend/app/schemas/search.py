import uuid
from datetime import datetime

from pydantic import BaseModel


class ConversationHit(BaseModel):
    id: uuid.UUID
    title: str
    function_type: str
    snippet: str
    matched_message_id: uuid.UUID
    updated_at: datetime


class DocumentHit(BaseModel):
    id: uuid.UUID
    filename: str
    source_type: str
    status: str


class SearchResults(BaseModel):
    conversations: list[ConversationHit]
    documents: list[DocumentHit]
