import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.organization import OrganizationStatus
from app.models.organization_membership import MembershipRole


class CreateOrganizationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    is_platform: bool = False


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: OrganizationStatus | None = None
    settings_json: dict[str, Any] | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: OrganizationStatus
    is_platform: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: OrganizationStatus
    is_platform: bool

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID | None = None
    email: str | None = None
    role: MembershipRole = MembershipRole.VIEWER

    @model_validator(mode="after")
    def _require_user_id_or_email(self) -> "AddMemberRequest":
        if not self.user_id and not self.email:
            raise ValueError("At least one of 'user_id' or 'email' must be provided")
        return self


class UpdateMemberRoleRequest(BaseModel):
    role: MembershipRole


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: MembershipRole
    is_active: bool
    email: str
    display_name: str
    invitation_status: str = "active"
    created_at: datetime

    model_config = {"from_attributes": True}
