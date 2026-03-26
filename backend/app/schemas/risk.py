import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.risk import (
    Likelihood,
    MitigationStatus,
    RiskLevel,
    RiskStatus,
    Severity,
)

# --- Risk Entry Schemas ---


class CreateRiskEntryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    hazard: str = Field(..., min_length=1)
    severity: Severity
    likelihood: Likelihood
    function_type: str = Field(default="general", max_length=20)
    conversation_id: uuid.UUID | None = None
    notes: str | None = None


class UpdateRiskEntryRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    hazard: str | None = Field(default=None, min_length=1)
    severity: Severity | None = None
    likelihood: Likelihood | None = None
    status: RiskStatus | None = None
    notes: str | None = None


class MitigationResponse(BaseModel):
    id: uuid.UUID
    risk_entry_id: uuid.UUID
    title: str
    description: str
    assignee: str | None
    due_date: datetime | None
    status: MitigationStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RiskEntryResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID
    title: str
    description: str
    hazard: str
    severity: int
    likelihood: str
    risk_level: RiskLevel
    status: RiskStatus
    function_type: str
    conversation_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RiskEntryDetailResponse(RiskEntryResponse):
    mitigations: list[MitigationResponse]


class RiskEntryListItem(BaseModel):
    id: uuid.UUID
    title: str
    hazard: str
    severity: int
    likelihood: str
    risk_level: RiskLevel
    status: RiskStatus
    function_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Mitigation Schemas ---


class CreateMitigationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = None


class UpdateMitigationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = None
    status: MitigationStatus | None = None
