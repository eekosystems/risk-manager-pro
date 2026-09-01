import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_correlation_id,
    get_current_organization,
    require_any_member,
    require_platform_admin,
)
from app.core.rate_limit import limiter
from app.models.feedback import FeedbackStatus
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.feedback import (
    CreateGuidanceRequest,
    FeedbackResponse,
    FeedbackReviewItem,
    GuidanceResponse,
    PromoteFeedbackRequest,
    ReviewFeedbackRequest,
    SubmitFeedbackRequest,
    UpdateGuidanceRequest,
)
from app.services.audit import AuditLogger
from app.services.feedback import FeedbackService, GuidanceService

router = APIRouter(prefix="/feedback", tags=["feedback"])
guidance_router = APIRouter(prefix="/guidance", tags=["guidance"])

# How much of the reviewed output to show in the queue. Enough to judge the
# feedback against, without shipping whole transcripts into a list view.
MESSAGE_EXCERPT_CHARS = 1200


def _get_feedback_service(db: AsyncSession = Depends(get_db)) -> FeedbackService:
    return FeedbackService(db=db)


def _get_guidance_service(db: AsyncSession = Depends(get_db)) -> GuidanceService:
    return GuidanceService(db=db)


# ── Submission: any member, on their own organization's outputs ───────────


