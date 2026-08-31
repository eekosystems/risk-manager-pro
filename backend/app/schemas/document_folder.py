import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentFolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None


class RenameFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MoveFolderRequest(BaseModel):
    parent_id: uuid.UUID | None = None


class MoveDocumentsRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    folder_id: uuid.UUID | None = None


class MoveDocumentsResult(BaseModel):
    moved: int
    folder_id: uuid.UUID | None
