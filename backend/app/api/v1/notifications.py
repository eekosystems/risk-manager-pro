import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_organization, get_current_user
from app.core.exceptions import NotFoundError
from app.models.organization import Organization
from app.models.user import User
from app.models.user_notification_preference import UserNotificationPreference
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notification import NotificationService
from app.services.preference_tokens import verify_preference_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db=db)


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: NotificationService = Depends(_get_notification_service),
) -> PaginatedResponse[NotificationResponse]:
    entries, total = await service.list_notifications(
        user_id=current_user.id,
        organization_id=organization.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    total_pages = (total + limit - 1) // limit
    return PaginatedResponse(
        data=entries,
        meta=PaginatedMeta(
            request_id="",
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/unread-count", response_model=DataResponse[UnreadCountResponse])
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: NotificationService = Depends(_get_notification_service),
) -> DataResponse[UnreadCountResponse]:
    count = await service.get_unread_count(current_user.id, organization.id)
    return DataResponse(
        data=UnreadCountResponse(count=count),
        meta=MetaResponse(request_id=""),
    )


@router.patch("/{notification_id}/read", response_model=DataResponse[NotificationResponse])
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(_get_notification_service),
) -> DataResponse[NotificationResponse]:
    entry = await service.mark_read(notification_id, current_user.id)
    if not entry:
        raise NotFoundError("Notification", str(notification_id))
    return DataResponse(data=entry, meta=MetaResponse(request_id=str(notification_id)))


@router.post("/mark-all-read", status_code=204)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: NotificationService = Depends(_get_notification_service),
) -> None:
    await service.mark_all_read(current_user.id, organization.id)


# --- Email preference management (token-authenticated, no login required) ---


class PreferenceResponse(BaseModel):
    email_opt_out: bool


class UpdatePreferenceRequest(BaseModel):
    email_opt_out: bool


async def _resolve_token(token: str) -> uuid.UUID:
    user_id = verify_preference_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}},
        )
    return user_id


@router.get(
    "/preferences/{token}",
    response_model=DataResponse[PreferenceResponse],
)
async def get_email_preference(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> DataResponse[PreferenceResponse]:
    user_id = await _resolve_token(token)
    row = (
        await db.execute(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    return DataResponse(
        data=PreferenceResponse(email_opt_out=bool(row and row.email_opt_out)),
        meta=MetaResponse(request_id=""),
    )


@router.post(
    "/preferences/{token}",
    response_model=DataResponse[PreferenceResponse],
)
async def update_email_preference(
    token: str,
    payload: UpdatePreferenceRequest,
    db: AsyncSession = Depends(get_db),
) -> DataResponse[PreferenceResponse]:
    user_id = await _resolve_token(token)
    row = (
        await db.execute(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserNotificationPreference(user_id=user_id, email_opt_out=payload.email_opt_out)
        db.add(row)
    else:
        row.email_opt_out = payload.email_opt_out
    await db.commit()
    return DataResponse(
        data=PreferenceResponse(email_opt_out=row.email_opt_out),
        meta=MetaResponse(request_id=""),
    )
