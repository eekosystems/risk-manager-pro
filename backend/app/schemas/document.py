import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentStatus, SourceType


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    source_type: SourceType
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    source_type: SourceType
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    source_type: SourceType
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
