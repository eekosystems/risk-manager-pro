import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    resource_type: str
    resource_id: str | None
    is_read: bool
    created_at: datetime
    triggered_by_user_id: uuid.UUID

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    count: int
