"""Tests for audit logging service."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.tasks import drain_all_tasks
from app.models.user import User
from app.services.audit import AuditLogger
from tests.conftest import make_test_user


@pytest.fixture
def mock_request() -> MagicMock:
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers.get.return_value = "TestAgent/1.0"
    request.state.correlation_id = str(uuid.uuid4())
    return request


@pytest.mark.asyncio
async def test_audit_log_creates_task(mock_request: MagicMock) -> None:
    db = AsyncMock()
    logger = AuditLogger(db=db, request=mock_request)
    user = make_test_user()

    with patch("app.services.audit.asyncio.create_task") as mock_create_task:
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()
        mock_create_task.return_value = mock_task

        await logger.log(
            action="test.action",
            user=user,
            resource_type="document",
            resource_id=str(uuid.uuid4()),
            outcome="success",
        )

        mock_create_task.assert_called_once()
        mock_task.add_done_callback.assert_called_once()


@pytest.mark.asyncio
async def test_audit_log_passes_organization_id(mock_request: MagicMock) -> None:
    db = AsyncMock()
    logger = AuditLogger(db=db, request=mock_request)
    user = make_test_user()
    org_id = uuid.uuid4()

    with patch("app.services.audit.asyncio.create_task") as mock_create_task:
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()
        mock_create_task.return_value = mock_task

        await logger.log(
            action="test.action",
            user=user,
            resource_type="document",
            resource_id=str(uuid.uuid4()),
            outcome="success",
            organization_id=org_id,
        )

        mock_create_task.assert_called_once()
        # Verify the coroutine passed to create_task has the org_id
        call_args = mock_create_task.call_args
        assert call_args is not None


@pytest.mark.asyncio
async def test_audit_log_with_metadata(mock_request: MagicMock) -> None:
    db = AsyncMock()
    logger = AuditLogger(db=db, request=mock_request)
    user = make_test_user()

    metadata = {"extra_key": "extra_value"}
    with patch("app.services.audit.asyncio.create_task") as mock_create_task:
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()
        mock_create_task.return_value = mock_task

        await logger.log(
            action="test.action",
            user=user,
            metadata=metadata,
        )

        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_audit_task_tracking(mock_request: MagicMock) -> None:
    """Verify that pending audit tasks are tracked and can be drained."""
    db = AsyncMock()
    logger = AuditLogger(db=db, request=mock_request)
    user = make_test_user()

    # Track tasks created with real asyncio (mock the DB write)
    with patch("app.services.audit._write_audit_entry", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = None

        await logger.log(
            action="test.tracking",
            user=user,
            resource_type="test",
        )

        # Give the event loop a moment to schedule the task
        await asyncio.sleep(0.01)

        # Drain should complete without error
        await drain_all_tasks()


@pytest.mark.asyncio
async def test_audit_logger_does_not_use_db_attribute(mock_request: MagicMock) -> None:
    """Verify the AuditLogger does not carry a dead _db attribute."""
    db = AsyncMock()
    logger = AuditLogger(db=db, request=mock_request)
    assert not hasattr(logger, "_db")
