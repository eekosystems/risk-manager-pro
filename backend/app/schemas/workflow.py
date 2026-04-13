import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.workflow import WorkflowStatus, WorkflowType


class CreateWorkflowRequest(BaseModel):
    type: WorkflowType
    title: str = Field(default="", max_length=500)
    data: dict[str, Any] = Field(default_factory=dict)
    conversation_id: uuid.UUID | None = None


class UpdateWorkflowRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    data: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    type: WorkflowType
    status: WorkflowStatus
    title: str
    data: dict[str, Any]
    conversation_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    risk_entry_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApproveWorkflowRequest(BaseModel):
    approve: bool = True
    notes: str | None = None
