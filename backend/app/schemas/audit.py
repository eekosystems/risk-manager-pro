import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditEntryResponse(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str
    correlation_id: uuid.UUID
    outcome: str
    organization_id: uuid.UUID | None
    # What changed: before/after values, the originating chat, and the like.
    metadata: dict[str, object] | None = Field(default=None, validation_alias="metadata_json")

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditFilterParams(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    outcome: str | None = None
    user_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
