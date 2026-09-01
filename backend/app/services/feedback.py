import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.conversation import FunctionType
from app.models.feedback import FeedbackRating, FeedbackStatus, MessageFeedback
from app.models.guidance import ApplicationGuidance, GuidanceScope
from app.repositories.conversation import ConversationRepository
from app.repositories.feedback import FeedbackRepository, GuidanceRepository

logger = structlog.get_logger(__name__)

MAX_COMMENT_LENGTH = 5000
MAX_GUIDANCE_LENGTH = 2000

# Ceiling on what gets injected into any one request. Guidance competes with
# retrieved documents for the context window, so the store is allowed to grow
# past this while the prompt is not.
MAX_GUIDANCE_RULES_PER_REQUEST = 40


class GuidanceService:
    """The application's permanent memory: curated rules injected into the prompt."""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = GuidanceRepository(db)

    @staticmethod
    def _clean_content(content: str) -> str:
        cleaned = content.strip()
        if not cleaned:
            raise ValidationError("Guidance cannot be empty")
        if len(cleaned) > MAX_GUIDANCE_LENGTH:
            raise ValidationError(
                f"Guidance cannot exceed {MAX_GUIDANCE_LENGTH} characters. "
                "Keep each rule to a single instruction."
            )
        return cleaned

    async def create(
        self,
        content: str,
        scope: GuidanceScope,
        created_by: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        function_type: FunctionType | None = None,
        source_feedback_id: uuid.UUID | None = None,
    ) -> ApplicationGuidance:
        cleaned = self._clean_content(content)
        if scope is GuidanceScope.ORGANIZATION and organization_id is None:
            raise ValidationError("Organization-scoped guidance needs an organization")
        if scope is GuidanceScope.GLOBAL and organization_id is not None:
            raise ValidationError("Global guidance cannot be tied to an organization")

        return await self._repo.create(
            scope=scope,
            content=cleaned,
            created_by=created_by,
            organization_id=organization_id,
            function_type=function_type,
            source_feedback_id=source_feedback_id,
        )

    async def list_all(self, include_inactive: bool = True) -> list[ApplicationGuidance]:
        return await self._repo.list_all(include_inactive=include_inactive)

    async def update(
        self,
        guidance_id: uuid.UUID,
        content: str | None = None,
        is_active: bool | None = None,
        function_type: FunctionType | None = None,
        clear_function_type: bool = False,
    ) -> ApplicationGuidance:
        guidance = await self._repo.get_by_id(guidance_id)
        if guidance is None:
            raise NotFoundError("Guidance", str(guidance_id))
        cleaned = self._clean_content(content) if content is not None else None
        return await self._repo.update(
            guidance,
            content=cleaned,
            is_active=is_active,
            function_type=function_type,
            clear_function_type=clear_function_type,
        )

    async def delete(self, guidance_id: uuid.UUID) -> None:
        guidance = await self._repo.get_by_id(guidance_id)
        if guidance is None:
            raise NotFoundError("Guidance", str(guidance_id))
        await self._repo.delete(guidance)

    async def build_prompt_block(
        self, organization_id: uuid.UUID, function_type: FunctionType
    ) -> str:
        """Render the active guidance for this request as a system-prompt block.

        Returns an empty string when nothing applies, so the caller can skip
        adding a message entirely rather than send an empty instruction.
        """
        rules = await self._repo.list_active_for(organization_id, function_type)
        if not rules:
            return ""

        if len(rules) > MAX_GUIDANCE_RULES_PER_REQUEST:
            logger.warning(
                "guidance_truncated",
                organization_id=str(organization_id),
                function_type=function_type.value,
                total=len(rules),
                applied=MAX_GUIDANCE_RULES_PER_REQUEST,
            )
            rules = rules[:MAX_GUIDANCE_RULES_PER_REQUEST]

        lines = "\n".join(f"- {rule.content}" for rule in rules)
        return (
            "Learned guidance — corrections and preferences your reviewers have "
            "approved from user feedback on previous answers. Apply them to this "
            "response. They refine how you present and reason about an answer; "
            "they never license you to state a safety fact the retrieved context "
            "does not support.\n\n"
            f"{lines}"
        )


