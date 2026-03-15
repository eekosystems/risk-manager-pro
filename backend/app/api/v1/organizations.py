import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_user,
    get_graph_service,
    require_org_role,
    require_platform_admin,
)
from app.models.organization_membership import MembershipRole
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.organization import (
    AddMemberRequest,
    CreateOrganizationRequest,
    MemberResponse,
    OrganizationListItem,
    OrganizationResponse,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
)
from app.services.audit import AuditLogger
from app.services.microsoft_graph import MicrosoftGraphService
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _get_org_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db=db)


@router.post("", response_model=DataResponse[OrganizationResponse], status_code=201)
async def create_organization(
    payload: CreateOrganizationRequest,
    current_user: User = Depends(require_platform_admin),
    service: OrganizationService = Depends(_get_org_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[OrganizationResponse]:
    org = await service.create_organization(
        name=payload.name,
        slug=payload.slug,
        created_by=current_user.id,
        is_platform=payload.is_platform,
    )
    await audit.log(
        action="organization.created",
        user=current_user,
        resource_type="organization",
        resource_id=str(org.id),
        organization_id=org.id,
    )
    return DataResponse(
        data=OrganizationResponse.model_validate(org),
        meta=MetaResponse(request_id=str(org.id)),
    )


@router.get("", response_model=DataResponse[list[OrganizationListItem]])
async def list_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(_get_org_service),
) -> DataResponse[list[OrganizationListItem]]:
    orgs = await service.list_organizations(current_user, skip, limit)
    items = [OrganizationListItem.model_validate(o) for o in orgs]
    return DataResponse(data=items, meta=MetaResponse(request_id=""))


@router.get("/{org_id}", response_model=DataResponse[OrganizationResponse])
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(_get_org_service),
) -> DataResponse[OrganizationResponse]:
    org = await service.get_organization_with_access_check(org_id, current_user)
    return DataResponse(
        data=OrganizationResponse.model_validate(org),
        meta=MetaResponse(request_id=str(org_id)),
    )


@router.patch("/{org_id}", response_model=DataResponse[OrganizationResponse])
async def update_organization(
    org_id: uuid.UUID,
    payload: UpdateOrganizationRequest,
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    service: OrganizationService = Depends(_get_org_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[OrganizationResponse]:
    org = await service.update_organization(
        org_id=org_id,
        name=payload.name,
        status=payload.status,
        settings_json=payload.settings_json,
    )
    await audit.log(
        action="organization.updated",
        user=current_user,
        resource_type="organization",
        resource_id=str(org_id),
        organization_id=org_id,
    )
    return DataResponse(
        data=OrganizationResponse.model_validate(org),
        meta=MetaResponse(request_id=str(org_id)),
    )


@router.post(
    "/{org_id}/members",
    response_model=DataResponse[MemberResponse],
    status_code=201,
)
async def add_member(
    org_id: uuid.UUID,
    payload: AddMemberRequest,
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    service: OrganizationService = Depends(_get_org_service),
    graph: MicrosoftGraphService = Depends(get_graph_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[MemberResponse]:
    member_resp = await service.add_member_and_build_response(
        organization_id=org_id,
        role=payload.role,
        invited_by=current_user.id,
        user_id=payload.user_id,
        email=payload.email,
        graph_service=graph,
    )
    await audit.log(
        action="organization.member_added",
        user=current_user,
        resource_type="membership",
        resource_id=str(member_resp.id),
        organization_id=org_id,
        metadata={"invitation_status": member_resp.invitation_status},
    )
    return DataResponse(
        data=member_resp,
        meta=MetaResponse(request_id=str(member_resp.id)),
    )


@router.get("/{org_id}/members", response_model=DataResponse[list[MemberResponse]])
async def list_members(
    org_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(_get_org_service),
) -> DataResponse[list[MemberResponse]]:
    await service.verify_membership_or_admin(org_id, current_user)
    items = await service.list_members_response(org_id, skip, limit)
    return DataResponse(data=items, meta=MetaResponse(request_id=""))


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=DataResponse[MemberResponse],
)
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    service: OrganizationService = Depends(_get_org_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[MemberResponse]:
    member_resp = await service.update_member_role_and_build_response(org_id, user_id, payload.role)
    await audit.log(
        action="organization.member_role_updated",
        user=current_user,
        resource_type="membership",
        resource_id=str(member_resp.id),
        organization_id=org_id,
    )
    return DataResponse(
        data=member_resp,
        meta=MetaResponse(request_id=str(member_resp.id)),
    )


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    service: OrganizationService = Depends(_get_org_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.remove_member(org_id, user_id)
    await audit.log(
        action="organization.member_removed",
        user=current_user,
        resource_type="membership",
        resource_id=str(user_id),
        organization_id=org_id,
    )