@router.post("", response_model=DataResponse[FeedbackResponse], status_code=201)
@limiter.limit("30/minute")
async def submit_feedback(
    request: Request,
    payload: SubmitFeedbackRequest,
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: FeedbackService = Depends(_get_feedback_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[FeedbackResponse]:
    feedback = await service.submit(
        organization_id=organization.id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        submitted_by=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    await audit.log(
        action="feedback.submitted",
        user=current_user,
        resource_type="message_feedback",
        resource_id=str(feedback.id),
        organization_id=organization.id,
        metadata={"rating": feedback.rating.value},
    )
    return DataResponse(
        data=FeedbackResponse.model_validate(feedback),
        meta=MetaResponse(request_id=correlation_id),
    )


# ── Curation: platform admins only ───────────────────────────────────────


@router.get("", response_model=PaginatedResponse[FeedbackReviewItem])
async def list_feedback(
    status: FeedbackStatus | None = Query(None),
    organization_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _current_user: User = Depends(require_platform_admin),
    service: FeedbackService = Depends(_get_feedback_service),
    correlation_id: str = Depends(get_correlation_id),
) -> PaginatedResponse[FeedbackReviewItem]:
    rows, total = await service.list_for_review(
        status=status, organization_id=organization_id, skip=skip, limit=limit
    )

    messages, submitters = await service.load_context_for(rows)
    items = [
        FeedbackReviewItem(
            id=row.id,
            organization_id=row.organization_id,
            conversation_id=row.conversation_id,
            message_id=row.message_id,
            rating=row.rating,
            status=row.status,
            comment=row.comment,
            submitted_by=row.submitted_by,
            submitter_name=submitters.get(row.submitted_by, "Unknown user"),
            message_excerpt=messages.get(row.message_id, "")[:MESSAGE_EXCERPT_CHARS],
            review_note=row.review_note,
            reviewed_at=row.reviewed_at,
            created_at=row.created_at,
        )
        for row in rows
    ]

    page_size = limit or 1
    return PaginatedResponse(
        data=items,
        meta=PaginatedMeta(
            request_id=correlation_id,
            total=total,
            page=(skip // page_size) + 1,
            page_size=limit,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.patch("/{feedback_id}", response_model=DataResponse[FeedbackResponse])
async def review_feedback(
    feedback_id: uuid.UUID,
    payload: ReviewFeedbackRequest,
    current_user: User = Depends(require_platform_admin),
    service: FeedbackService = Depends(_get_feedback_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[FeedbackResponse]:
    feedback = await service.set_status(
        feedback_id,
        payload.status,
        reviewed_by=current_user.id,
        review_note=payload.review_note,
    )
    await audit.log(
        action="feedback.reviewed",
        user=current_user,
        resource_type="message_feedback",
        resource_id=str(feedback_id),
        organization_id=feedback.organization_id,
        metadata={"status": feedback.status.value},
    )
    return DataResponse(
        data=FeedbackResponse.model_validate(feedback),
        meta=MetaResponse(request_id=correlation_id),
    )


@router.post(
    "/{feedback_id}/promote",
    response_model=DataResponse[GuidanceResponse],
    status_code=201,
)
async def promote_feedback(
    feedback_id: uuid.UUID,
    payload: PromoteFeedbackRequest,
    current_user: User = Depends(require_platform_admin),
    service: FeedbackService = Depends(_get_feedback_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[GuidanceResponse]:
    """Promote feedback into a guidance rule that shapes every future answer."""
    guidance = await service.promote(
        feedback_id=feedback_id,
        content=payload.content,
        scope=payload.scope,
        created_by=current_user.id,
        function_type=payload.function_type,
    )
    await audit.log(
        action="guidance.promoted",
        user=current_user,
        resource_type="application_guidance",
        resource_id=str(guidance.id),
        organization_id=guidance.organization_id,
        metadata={
            "source_feedback_id": str(feedback_id),
            "scope": guidance.scope.value,
            "function_type": guidance.function_type.value if guidance.function_type else "all",
        },
    )
    return DataResponse(
        data=GuidanceResponse.model_validate(guidance),
        meta=MetaResponse(request_id=correlation_id),
    )


# ── Guidance store: platform admins only ─────────────────────────────────


@guidance_router.get("", response_model=DataResponse[list[GuidanceResponse]])
async def list_guidance(
    include_inactive: bool = Query(True),
    _current_user: User = Depends(require_platform_admin),
    service: GuidanceService = Depends(_get_guidance_service),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[list[GuidanceResponse]]:
    rules = await service.list_all(include_inactive=include_inactive)
    return DataResponse(
        data=[GuidanceResponse.model_validate(r) for r in rules],
        meta=MetaResponse(request_id=correlation_id),
    )


@guidance_router.post("", response_model=DataResponse[GuidanceResponse], status_code=201)
async def create_guidance(
    payload: CreateGuidanceRequest,
    current_user: User = Depends(require_platform_admin),
    service: GuidanceService = Depends(_get_guidance_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[GuidanceResponse]:
    guidance = await service.create(
        content=payload.content,
        scope=payload.scope,
        created_by=current_user.id,
        organization_id=payload.organization_id,
        function_type=payload.function_type,
    )
    await audit.log(
        action="guidance.created",
        user=current_user,
        resource_type="application_guidance",
        resource_id=str(guidance.id),
        organization_id=guidance.organization_id,
        metadata={"scope": guidance.scope.value},
    )
    return DataResponse(
        data=GuidanceResponse.model_validate(guidance),
        meta=MetaResponse(request_id=correlation_id),
    )


@guidance_router.patch("/{guidance_id}", response_model=DataResponse[GuidanceResponse])
async def update_guidance(
    guidance_id: uuid.UUID,
    payload: UpdateGuidanceRequest,
    current_user: User = Depends(require_platform_admin),
    service: GuidanceService = Depends(_get_guidance_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[GuidanceResponse]:
    guidance = await service.update(
        guidance_id,
        content=payload.content,
        is_active=payload.is_active,
        function_type=payload.function_type,
        clear_function_type=payload.applies_to_all_functions,
    )
    await audit.log(
        action="guidance.updated",
        user=current_user,
        resource_type="application_guidance",
        resource_id=str(guidance_id),
        organization_id=guidance.organization_id,
        metadata={"is_active": guidance.is_active},
    )
    return DataResponse(
        data=GuidanceResponse.model_validate(guidance),
        meta=MetaResponse(request_id=correlation_id),
    )


@guidance_router.delete("/{guidance_id}", status_code=204)
async def delete_guidance(
    guidance_id: uuid.UUID,
    current_user: User = Depends(require_platform_admin),
    service: GuidanceService = Depends(_get_guidance_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete(guidance_id)
    await audit.log(
        action="guidance.deleted",
        user=current_user,
        resource_type="application_guidance",
        resource_id=str(guidance_id),
    )
