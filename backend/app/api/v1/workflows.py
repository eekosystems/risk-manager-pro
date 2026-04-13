import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    require_analyst_or_above,
    require_org_role,
)
from app.models.organization import Organization
from app.models.organization_membership import MembershipRole
from app.models.user import User
from app.models.workflow import WorkflowStatus, WorkflowType
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.workflow import (
    ApproveWorkflowRequest,
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowResponse,
)
from app.services.audit import AuditLogger
from app.services.workflow import WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _get_workflow_service(db: AsyncSession = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db=db)


@router.post("", response_model=DataResponse[WorkflowResponse], status_code=201)
async def create_workflow(
    payload: CreateWorkflowRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[WorkflowResponse]:
    workflow = await service.create(payload, current_user.id, organization.id)
    await audit.log(
        action=f"workflow.{payload.type.value}.created",
        user=current_user,
        resource_type="workflow",
        resource_id=str(workflow.id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=WorkflowResponse.model_validate(workflow),
        meta=MetaResponse(request_id=str(workflow.id)),
    )


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    type: WorkflowType | None = Query(None),
    status: WorkflowStatus | None = Query(None),
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
) -> PaginatedResponse[WorkflowResponse]:
    workflows, total = await service.list_for_org(
        organization_id=organization.id,
        type_filter=type,
        status_filter=status,
        skip=skip,
        limit=limit,
    )
    items = [WorkflowResponse.model_validate(w) for w in workflows]
    total_pages = (total + limit - 1) // limit if total else 0
    return PaginatedResponse(
        data=items,
        meta=PaginatedMeta(
            request_id="",
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/{workflow_id}", response_model=DataResponse[WorkflowResponse])
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
) -> DataResponse[WorkflowResponse]:
    workflow = await service.get(workflow_id, organization.id)
    return DataResponse(
        data=WorkflowResponse.model_validate(workflow),
        meta=MetaResponse(request_id=str(workflow_id)),
    )


@router.patch("/{workflow_id}", response_model=DataResponse[WorkflowResponse])
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: UpdateWorkflowRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[WorkflowResponse]:
    workflow = await service.update(workflow_id, organization.id, payload)
    await audit.log(
        action=f"workflow.{workflow.type.value}.updated",
        user=current_user,
        resource_type="workflow",
        resource_id=str(workflow_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=WorkflowResponse.model_validate(workflow),
        meta=MetaResponse(request_id=str(workflow_id)),
    )


@router.post("/{workflow_id}/submit", response_model=DataResponse[WorkflowResponse])
async def submit_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[WorkflowResponse]:
    workflow = await service.submit(workflow_id, organization.id)
    await audit.log(
        action=f"workflow.{workflow.type.value}.submitted",
        user=current_user,
        resource_type="workflow",
        resource_id=str(workflow_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=WorkflowResponse.model_validate(workflow),
        meta=MetaResponse(request_id=str(workflow_id)),
    )


@router.post("/{workflow_id}/approve", response_model=DataResponse[WorkflowResponse])
async def approve_workflow(
    workflow_id: uuid.UUID,
    payload: ApproveWorkflowRequest,
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[WorkflowResponse]:
    workflow = await service.approve(workflow_id, organization.id, current_user.id, payload.approve)
    await audit.log(
        action=f"workflow.{workflow.type.value}.{'approved' if payload.approve else 'rejected'}",
        user=current_user,
        resource_type="workflow",
        resource_id=str(workflow_id),
        organization_id=organization.id,
        metadata={"notes": payload.notes} if payload.notes else None,
    )
    return DataResponse(
        data=WorkflowResponse.model_validate(workflow),
        meta=MetaResponse(request_id=str(workflow_id)),
    )


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: WorkflowService = Depends(_get_workflow_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete(workflow_id, organization.id)
    await audit.log(
        action="workflow.deleted",
        user=current_user,
        resource_type="workflow",
        resource_id=str(workflow_id),
        organization_id=organization.id,
    )
