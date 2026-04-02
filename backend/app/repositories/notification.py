import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_batch(self, notifications: list[Notification]) -> None:
        self._db.add_all(notifications)
        await self._db.flush()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Notification], int]:
        base = select(Notification).where(
            Notification.recipient_user_id == user_id,
            Notification.organization_id == organization_id,
        )
        count_base = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.organization_id == organization_id,
            )
        )

        if unread_only:
            base = base.where(Notification.is_read.is_(False))
            count_base = count_base.where(Notification.is_read.is_(False))

        count_result = await self._db.execute(count_base)
        total = count_result.scalar_one()

        stmt = base.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_unread(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.organization_id == organization_id,
                Notification.is_read.is_(False),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def mark_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
        result = await self._db.execute(stmt)
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_read = True
            await self._db.flush()
        return notification

    async def mark_all_read(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> int:
        stmt = (
            update(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.organization_id == organization_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        result = await self._db.execute(stmt)
        await self._db.flush()
        return result.rowcount  # type: ignore[return-value]
