"""Tests for document service."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.document import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE, DocumentService
from tests.conftest import ORGANIZATION_ID, make_test_user


@pytest.fixture
def user() -> User:
    return make_test_user()


@pytest.fixture
def document_service(mock_storage_service: AsyncMock) -> DocumentService:
    db = AsyncMock()
    service = DocumentService(db=db, storage=mock_storage_service)
    return service


@pytest.mark.asyncio
async def test_upload_validates_content_type(document_service: DocumentService, user: User) -> None:
    with pytest.raises(ValidationError, match="Unsupported file type"):
        await document_service.upload(
            user=user,
            organization_id=ORGANIZATION_ID,
            filename="image.png",
            content_type="image/png",
            data=b"fake-image-data",
        )


@pytest.mark.asyncio
async def test_upload_validates_file_size(document_service: DocumentService, user: User) -> None:
    oversized_data = b"x" * (MAX_FILE_SIZE + 1)
    with pytest.raises(ValidationError, match="exceeds maximum size"):
        await document_service.upload(
            user=user,
            organization_id=ORGANIZATION_ID,
            filename="huge.txt",
            content_type="text/plain",
            data=oversized_data,
        )


@pytest.mark.asyncio
async def test_upload_stores_and_creates_document(
    document_service: DocumentService,
    mock_storage_service: AsyncMock,
    user: User,
) -> None:
    doc = Document(
        id=uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        uploaded_by=user.id,
        filename="safety-manual.txt",
        blob_path=f"{ORGANIZATION_ID}/doc-id/safety-manual.txt",
        content_type="text/plain",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
    )

    document_service._repo = AsyncMock()
    document_service._repo.create.return_value = doc

    result = await document_service.upload(
        user=user,
        organization_id=ORGANIZATION_ID,
        filename="safety-manual.txt",
        content_type="text/plain",
        data=b"fake plain text content",
    )

    mock_storage_service.upload.assert_awaited_once()
    assert result.filename == "safety-manual.txt"


@pytest.mark.asyncio
async def test_get_document_not_found(document_service: DocumentService, user: User) -> None:
    document_service._repo = AsyncMock()
    document_service._repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await document_service.get_document(uuid.uuid4(), ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_allowed_content_types_match_expected() -> None:
    assert "application/pdf" in ALLOWED_CONTENT_TYPES
    assert "text/plain" in ALLOWED_CONTENT_TYPES
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in ALLOWED_CONTENT_TYPES
    )
