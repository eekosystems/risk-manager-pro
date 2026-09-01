import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import FunctionType
from app.models.feedback import FeedbackRating, FeedbackStatus, MessageFeedback
from app.models.guidance import ApplicationGuidance, GuidanceScope
from app.models.message import Message
from app.models.user import User


class FeedbackRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        submitted_by: uuid.UUID,
        rating: FeedbackRating,
        comment: str,
    ) -> MessageFeedback:
        feedback = MessageFeedback(
            organization_id=organization_id,
            conversation_id=conversation_id,
            message_id=message_id,
            submitted_by=submitted_by,
            rating=rating,
            comment=comment,
        )
        self._db.add(feedback)
        await self._db.flush()
        return feedback

    async def get_by_id(self, feedback_id: uuid.UUID) -> MessageFeedback | None:
        """Fetch across tenants — platform admins curate feedback org-wide."""
        stmt = select(MessageFeedback).where(MessageFeedback.id == feedback_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_review(
        self,
        status: FeedbackStatus | None = None,
        organization_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[MessageFeedback], int]:
        filters = []
        if status is not None:
            filters.append(MessageFeedback.status == status)
        if organization_id is not None:
            filters.append(MessageFeedback.organization_id == organization_id)

        count_stmt = select(func.count()).select_from(MessageFeedback)
        stmt = select(MessageFeedback)
        for condition in filters:
            count_stmt = count_stmt.where(condition)
            stmt = stmt.where(condition)

        total = (await self._db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(MessageFeedback.created_at.desc()).offset(skip).limit(limit)
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows, int(total)

    async def get_message(self, message_id: uuid.UUID) -> Message | None:
        stmt = select(Message).where(Message.id == message_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def load_context_for(
        self, rows: list[MessageFeedback]
    ) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
        """Batch-fetch message bodies and submitter names for a page of feedback.

        Fetched in two queries rather than two per row, so the review queue
        does not issue a hundred round trips to render fifty entries.
        """
        if not rows:
            return {}, {}

        message_ids = {r.message_id for r in rows}
        user_ids = {r.submitted_by for r in rows}

        message_rows = (
            await self._db.execute(
                select(Message.id, Message.content).where(Message.id.in_(message_ids))
            )
        ).all()
        user_rows = (
            await self._db.execute(
                select(User.id, User.display_name).where(User.id.in_(user_ids))
            )
        ).all()

        return (
            {mid: content for mid, content in message_rows},
            {uid: name for uid, name in user_rows},
        )

    async def get_submitter(self, feedback: MessageFeedback) -> User | None:
        stmt = select(User).where(User.id == feedback.submitted_by)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_status(
        self,
        feedback: MessageFeedback,
        status: FeedbackStatus,
        reviewed_by: uuid.UUID,
        review_note: str | None = None,
    ) -> MessageFeedback:
        feedback.status = status
        feedback.reviewed_by = reviewed_by
        feedback.reviewed_at = datetime.utcnow()
        if review_note is not None:
            feedback.review_note = review_note
        await self._db.flush()
        return feedback


class GuidanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        scope: GuidanceScope,
        content: str,
        created_by: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        function_type: FunctionType | None = None,
        source_feedback_id: uuid.UUID | None = None,
    ) -> ApplicationGuidance:
        guidance = ApplicationGuidance(
            scope=scope,
            organization_id=organization_id,
            function_type=function_type,
            content=content,
            source_feedback_id=source_feedback_id,
            created_by=created_by,
        )
        self._db.add(guidance)
        await self._db.flush()
        return guidance

    async def get_by_id(self, guidance_id: uuid.UUID) -> ApplicationGuidance | None:
        stmt = select(ApplicationGuidance).where(ApplicationGuidance.id == guidance_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, include_inactive: bool = True
    ) -> list[ApplicationGuidance]:
        stmt = select(ApplicationGuidance)
        if not include_inactive:
            stmt = stmt.where(ApplicationGuidance.is_active.is_(True))
        stmt = stmt.order_by(ApplicationGuidance.created_at.desc())
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_active_for(
        self, organization_id: uuid.UUID, function_type: FunctionType
    ) -> list[ApplicationGuidance]:
        """Active rules that apply to this organization and function type.

        Matches global rules plus the organization's own, and within each,
        rules pinned to this function type plus those that apply to all.
        """
        stmt = (
            select(ApplicationGuidance)
            .where(
                ApplicationGuidance.is_active.is_(True),
                or_(
                    ApplicationGuidance.scope == GuidanceScope.GLOBAL,
                    ApplicationGuidance.organization_id == organization_id,
                ),
                or_(
                    ApplicationGuidance.function_type.is_(None),
                    ApplicationGuidance.function_type == function_type,
                ),
            )
            # Global rules first so an organization's own rule reads as the
            # more specific instruction when the two overlap.
            .order_by(
                ApplicationGuidance.scope.desc(),
                ApplicationGuidance.created_at.asc(),
            )
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def update(
        self,
        guidance: ApplicationGuidance,
        content: str | None = None,
        is_active: bool | None = None,
        function_type: FunctionType | None = None,
        clear_function_type: bool = False,
    ) -> ApplicationGuidance:
        if content is not None:
            guidance.content = content
        if is_active is not None:
            guidance.is_active = is_active
        if clear_function_type:
            guidance.function_type = None
        elif function_type is not None:
            guidance.function_type = function_type
        await self._db.flush()
        return guidance

    async def delete(self, guidance: ApplicationGuidance) -> None:
        await self._db.delete(guidance)
        await self._db.flush()