class FeedbackService:
    """Capture user feedback on outputs and curate it into application guidance."""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = FeedbackRepository(db)
        self._guidance = GuidanceService(db)
        self._conversations = ConversationRepository(db)

    @staticmethod
    def _clean_comment(comment: str) -> str:
        cleaned = comment.strip()
        if not cleaned:
            raise ValidationError("Feedback comment cannot be empty")
        if len(cleaned) > MAX_COMMENT_LENGTH:
            raise ValidationError(
                f"Feedback cannot exceed {MAX_COMMENT_LENGTH} characters"
            )
        return cleaned

    async def submit(
        self,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        submitted_by: uuid.UUID,
        rating: FeedbackRating,
        comment: str,
    ) -> MessageFeedback:
        cleaned = self._clean_comment(comment)

        # The conversation must belong to the caller's tenant, so feedback can
        # never be attached to another organization's output.
        conversation = await self._conversations.get_by_id(
            conversation_id, organization_id
        )
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        message = await self._repo.get_message(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise NotFoundError("Message", str(message_id))

        return await self._repo.create(
            organization_id=organization_id,
            conversation_id=conversation_id,
            message_id=message_id,
            submitted_by=submitted_by,
            rating=rating,
            comment=cleaned,
        )

    async def list_for_review(
        self,
        status: FeedbackStatus | None = None,
        organization_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[MessageFeedback], int]:
        return await self._repo.list_for_review(
            status=status, organization_id=organization_id, skip=skip, limit=limit
        )

    async def load_context_for(
        self, rows: list[MessageFeedback]
    ) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
        """Message bodies and submitter names for a page, keyed by id."""
        return await self._repo.load_context_for(rows)

    async def get_with_context(
        self, feedback_id: uuid.UUID
    ) -> tuple[MessageFeedback, str, str]:
        """Return the feedback plus the output it refers to and the submitter's name."""
        feedback = await self._repo.get_by_id(feedback_id)
        if feedback is None:
            raise NotFoundError("Feedback", str(feedback_id))
        message = await self._repo.get_message(feedback.message_id)
        submitter = await self._repo.get_submitter(feedback)
        return (
            feedback,
            message.content if message else "",
            submitter.display_name if submitter else "Unknown user",
        )

    async def set_status(
        self,
        feedback_id: uuid.UUID,
        status: FeedbackStatus,
        reviewed_by: uuid.UUID,
        review_note: str | None = None,
    ) -> MessageFeedback:
        if status is FeedbackStatus.PROMOTED:
            raise ValidationError(
                "Promote feedback by creating guidance from it, not by setting status"
            )
        feedback = await self._repo.get_by_id(feedback_id)
        if feedback is None:
            raise NotFoundError("Feedback", str(feedback_id))
        return await self._repo.set_status(
            feedback, status, reviewed_by, review_note=review_note
        )

    async def promote(
        self,
        feedback_id: uuid.UUID,
        content: str,
        scope: GuidanceScope,
        created_by: uuid.UUID,
        function_type: FunctionType | None = None,
    ) -> ApplicationGuidance:
        """Turn a piece of feedback into a guidance rule that shapes future answers."""
        feedback = await self._repo.get_by_id(feedback_id)
        if feedback is None:
            raise NotFoundError("Feedback", str(feedback_id))
        if feedback.status is FeedbackStatus.PROMOTED:
            raise ConflictError("This feedback has already been promoted")

        guidance = await self._guidance.create(
            content=content,
            scope=scope,
            created_by=created_by,
            # An organization-scoped rule inherits the tenant the feedback came
            # from — a platform admin is not tied to one organization.
            organization_id=(
                feedback.organization_id if scope is GuidanceScope.ORGANIZATION else None
            ),
            function_type=function_type,
            source_feedback_id=feedback.id,
        )
        await self._repo.set_status(feedback, FeedbackStatus.PROMOTED, created_by)
        return guidance
