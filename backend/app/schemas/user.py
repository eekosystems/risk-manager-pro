import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.organization_membership import MembershipRole


class UserOrgMembership(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    role: MembershipRole
    is_active: bool

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool
    is_active: bool

    model_config = {"from_attributes": True}


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    organizations: list[UserOrgMembership] = []

    model_config = {"from_attributes": True}
