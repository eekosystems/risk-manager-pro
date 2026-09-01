"""Org-admin supervisory read of another user's conversation.

Covers the access boundary (who may read), the tenant boundary (whose data is
reachable), and the audit trail the read is required to leave behind.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_current_user,
    get_openai_client,
    get_rag_service,
    get_search_indexer,
    get_storage_service,
)
from app.main import create_app
from app.models.conversation import Conversation, FunctionType
from app.models.message import Message, MessageRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole
from app.models.user import User
from tests.conftest import make_test_membership, make_test_organization, make_test_user


@pytest.fixture(autouse=True)
def _enforce_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "enforce_rbac", True)


async def _build_app(
    db_session: AsyncSession,
    user: User,
    organization: Organization,
    role: MembershipRole,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> FastAPI:
    db_session.add(make_test_membership(user.id, organization.id, role=role))
    await db_session.flush()

    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: organization
    app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger
    app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_search_indexer] = lambda: mock_search_indexer
    return app


async def _seed_conversation(
    db: AsyncSession,
    organization_id: uuid.UUID,
    author: User,
    title: str = "Runway incursion review",
) -> Conversation:
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=author.id,
        organization_id=organization_id,
        title=title,
        function_type=FunctionType.GENERAL,
    )
    db.add(conversation)
    await db.flush()

    db.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="What is the residual risk?",
        )
    )
    db.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="The residual risk is Medium.",
        )
    )
    await db.flush()
    return conversation


async def _seed_org_and_users(db: AsyncSession) -> tuple[Organization, User, User]:
    """Seed an organization plus a subject (chat author) and a reader."""
    org = make_test_organization()
    db.add(org)
    await db.flush()

    subject = make_test_user(email="analyst@example.com", display_name="Dana Analyst")
    db.add(subject)
    reader = make_test_user(email="admin@example.com", display_name="Alex Admin")
    db.add(reader)
    await db.flush()

    return org, subject, reader


async def _get_transcript(app: FastAPI, conversation_id: uuid.UUID) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(
            f"/api/v1/chat/conversations/{conversation_id}/transcript"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [MembershipRole.VIEWER, MembershipRole.ANALYST])
async def test_non_admins_cannot_read_another_users_conversation(
    role: MembershipRole,
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    org, subject, reader = await _seed_org_and_users(db_session)
    conversation = await _seed_conversation(db_session, org.id, subject)
    app = await _build_app(
        db_session,
        reader,
        org,
        role,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    response = await _get_transcript(app, conversation.id)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_org_admin_reads_another_users_conversation(
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    org, subject, reader = await _seed_org_and_users(db_session)
    conversation = await _seed_conversation(db_session, org.id, subject)
    app = await _build_app(
        db_session,
        reader,
        org,
        MembershipRole.ORG_ADMIN,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    response = await _get_transcript(app, conversation.id)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["title"] == "Runway incursion review"
    assert body["author"]["id"] == str(subject.id)
    assert body["author"]["display_name"] == "Dana Analyst"
    assert [m["content"] for m in body["messages"]] == [
        "What is the residual risk?",
        "The residual risk is Medium.",
    ]


@pytest.mark.asyncio
async def test_transcript_author_excludes_contact_details(
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    """The reader needs to know whose chat this is, not their contact record."""
    org, subject, reader = await _seed_org_and_users(db_session)
    conversation = await _seed_conversation(db_session, org.id, subject)
    app = await _build_app(
        db_session,
        reader,
        org,
        MembershipRole.ORG_ADMIN,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    response = await _get_transcript(app, conversation.id)

    assert set(response.json()["data"]["author"]) == {"id", "display_name"}


@pytest.mark.asyncio
async def test_org_admin_cannot_read_another_organizations_conversation(
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    org, subject, reader = await _seed_org_and_users(db_session)

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Corp",
        slug="other-corp",
        status=OrganizationStatus.ACTIVE,
        is_platform=False,
    )
    db_session.add(other_org)
    await db_session.flush()
    foreign = await _seed_conversation(db_session, other_org.id, subject, "Theirs")

    app = await _build_app(
        db_session,
        reader,
        org,
        MembershipRole.ORG_ADMIN,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    response = await _get_transcript(app, foreign.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reading_a_transcript_is_audited_with_the_subject(
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    org, subject, reader = await _seed_org_and_users(db_session)
    conversation = await _seed_conversation(db_session, org.id, subject)
    app = await _build_app(
        db_session,
        reader,
        org,
        MembershipRole.ORG_ADMIN,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    await _get_transcript(app, conversation.id)

    mock_audit_logger.log.assert_awaited()
    kwargs = mock_audit_logger.log.await_args.kwargs
    assert kwargs["action"] == "chat.conversation_viewed"
    assert kwargs["resource_id"] == str(conversation.id)
    assert kwargs["metadata"] == {"subject_user_id": str(subject.id)}
    # The subject is identified by id only — no name or email in the trail.
    assert subject.display_name not in str(kwargs)
    assert subject.email not in str(kwargs)


@pytest.mark.asyncio
async def test_a_failed_lookup_is_audited_too(
    db_session: AsyncSession,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    org, _subject, reader = await _seed_org_and_users(db_session)
    app = await _build_app(
        db_session,
        reader,
        org,
        MembershipRole.ORG_ADMIN,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )

    response = await _get_transcript(app, uuid.uuid4())

    assert response.status_code == 404
    kwargs = mock_audit_logger.log.await_args.kwargs
    assert kwargs["action"] == "chat.conversation_viewed"
    assert kwargs["outcome"] == "failure"
