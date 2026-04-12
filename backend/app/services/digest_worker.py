import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.notification import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDeliveryLog,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.settings import DigestFrequency, QaqcSettingsPayload
from app.services.email import get_email_service
from app.services.email_templates import DigestItem, render_digest
from app.services.preference_tokens import issue_preference_token
from app.services.settings import SettingsService

logger = structlog.get_logger(__name__)

_CHECK_INTERVAL_SECONDS = 900  # 15 minutes


async def run_digest_worker(stop_event: asyncio.Event) -> None:
    """Long-running task that sends QA/QC digest emails at configured hours."""
    if not settings.qaqc_digest_enabled:
        logger.info("digest_worker_disabled")
        return

    logger.info("digest_worker_started", interval_seconds=_CHECK_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            await _run_cycle()
        except Exception:  # noqa: BLE001
            logger.error("digest_worker_cycle_failed", exc_info=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_CHECK_INTERVAL_SECONDS)
        except TimeoutError:
            continue
    logger.info("digest_worker_stopped")


async def _run_cycle() -> None:
    now = datetime.now(UTC)
    async with async_session_factory() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        for org in orgs:
            settings_svc = SettingsService(db=session)
            config = await settings_svc.get_effective_qaqc_config(org.id)
            if config.digest_frequency == DigestFrequency.IMMEDIATE:
                continue
            if not _is_due(config, now):
                continue
            period_label = (
                "Daily" if config.digest_frequency == DigestFrequency.DAILY else "Weekly"
            )
            await _send_digests_for_org(session, org.id, config, period_label)


def _is_due(config: QaqcSettingsPayload, now: datetime) -> bool:
    if now.hour != config.digest_send_hour_utc:
        return False
    if config.digest_frequency == DigestFrequency.WEEKLY:
        return now.weekday() == 0  # Monday
    return True


async def _send_digests_for_org(
    session: AsyncSession,
    organization_id: uuid.UUID,
    config: QaqcSettingsPayload,
    period_label: str,
) -> None:
    reviewer_ids = [
        uuid.UUID(uid) if isinstance(uid, str) else uid for uid in config.reviewer_user_ids
    ]
    if not reviewer_ids:
        return

    pending_rows = await session.execute(
        select(NotificationDeliveryLog, Notification)
        .join(Notification, Notification.id == NotificationDeliveryLog.notification_id)
        .where(
            NotificationDeliveryLog.status == DeliveryStatus.PENDING,
            NotificationDeliveryLog.channel == DeliveryChannel.EMAIL,
            Notification.organization_id == organization_id,
            Notification.recipient_user_id.in_(reviewer_ids),
        )
        .order_by(Notification.created_at.asc())
    )
    pairs = pending_rows.all()
    if not pairs:
        return

    by_user: dict[uuid.UUID, list[tuple[NotificationDeliveryLog, Notification]]] = {}
    for log, notification in pairs:
        by_user.setdefault(notification.recipient_user_id, []).append((log, notification))

    users_result = await session.execute(
        select(User).where(User.id.in_(list(by_user.keys())), User.is_active.is_(True))
    )
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    email_service = get_email_service()
    for user_id, rows in by_user.items():
        user = users_by_id.get(user_id)
        if user is None:
            for log, _ in rows:
                log.status = DeliveryStatus.SKIPPED
                log.error_message = "user_not_found"
            continue

        items = [
            DigestItem(
                notification_type=n.type,
                title=n.title,
                body=n.body,
                resource_type=n.resource_type,
                resource_id=n.resource_id,
                created_at=n.created_at,
            )
            for _, n in rows
        ]
        rendered = render_digest(
            items=items,
            period_label=period_label,
            preference_token=issue_preference_token(user.id),
        )
        success = await email_service.send(
            to=user.email,
            subject=rendered.subject,
            html=rendered.html,
            text_fallback=rendered.text,
        )
        for log, _ in rows:
            log.status = DeliveryStatus.SENT if success else DeliveryStatus.FAILED
            log.error_message = None if success else "digest_send_failed"

    await session.commit()
    logger.info(
        "digest_worker_sent",
        organization_id=str(organization_id),
        recipients=len(by_user),
        items=len(pairs),
        period=period_label,
    )
