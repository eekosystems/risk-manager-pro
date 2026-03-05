"""Tests for conversation repository."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus, FunctionType
from app.models.message import MessageRole
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from tests.conftest import ORGANIZATION_ID, make_test_organization, make_test_user


async def _seed(db: AsyncSession) -> tuple[User, uuid.UUID]:
    """Seed a user and organization, return (user, organization_id)."""
    org = make_test_organization()
    db.add(org)
    await db.flush()

    user = make_test_user()
    db.add(user)
    await db.flush()

    return user, org.id


async def _seed_two_orgs(db: AsyncSession) -> tuple[User, uuid.UUID, uuid.UUID]:
    """Seed a user and two organizations, return (user, org_a_id, org_b_id)."""
    org_a = make_test_organization()
    db.add(org_a)
    await db.flush()

    org_b_id = uuid.uuid4()
    org_b = Organization(
        id=org_b_id,
        name="Other Corp",
        slug="other-corp",
        status=OrganizationStatus.ACTIVE,
        is_platform=False,
    )
    db.add(org_b)
    await db.flush()

    user = make_test_user()
    db.add(user)
    await db.flush()

    return user, org_a.id, org_b_id


@pytest.mark.asyncio
async def test_create_conversation(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    conversation = await repo.create(
        user_id=user.id,
        organization_id=org_id,
        title="Runway Incursion Analysis",
        function_type=FunctionType.PHL,
    )

    assert conversation.id is not None
    assert conversation.title == "Runway Incursion Analysis"
    assert conversation.function_type == FunctionType.PHL
    assert conversation.user_id == user.id
    assert conversation.organization_id == org_id


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    created = await repo.create(
        user_id=user.id,
        organization_id=org_id,
        title="SRA Analysis",
    )

    fetched = await repo.get_by_id(created.id, org_id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "SRA Analysis"


@pytest.mark.asyncio
async def test_organization_isolation(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    conversation = await repo.create(
        user_id=user.id,
        organization_id=org_id,
        title="Org A Conversation",
    )

    other_org = uuid.uuid4()
    fetched = await repo.get_by_id(conversation.id, other_org)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_for_user(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    await repo.create(user_id=user.id, organization_id=org_id, title="Conv 1")
    await repo.create(user_id=user.id, organization_id=org_id, title="Conv 2")

    conversations = await repo.list_for_user(user.id, org_id)
    assert len(conversations) == 2


@pytest.mark.asyncio
async def test_add_message_and_ordering(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    conversation = await repo.create(
        user_id=user.id, organization_id=org_id
    )

    await repo.add_message(
        conversation_id=conversation.id,
        organization_id=org_id,
        role=MessageRole.USER,
        content="First message",
    )
    await repo.add_message(
        conversation_id=conversation.id,
        organization_id=org_id,
        role=MessageRole.ASSISTANT,
        content="Second message",
    )

    messages = await repo.get_messages(conversation.id, org_id)
    assert len(messages) == 2
    assert messages[0].content == "First message"
    assert messages[1].content == "Second message"


@pytest.mark.asyncio
async def test_archive_conversation(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = ConversationRepository(db_session)

    conversation = await repo.create(
        user_id=user.id, organization_id=org_id
    )

    result = await repo.archive(conversation.id, org_id)
    assert result is True

    conversations = await repo.list_for_user(user.id, org_id)
    assert len(conversations) == 0


# --- Tenant Isolation Tests ---


@pytest.mark.asyncio
async def test_get_messages_isolation(db_session: AsyncSession) -> None:
    """Messages in Org A conversation should not be visible from Org B."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = ConversationRepository(db_session)

    conv = await repo.create(user_id=user.id, organization_id=org_a, title="Org A conv")
    await repo.add_message(
        conversation_id=conv.id,
        organization_id=org_a,
        role=MessageRole.USER,
        content="Secret Org A message",
    )

    # Should get messages with correct org
    messages_a = await repo.get_messages(conv.id, org_a)
    assert len(messages_a) == 1

    # Should get nothing with wrong org
    messages_b = await repo.get_messages(conv.id, org_b)
    assert len(messages_b) == 0


@pytest.mark.asyncio
async def test_add_message_isolation(db_session: AsyncSession) -> None:
    """Adding a message to a conversation with wrong org should fail."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = ConversationRepository(db_session)

    conv = await repo.create(user_id=user.id, organization_id=org_a, title="Org A conv")

    # Should succeed with correct org
    msg = await repo.add_message(
        conversation_id=conv.id,
        organization_id=org_a,
        role=MessageRole.USER,
        content="Valid message",
    )
    assert msg.content == "Valid message"

    # Should fail with wrong org
    with pytest.raises(ValueError, match="not found"):
        await repo.add_message(
            conversation_id=conv.id,
            organization_id=org_b,
            role=MessageRole.USER,
            content="Invalid message",
        )


@pytest.mark.asyncio
async def test_list_for_user_isolation(db_session: AsyncSession) -> None:
    """Conversations in Org A should not appear in Org B listing."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = ConversationRepository(db_session)

    await repo.create(user_id=user.id, organization_id=org_a, title="A conv")
    await repo.create(user_id=user.id, organization_id=org_b, title="B conv")

    list_a = await repo.list_for_user(user.id, org_a)
    list_b = await repo.list_for_user(user.id, org_b)

    assert len(list_a) == 1
    assert list_a[0].title == "A conv"
    assert len(list_b) == 1
    assert list_b[0].title == "B conv"
