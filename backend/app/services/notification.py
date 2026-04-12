import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import async_session_factory
from app.core.tasks import track_task
from app.models.notification import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDeliveryLog,
    NotificationType,
)
from app.models.user import User
from app.models.user_notification_preference import UserNotificationPreference
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationResponse
from app.schemas.settings import DeliveryMode, DigestFrequency, QaqcSettingsPayload
from app.services.email import get_email_service
from app.services.email_templates import render_notification
from app.services.preference_tokens import issue_preference_token
from app.services.settings import SettingsService

logger = structlog.get_logger(__name__)


class NotificationService:
    def __init__(self, db: object) -> None:
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

    async def get_unread_count(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> int:
        return await self._repo.count_unread(user_id, organization_id)

    async def mark_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationResponse | None:
        entry = await self._repo.mark_read(notification_id, user_id)
        if entry:
            return NotificationResponse.model_validate(entry)
        return None

    async def mark_all_read(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> int:
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
                triggered_by_display_name=triggered_by.display_name,
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
    triggered_by_display_name: str,
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
                uuid.UUID(uid) if isinstance(uid, str) else uid
                for uid in config.reviewer_user_ids
            ]
            reviewer_ids = [uid for uid in reviewer_ids if uid != triggered_by_user_id]
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

            send_email = config.delivery_mode in (DeliveryMode.EMAIL, DeliveryMode.BOTH)
            immediate = config.digest_frequency == DigestFrequency.IMMEDIATE

            if send_email:
                recipient_rows = await session.execute(
                    select(User).where(User.id.in_(reviewer_ids), User.is_active.is_(True))
                )
                users_by_id = {u.id: u for u in recipient_rows.scalars().all()}
                pref_rows = await session.execute(
                    select(UserNotificationPreference).where(
                        UserNotificationPreference.user_id.in_(reviewer_ids)
                    )
                )
                opt_outs = {p.user_id for p in pref_rows.scalars().all() if p.email_opt_out}
                for notification in notifications:
                    user = users_by_id.get(notification.recipient_user_id)
                    if user is None:
                        session.add(
                            NotificationDeliveryLog(
                                notification_id=notification.id,
                                channel=DeliveryChannel.EMAIL,
                                status=DeliveryStatus.SKIPPED,
                                error_message="user_not_found",
                            )
                        )
                        continue
                    if user.id in opt_outs:
                        session.add(
                            NotificationDeliveryLog(
                                notification_id=notification.id,
                                channel=DeliveryChannel.EMAIL,
                                status=DeliveryStatus.SKIPPED,
                                error_message="user_opted_out",
                            )
                        )
                        continue
                    if immediate:
                        await _send_immediate_email(
                            session=session,
                            notification=notification,
                            user=user,
                            triggered_by_display_name=triggered_by_display_name,
                        )
                    else:
                        session.add(
                            NotificationDeliveryLog(
                                notification_id=notification.id,
                                channel=DeliveryChannel.EMAIL,
                                status=DeliveryStatus.PENDING,
                            )
                        )

            await session.commit()

            logger.info(
                "qaqc_notifications_dispatched",
                count=len(notifications),
                type=notification_type,
                delivery_mode=config.delivery_mode,
                digest_frequency=config.digest_frequency,
                organization_id=str(organization_id),
            )
    except SQLAlchemyError:
        logger.error(
            "qaqc_notification_dispatch_failed",
            notification_type=notification_type,
            organization_id=str(organization_id),
            exc_info=True,
        )


async def _send_immediate_email(
    *,
    session: object,
    notification: Notification,
    user: User,
    triggered_by_display_name: str,
) -> None:
    token = issue_preference_token(user.id)
    rendered = render_notification(
        notification_type=notification.type,
        title=notification.title,
        body=notification.body,
        resource_type=notification.resource_type,
        resource_id=notification.resource_id,
        triggered_by_name=triggered_by_display_name,
        preference_token=token,
    )
    email_service = get_email_service()
    success = await email_service.send(
        to=user.email,
        subject=rendered.subject,
        html=rendered.html,
        text_fallback=rendered.text,
    )
    session.add(  # type: ignore[attr-defined]
        NotificationDeliveryLog(
            notification_id=notification.id,
            channel=DeliveryChannel.EMAIL,
            status=DeliveryStatus.SENT if success else DeliveryStatus.FAILED,
            error_message=None if success else "acs_send_failed",
        )
    )


def _should_notify(config: QaqcSettingsPayload, notification_type: NotificationType) -> bool:
    if notification_type == NotificationType.CHAT_RESPONSE:
        return config.notify_on_chat
    if notification_type == NotificationType.RISK_CREATED:
        return config.notify_on_risk_created
    if notification_type == NotificationType.RISK_UPDATED:
        return config.notify_on_risk_updated
    if notification_type == NotificationType.MITIGATION_CREATED:
        return config.notify_on_mitigation_created
    if notification_type == NotificationType.DOCUMENT_INDEXED:
        return config.notify_on_document_indexed
    return False
