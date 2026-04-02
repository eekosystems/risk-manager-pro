"""Tests for document processor service."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document, DocumentStatus, SourceType
from app.services.document_processor import DocumentProcessor


@pytest.fixture
def processor(
    mock_storage_service: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> DocumentProcessor:
    repo = AsyncMock()
    return DocumentProcessor(
        storage=mock_storage_service,
        openai_client=mock_openai_client,
        indexer=mock_search_indexer,
        repo=repo,
    )


@pytest.mark.asyncio
async def test_process_document_pipeline(
    processor: DocumentProcessor,
    mock_storage_service: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        organization_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        filename="safety-guide.txt",
        blob_path="org/doc/safety-guide.txt",
        content_type="text/plain",
        size_bytes=100,
        status=DocumentStatus.PROCESSING,
        source_type=SourceType.CLIENT,
    )

    mock_storage_service.download.return_value = (
        b"This is a safety document with important content."
    )
    mock_openai_client.embed_batch.return_value = [[0.1] * 1536]
    processor._repo.get_by_id_system.return_value = doc

    await processor.process(doc_id)

    processor._repo.update_status.assert_any_call(doc_id, DocumentStatus.PROCESSING)
    mock_storage_service.download.assert_awaited_once()
    mock_openai_client.embed_batch.assert_awaited()
    mock_search_indexer.index_chunks.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_empty_document_fails(
    processor: DocumentProcessor,
    mock_storage_service: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        organization_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        filename="empty.txt",
        blob_path="org/doc/empty.txt",
        content_type="text/plain",
        size_bytes=0,
        status=DocumentStatus.PROCESSING,
        source_type=SourceType.CLIENT,
    )

    mock_storage_service.download.return_value = b"   "
    processor._repo.get_by_id_system.return_value = doc

    await processor.process(doc_id)

    processor._repo.update_status.assert_any_call(
        doc_id, DocumentStatus.FAILED, error_message="No text extracted"
    )


@pytest.mark.asyncio
async def test_process_error_sets_failed_status(
    processor: DocumentProcessor,
    mock_storage_service: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        organization_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        filename="corrupt.pdf",
        blob_path="org/doc/corrupt.pdf",
        content_type="application/pdf",
        size_bytes=100,
        status=DocumentStatus.PROCESSING,
        source_type=SourceType.CLIENT,
    )

    mock_storage_service.download.side_effect = RuntimeError("Storage unavailable")
    processor._repo.get_by_id_system.return_value = doc

    await processor.process(doc_id)

    last_call = processor._repo.update_status.call_args_list[-1]
    assert last_call.args[1] == DocumentStatus.FAILED
    error_msg = last_call.kwargs.get("error_message", "")
    assert "Document processing failed" in error_msg


def test_extract_text_plain() -> None:
    text = DocumentProcessor._extract_text(b"Hello, world!", "text/plain")
    assert text == "Hello, world!"


def test_chunk_text_produces_chunks() -> None:
    long_text = "word " * 2000
    chunks = DocumentProcessor._chunk_text(long_text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) > 0
