"""
Test fixtures for Risk Manager Pro backend.

Uses a real PostgreSQL database (from docker-compose) with per-test SAVEPOINT
rollback for isolation. Azure services are mocked.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
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
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User
from app.services.audit import AuditLogger

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://rmp_dev:rmp_dev_password@localhost:5432/riskmanagerpro",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(test_engine, expire_on_commit=False)

ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        # Use a nested SAVEPOINT so that individual test operations
        # (including those that internally commit) get properly rolled back
        nested = await conn.begin_nested()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        try:
            yield session
        finally:
            await session.close()
            if nested.is_active:
                await nested.rollback()
            if transaction.is_active:
                await transaction.rollback()


def make_test_organization(
    *,
    org_id: uuid.UUID = ORGANIZATION_ID,
    name: str = "Test Organization",
    slug: str = "test-org",
    is_platform: bool = True,
) -> Organization:
    return Organization(
        id=org_id,
        name=name,
        slug=slug,
        status=OrganizationStatus.ACTIVE,
        is_platform=is_platform,
    )


@pytest.fixture
def test_organization() -> Organization:
    return make_test_organization()


def make_test_user(
    *,
    display_name: str = "Test User",
    email: str = "test@example.com",
    is_platform_admin: bool = False,
    is_active: bool = True,
) -> User:
    return User(
        id=uuid.uuid4(),
        entra_id=str(uuid.uuid4()),
        email=email,
        display_name=display_name,
        is_platform_admin=is_platform_admin,
        is_active=is_active,
        created_at=datetime.now(UTC),
        last_login=datetime.now(UTC),
    )


@pytest.fixture
def test_user() -> User:
    return make_test_user()


@pytest.fixture
def admin_user() -> User:
    return make_test_user(
        display_name="Admin User",
        email="admin@example.com",
        is_platform_admin=True,
    )


@pytest.fixture
def platform_admin_user() -> User:
    return make_test_user(
        display_name="Platform Admin",
        email="platform-admin@example.com",
        is_platform_admin=True,
    )


def make_test_membership(
    user_id: uuid.UUID,
    organization_id: uuid.UUID = ORGANIZATION_ID,
    role: MembershipRole = MembershipRole.ANALYST,
) -> OrganizationMembership:
    return OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        is_active=True,
    )


@pytest.fixture
def test_membership(test_user: User, test_organization: Organization) -> OrganizationMembership:
    return make_test_membership(test_user.id, test_organization.id)


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    client = AsyncMock()
    client.chat_completion.return_value = "This is a test AI response."
    client.embed.return_value = [0.1] * 1536
    client.embed_batch.return_value = [[0.1] * 1536]
    return client


@pytest.fixture
def mock_rag_service() -> AsyncMock:
    service = AsyncMock()
    service.hybrid_search.return_value = []
    return service


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    service = AsyncMock()
    service.upload.return_value = "org/doc-id/test.pdf"
    service.download.return_value = b"test file content"
    service.delete.return_value = None
    return service


@pytest.fixture
def mock_search_indexer() -> AsyncMock:
    indexer = AsyncMock()
    indexer.index_chunks.return_value = 5
    indexer.delete_by_document.return_value = None
    return indexer


@pytest.fixture
def mock_audit_logger() -> AsyncMock:
    logger = AsyncMock(spec=AuditLogger)
    logger.log.return_value = None
    return logger


@pytest.fixture
async def client(
    db_session: AsyncSession,
    test_user: User,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_current_organization] = lambda: test_organization
    app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger
    app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_search_indexer] = lambda: mock_search_indexer

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(
    db_session: AsyncSession,
    platform_admin_user: User,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated as a platform admin user."""
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: platform_admin_user
    app.dependency_overrides[get_current_organization] = lambda: test_organization
    app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger
    app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_search_indexer] = lambda: mock_search_indexer

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
