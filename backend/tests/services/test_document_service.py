"""Tests for document service."""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.document import ALLOWED_CONTENT_TYPES, DocumentService
from tests.conftest import ORGANIZATION_ID, make_test_user

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ZIP_MAGIC = b"PK\x03\x04"


async def _chunks(*payloads: bytes) -> AsyncIterator[bytes]:
    for payload in payloads:
        yield payload


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
async def test_upload_validates_file_size(
    document_service: DocumentService, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Patch the ceiling small so the test doesn't have to allocate gigabytes.
    monkeypatch.setattr(settings, "max_file_size_bytes", 1024)
    oversized_data = b"x" * (settings.max_file_size_bytes + 1)
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
    document_service._repo.find_by_content_hash.return_value = None
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


@pytest.mark.asyncio
async def test_spreadsheets_are_an_allowed_upload_type() -> None:
    """Client blocker: .xlsx tracking logs must be ingestible without conversion."""
    assert XLSX_CONTENT_TYPE in ALLOWED_CONTENT_TYPES
    assert "text/csv" in ALLOWED_CONTENT_TYPES


# --- Streaming upload (the path /documents/upload actually calls) -------------


def _prepare_streaming_service(
    service: DocumentService,
    storage: AsyncMock,
    *,
    head: bytes,
    size: int,
    duplicate_of: Document | None = None,
    created: Document | None = None,
) -> AsyncMock:
    storage.upload_stream.return_value = size
    storage.download_head.return_value = head
    repo = AsyncMock()
    repo.find_by_content_hash.return_value = duplicate_of
    repo.create.return_value = created if created is not None else _stub_document()
    service._repo = repo
    return repo


def _stub_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        uploaded_by=uuid.uuid4(),
        filename="stub.pdf",
        blob_path="stub",
        content_type="application/pdf",
        size_bytes=4,
        status=DocumentStatus.UPLOADED,
    )


@pytest.mark.asyncio
async def test_upload_streaming_accepts_xlsx_and_records_streamed_size(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    doc = Document(
        id=uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        uploaded_by=user.id,
        filename="Airport_Safety_Tracking.xlsx",
        blob_path=f"{ORGANIZATION_ID}/doc-id/Airport_Safety_Tracking.xlsx",
        content_type=XLSX_CONTENT_TYPE,
        size_bytes=12,
        status=DocumentStatus.UPLOADED,
    )
    repo = _prepare_streaming_service(
        document_service, mock_storage_service, head=ZIP_MAGIC, size=12, created=doc
    )

    result = await document_service.upload_streaming(
        user=user,
        organization_id=ORGANIZATION_ID,
        filename="Airport_Safety_Tracking.xlsx",
        content_type=XLSX_CONTENT_TYPE,
        chunks=_chunks(ZIP_MAGIC, b"rest-bytes"),
    )

    mock_storage_service.upload_stream.assert_awaited_once()
    assert result.filename == "Airport_Safety_Tracking.xlsx"
    # size_bytes comes from what the stream actually wrote, not a client claim.
    assert repo.create.await_args.kwargs["size_bytes"] == 12


@pytest.mark.asyncio
async def test_upload_streaming_passes_the_configured_size_cap_to_storage(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    """The 2 GB ceiling must reach the layer that enforces it mid-stream."""
    _prepare_streaming_service(
        document_service, mock_storage_service, head=b"%PDF", size=4, created=None
    )

    await document_service.upload_streaming(
        user=user,
        organization_id=ORGANIZATION_ID,
        filename="report.pdf",
        content_type="application/pdf",
        chunks=_chunks(b"%PDF"),
    )

    assert mock_storage_service.upload_stream.await_args.kwargs["max_bytes"] == (
        settings.max_file_size_bytes
    )
    assert settings.max_file_size_bytes == 2 * 1024 * 1024 * 1024


@pytest.mark.asyncio
async def test_upload_streaming_rejects_unsupported_type_before_streaming(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    with pytest.raises(ValidationError, match="Unsupported file type"):
        await document_service.upload_streaming(
            user=user,
            organization_id=ORGANIZATION_ID,
            filename="image.png",
            content_type="image/png",
            chunks=_chunks(b"\x89PNG"),
        )

    mock_storage_service.upload_stream.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_streaming_rejects_content_type_mismatch_and_deletes_blob(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    """A file whose real bytes don't match the declared type must not persist."""
    _prepare_streaming_service(
        document_service, mock_storage_service, head=b"\x89PNG", size=4, created=None
    )

    with pytest.raises(ValidationError, match="does not match declared type"):
        await document_service.upload_streaming(
            user=user,
            organization_id=ORGANIZATION_ID,
            filename="fake.pdf",
            content_type="application/pdf",
            chunks=_chunks(b"\x89PNG"),
        )

    mock_storage_service.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_streaming_detects_duplicate_and_deletes_orphan_blob(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    existing = Document(
        id=uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        uploaded_by=user.id,
        filename="already-there.pdf",
        blob_path="p",
        content_type="application/pdf",
        size_bytes=4,
        status=DocumentStatus.INDEXED,
    )
    _prepare_streaming_service(
        document_service,
        mock_storage_service,
        head=b"%PDF",
        size=4,
        duplicate_of=existing,
    )

    with pytest.raises(ConflictError, match="already-there.pdf"):
        await document_service.upload_streaming(
            user=user,
            organization_id=ORGANIZATION_ID,
            filename="copy.pdf",
            content_type="application/pdf",
            chunks=_chunks(b"%PDF"),
        )

    mock_storage_service.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_streaming_hashes_the_whole_stream(
    document_service: DocumentService, mock_storage_service: AsyncMock, user: User
) -> None:
    """Dedup must hash every chunk, not just the first."""
    import hashlib

    payloads = [b"%PDF", b"-second-", b"-third-"]

    async def _consume(_path: str, chunks: AsyncIterator[bytes], *_a: object, **_k: object) -> int:
        return sum([len(c) async for c in chunks])

    repo = _prepare_streaming_service(
        document_service, mock_storage_service, head=b"%PDF", size=0, created=None
    )
    mock_storage_service.upload_stream.side_effect = _consume

    await document_service.upload_streaming(
        user=user,
        organization_id=ORGANIZATION_ID,
        filename="report.pdf",
        content_type="application/pdf",
        chunks=_chunks(*payloads),
    )

    expected = hashlib.sha256(b"".join(payloads)).hexdigest()
    assert repo.create.await_args.kwargs["content_hash"] == expected
