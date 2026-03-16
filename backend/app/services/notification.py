import asyncio
import uuid

import structlog
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import async_session_factory
from app.core.tasks import track_task
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationResponse
from app.schemas.settings import QaqcSettingsPayload
from app.services.settings import SettingsService

logger = structlog.get_logger(__name__)


class NotificationService:
    def __init__(self, db: object) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        self._repo = NotificationRepository(db)  # type: ignore[arg-type]

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[NotificationResponse], int]:
        entries, total = await self._repo.list_for_user(
            user_id, organization_id, unread_only, skip, limit
        )
        return [NotificationResponse.model_validate(e) for e in entries], total

    async def get_unread_count(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> int:
        return await self._repo.count_unread(user_id, organization_id)

    async def mark_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationResponse | None:
        entry = await self._repo.mark_read(notification_id, user_id)
        if entry:
            return NotificationResponse.model_validate(entry)
        return None

    async def mark_all_read(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> int:
        return await self._repo.mark_all_read(user_id, organization_id)


class NotificationDispatcher:
    """Fire-and-forget QA/QC notification dispatcher (non-blocking)."""

    def dispatch(
        self,
        organization_id: uuid.UUID,
        triggered_by: User,
        notification_type: NotificationType,
        title: str,
        body: str,
        resource_type: str,
        resource_id: str | None,
    ) -> None:
        task = asyncio.create_task(
            _dispatch_qaqc_notifications(
                organization_id=organization_id,
                triggered_by_user_id=triggered_by.id,
                notification_type=notification_type,
                title=title,
                body=body[:500],
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )
        track_task(task)


async def _dispatch_qaqc_notifications(
    organization_id: uuid.UUID,
    triggered_by_user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    body: str,
    resource_type: str,
    resource_id: str | None,
) -> None:
    try:
        async with async_session_factory() as session:
            settings_svc = SettingsService(db=session)
            config = await settings_svc.get_effective_qaqc_config(organization_id)

            if not _should_notify(config, notification_type):
                return

            reviewer_ids = [
                uid for uid in config.reviewer_user_ids
                if uid != triggered_by_user_id
            ]
            if not reviewer_ids:
                return

            repo = NotificationRepository(session)
            notifications = [
                Notification(
                    organization_id=organization_id,
                    recipient_user_id=uid,
                    triggered_by_user_id=triggered_by_user_id,
                    type=notification_type,
                    title=title,
                    body=body,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
                for uid in reviewer_ids
            ]
            await repo.create_batch(notifications)
            await session.commit()

            logger.info(
                "qaqc_notifications_dispatched",
                count=len(notifications),
                type=notification_type,
                organization_id=str(organization_id),
            )
    except SQLAlchemyError:
        logger.error(
            "qaqc_notification_dispatch_failed",
            notification_type=notification_type,
            organization_id=str(organization_id),
            exc_info=True,
        )


def _should_notify(config: QaqcSettingsPayload, notification_type: NotificationType) -> bool:
    if notification_type == NotificationType.CHAT_RESPONSE:
        return config.notify_on_chat
    if notification_type == NotificationType.RISK_CREATED:
        return config.notify_on_risk_created
    return False
