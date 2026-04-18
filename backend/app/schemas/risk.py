import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.risk import (
    HazardCategory5M,
    HazardCategoryICAO,
    Likelihood,
    MitigationStatus,
    OperationalDomain,
    RecordSource,
    RecordStatus,
    RiskLevel,
    RiskMatrixApplied,
    RiskStatus,
    Severity,
    SyncStatus,
    ValidationStatus,
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

    # --- Sub-Prompt 4 / Risk Register fields (all optional for backward compat) ---
    airport_identifier: str | None = Field(default=None, max_length=20)
    potential_credible_outcome: str | None = None
    operational_domain: OperationalDomain | None = None
    sub_location: str | None = Field(default=None, max_length=255)
    hazard_category_5m: HazardCategory5M | None = None
    hazard_category_icao: HazardCategoryICAO | None = None
    risk_matrix_applied: RiskMatrixApplied = RiskMatrixApplied.FAA_5X5
    existing_controls: str | None = None
    residual_risk_level: RiskLevel | None = None
    record_status: RecordStatus = RecordStatus.OPEN
    validation_status: ValidationStatus = ValidationStatus.PENDING
    source: RecordSource = RecordSource.MANUAL_ENTRY
    acm_cross_reference: str | None = None


class UpdateRiskEntryRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    hazard: str | None = Field(default=None, min_length=1)
    severity: Severity | None = None
    likelihood: Likelihood | None = None
    status: RiskStatus | None = None
    notes: str | None = None

    airport_identifier: str | None = Field(default=None, max_length=20)
    potential_credible_outcome: str | None = None
    operational_domain: OperationalDomain | None = None
    sub_location: str | None = Field(default=None, max_length=255)
    hazard_category_5m: HazardCategory5M | None = None
    hazard_category_icao: HazardCategoryICAO | None = None
    risk_matrix_applied: RiskMatrixApplied | None = None
    existing_controls: str | None = None
    residual_risk_level: RiskLevel | None = None
    record_status: RecordStatus | None = None
    validation_status: ValidationStatus | None = None
    acm_cross_reference: str | None = None


class MitigationResponse(BaseModel):
    id: uuid.UUID
    risk_entry_id: uuid.UUID
    title: str
    description: str
    assignee: str | None
    due_date: datetime | None
    verification_method: str | None
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

    airport_identifier: str | None
    potential_credible_outcome: str | None
    operational_domain: OperationalDomain | None
    sub_location: str | None
    hazard_category_5m: HazardCategory5M | None
    hazard_category_icao: HazardCategoryICAO | None
    risk_matrix_applied: RiskMatrixApplied
    existing_controls: str | None
    residual_risk_level: RiskLevel | None
    record_status: RecordStatus
    validation_status: ValidationStatus
    source: RecordSource
    sync_status: SyncStatus
    acm_cross_reference: str | None

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
    airport_identifier: str | None
    operational_domain: OperationalDomain | None
    hazard_category_5m: HazardCategory5M | None
    record_status: RecordStatus
    validation_status: ValidationStatus
    source: RecordSource
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Mitigation Schemas ---


class CreateMitigationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = None
    verification_method: str | None = None


class UpdateMitigationRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, min_length=1)
    assignee: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = None
    verification_method: str | None = None
    status: MitigationStatus | None = None


# --- Airport Sub-Location Schemas (Sub-Prompt 4 §Step 3a library) ---


class SubLocationResponse(BaseModel):
    id: uuid.UUID
    airport_identifier: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateSubLocationRequest(BaseModel):
    airport_identifier: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
