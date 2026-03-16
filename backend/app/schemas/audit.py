import uuid
from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


class AuditFilterParams(BaseModel):
    action: str | None = None
    resource_type: str | None = None
    outcome: str | None = None
    user_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
