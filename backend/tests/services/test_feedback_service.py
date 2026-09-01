"""Feedback capture and the curated guidance it is promoted into.

The guidance store is the application's permanent memory, so these cover both
the curation rules and what actually reaches the prompt.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.conversation import Conversation, FunctionType
from app.models.feedback import FeedbackRating, FeedbackStatus
from app.models.guidance import GuidanceScope
from app.models.message import Message, MessageRole
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.services.feedback import (
    MAX_GUIDANCE_RULES_PER_REQUEST,
    FeedbackService,
    GuidanceService,
)
from tests.conftest import make_test_organization, make_test_user


async def _seed(db: AsyncSession) -> tuple[User, uuid.UUID]:
    org = make_test_organization()
    db.add(org)
    await db.flush()
    user = make_test_user()
    db.add(user)
    await db.flush()
    return user, org.id


async def _seed_second_org(db: AsyncSession) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.add(
        Organization(
            id=org_id,
            name="Other Corp",
            slug="other-corp",
            status=OrganizationStatus.ACTIVE,
            is_platform=False,
        )
    )
    await db.flush()
    return org_id


async def _seed_conversation(
    db: AsyncSession, org_id: uuid.UUID, user: User
) -> tuple[Conversation, Message]:
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_id,
        title="Runway incursion",
        function_type=FunctionType.SRA,
    )
    db.add(conversation)
    await db.flush()
    message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="The residual risk is Medium.",
    )
    db.add(message)
    await db.flush()
    return conversation, message


# --- Submission ---


@pytest.mark.asyncio
async def test_submit_feedback(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    conversation, message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)

    feedback = await service.submit(
        organization_id=org_id,
        conversation_id=conversation.id,
        message_id=message.id,
        submitted_by=user.id,
        rating=FeedbackRating.NOT_HELPFUL,
        comment="  Should cite AC 150/5340-30.  ",
    )

    assert feedback.comment == "Should cite AC 150/5340-30."
    assert feedback.status is FeedbackStatus.NEW
    assert feedback.rating is FeedbackRating.NOT_HELPFUL


@pytest.mark.asyncio
async def test_submit_rejects_empty_comment(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    conversation, message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)

    with pytest.raises(ValidationError, match="cannot be empty"):
        await service.submit(
            organization_id=org_id,
            conversation_id=conversation.id,
            message_id=message.id,
            submitted_by=user.id,
            rating=FeedbackRating.HELPFUL,
            comment="   ",
        )


@pytest.mark.asyncio
async def test_cannot_attach_feedback_to_another_tenants_output(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    conversation, message = await _seed_conversation(db_session, other_org_id, user)
    service = FeedbackService(db_session)

    with pytest.raises(NotFoundError):
        await service.submit(
            organization_id=org_id,
            conversation_id=conversation.id,
            message_id=message.id,
            submitted_by=user.id,
            rating=FeedbackRating.HELPFUL,
            comment="Nice.",
        )


@pytest.mark.asyncio
async def test_message_must_belong_to_the_named_conversation(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    conversation, _ = await _seed_conversation(db_session, org_id, user)
    _, other_message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)

    with pytest.raises(NotFoundError):
        await service.submit(
            organization_id=org_id,
            conversation_id=conversation.id,
            message_id=other_message.id,
            submitted_by=user.id,
            rating=FeedbackRating.HELPFUL,
            comment="Mismatched.",
        )


# --- Promotion ---


@pytest.mark.asyncio
async def test_promoting_feedback_creates_guidance_and_marks_it(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    conversation, message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)
    feedback = await service.submit(
        organization_id=org_id,
        conversation_id=conversation.id,
        message_id=message.id,
        submitted_by=user.id,
        rating=FeedbackRating.NOT_HELPFUL,
        comment="Should cite AC 150/5340-30.",
    )

    guidance = await service.promote(
        feedback_id=feedback.id,
        content="Cite AC 150/5340-30 on runway incursion findings.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        function_type=FunctionType.SRA,
    )

    assert guidance.content == "Cite AC 150/5340-30 on runway incursion findings."
    assert guidance.organization_id == org_id
    assert guidance.source_feedback_id == feedback.id
    assert guidance.is_active is True
    assert feedback.status is FeedbackStatus.PROMOTED


@pytest.mark.asyncio
async def test_feedback_cannot_be_promoted_twice(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    conversation, message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)
    feedback = await service.submit(
        organization_id=org_id,
        conversation_id=conversation.id,
        message_id=message.id,
        submitted_by=user.id,
        rating=FeedbackRating.HELPFUL,
        comment="Good.",
    )
    await service.promote(
        feedback_id=feedback.id,
        content="A rule.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
    )

    with pytest.raises(ConflictError, match="already been promoted"):
        await service.promote(
            feedback_id=feedback.id,
            content="A second rule.",
            scope=GuidanceScope.ORGANIZATION,
            created_by=user.id,
        )


@pytest.mark.asyncio
async def test_global_promotion_is_not_tied_to_the_source_tenant(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    conversation, message = await _seed_conversation(db_session, org_id, user)
    service = FeedbackService(db_session)
    feedback = await service.submit(
        organization_id=org_id,
        conversation_id=conversation.id,
        message_id=message.id,
        submitted_by=user.id,
        rating=FeedbackRating.HELPFUL,
        comment="Applies everywhere.",
    )

    guidance = await service.promote(
        feedback_id=feedback.id,
        content="Always show the matrix cell label.",
        scope=GuidanceScope.GLOBAL,
        created_by=user.id,
    )

    assert guidance.scope is GuidanceScope.GLOBAL
    assert guidance.organization_id is None


# --- Guidance validation ---


@pytest.mark.asyncio
async def test_org_scoped_guidance_requires_an_organization(
    db_session: AsyncSession,
) -> None:
    user, _org_id = await _seed(db_session)
    service = GuidanceService(db_session)

    with pytest.raises(ValidationError, match="needs an organization"):
        await service.create(
            content="A rule.",
            scope=GuidanceScope.ORGANIZATION,
            created_by=user.id,
        )


@pytest.mark.asyncio
async def test_global_guidance_cannot_name_an_organization(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)

    with pytest.raises(ValidationError, match="cannot be tied"):
        await service.create(
            content="A rule.",
            scope=GuidanceScope.GLOBAL,
            created_by=user.id,
            organization_id=org_id,
        )


# --- What actually reaches the prompt ---


@pytest.mark.asyncio
async def test_prompt_block_is_empty_when_no_guidance_applies(
    db_session: AsyncSession,
) -> None:
    _user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)

    assert await service.build_prompt_block(org_id, FunctionType.SRA) == ""


@pytest.mark.asyncio
async def test_prompt_block_includes_global_and_own_org_rules(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    service = GuidanceService(db_session)

    await service.create(
        content="Global rule.", scope=GuidanceScope.GLOBAL, created_by=user.id
    )
    await service.create(
        content="Our rule.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=org_id,
    )
    await service.create(
        content="Their rule.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=other_org_id,
    )

    block = await service.build_prompt_block(org_id, FunctionType.SRA)

    assert "Global rule." in block
    assert "Our rule." in block
    # Tenant isolation: another client's guidance must never shape our answers.
    assert "Their rule." not in block


@pytest.mark.asyncio
async def test_prompt_block_respects_function_scoping(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)

    await service.create(
        content="SRA only.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=org_id,
        function_type=FunctionType.SRA,
    )
    await service.create(
        content="Every function.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=org_id,
    )

    sra_block = await service.build_prompt_block(org_id, FunctionType.SRA)
    phl_block = await service.build_prompt_block(org_id, FunctionType.PHL)

    assert "SRA only." in sra_block
    assert "Every function." in sra_block
    assert "SRA only." not in phl_block
    assert "Every function." in phl_block


@pytest.mark.asyncio
async def test_deactivated_guidance_stops_reaching_the_prompt(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)
    rule = await service.create(
        content="Withdrawn rule.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=org_id,
    )

    await service.update(rule.id, is_active=False)
    block = await service.build_prompt_block(org_id, FunctionType.SRA)

    assert "Withdrawn rule." not in block


@pytest.mark.asyncio
async def test_prompt_block_is_capped_so_guidance_cannot_crowd_out_context(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)
    for i in range(MAX_GUIDANCE_RULES_PER_REQUEST + 5):
        await service.create(
            content=f"Rule number {i}.",
            scope=GuidanceScope.ORGANIZATION,
            created_by=user.id,
            organization_id=org_id,
        )

    block = await service.build_prompt_block(org_id, FunctionType.SRA)

    assert block.count("\n- ") == MAX_GUIDANCE_RULES_PER_REQUEST


@pytest.mark.asyncio
async def test_prompt_block_does_not_license_unsupported_claims(
    db_session: AsyncSession,
) -> None:
    """Guidance shapes presentation; it must never override grounding."""
    user, org_id = await _seed(db_session)
    service = GuidanceService(db_session)
    await service.create(
        content="Be concise.",
        scope=GuidanceScope.ORGANIZATION,
        created_by=user.id,
        organization_id=org_id,
    )

    block = await service.build_prompt_block(org_id, FunctionType.SRA)

    assert "retrieved context does not support" in block
