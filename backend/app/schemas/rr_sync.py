"""Pydantic schemas for RR dual-instance sync + ACP + closure approvals."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.rr_sync import (
    ACPDecision,
    ACPIntelligenceSource,
    ClosureApprovalStatus,
    PendingChangeDirection,
    PendingChangeStatus,
    PendingChangeType,
)

# --- Pending sync changes ---


class PendingSyncChangeResponse(BaseModel):
    id: uuid.UUID
    link_id: uuid.UUID | None
    source_risk_entry_id: uuid.UUID
    source_organization_id: uuid.UUID
    target_organization_id: uuid.UUID
    change_type: PendingChangeType
    direction: PendingChangeDirection
    status: PendingChangeStatus
    diff_json: dict[str, Any]
    initiator_user_id: uuid.UUID
    reviewer_user_id: uuid.UUID | None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


# --- Airport Context Profile ---


class ACPResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    airport_identifier: str
    system_profile: str | None
    known_risk_factors: str | None
    stakeholder_notes: str | None
    operational_impact_history: str | None
    extra_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateACPRequest(BaseModel):
    system_profile: str | None = None
    known_risk_factors: str | None = None
    stakeholder_notes: str | None = None
    operational_impact_history: str | None = None
    extra_json: dict[str, Any] | None = None


class ACPIntelligenceItemResponse(BaseModel):
    id: uuid.UUID
    acp_id: uuid.UUID
    airport_identifier: str
    source: ACPIntelligenceSource
    headline: str
    summary: str | None
    occurred_at: datetime | None
    external_url: str | None
    external_ref: str | None
    decision: ACPDecision
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
    linked_risk_entry_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateACPIntelligenceItemRequest(BaseModel):
    airport_identifier: str = Field(..., min_length=1, max_length=20)
    source: ACPIntelligenceSource
    headline: str = Field(..., min_length=1, max_length=500)
    summary: str | None = None
    occurred_at: datetime | None = None
    external_url: str | None = Field(default=None, max_length=1000)
    external_ref: str | None = Field(default=None, max_length=255)
    raw_payload: dict[str, Any] | None = None


class ACPItemDecisionRequest(BaseModel):
    decision: ACPDecision
    note: str | None = Field(default=None, max_length=2000)
    linked_risk_entry_id: uuid.UUID | None = None


# --- Closure approvals ---


class ClosureApprovalResponse(BaseModel):
    id: uuid.UUID
    risk_entry_id: uuid.UUID
    requested_by: uuid.UUID
    request_note: str | None
    status: ClosureApprovalStatus
    approver_user_id: uuid.UUID | None
    approval_note: str | None
    requested_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class RequestClosureRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ClosureDecisionRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


# --- FG portfolio view ---


class PortfolioRiskRow(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    airport_identifier: str | None
    title: str
    hazard: str
    severity: int
    likelihood: str
    risk_level: str
    record_status: str
    validation_status: str
    source: str
    created_at: datetime
    updated_at: datetime
