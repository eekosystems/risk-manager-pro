"""Tests for document endpoints."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.documents import _get_document_service
from app.models.document import Document, DocumentStatus, SourceType
from app.models.user import User
from tests.conftest import ORGANIZATION_ID

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _make_document(organization_id: uuid.UUID, user_id: uuid.UUID) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        organization_id=organization_id,
        uploaded_by=user_id,
        filename="test-safety-doc.pdf",
        blob_path=f"{organization_id}/{uuid.uuid4()}/test-safety-doc.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        status=DocumentStatus.UPLOADED,
        source_type=SourceType.CLIENT,
        chunk_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    return doc


@pytest.mark.asyncio
async def test_upload_document(test_app: FastAPI, client: AsyncClient, test_user: User) -> None:
    doc = _make_document(ORGANIZATION_ID, test_user.id)
    mock_service = AsyncMock()
    # The endpoint streams the body to storage rather than buffering it, so it
    # calls upload_streaming — not upload.
    mock_service.upload_streaming.return_value = doc
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert "data" in body
    assert body["data"]["filename"] == "test-safety-doc.pdf"
    mock_service.upload_streaming.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_document_streams_body_in_chunks(
    test_app: FastAPI, client: AsyncClient, test_user: User
) -> None:
    """The request body must reach the service as an async chunk iterator.

    This is what lets a multi-GB upload run without buffering the whole file in
    the API process; passing bytes instead would silently reintroduce that.
    """
    doc = _make_document(ORGANIZATION_ID, test_user.id)
    seen: dict[str, object] = {}

    async def _capture(**kwargs: object) -> Document:
        chunks = kwargs["chunks"]
        seen["body"] = b"".join([c async for c in chunks])  # type: ignore[attr-defined]
        seen["filename"] = kwargs["filename"]
        return doc

    mock_service = AsyncMock()
    mock_service.upload_streaming.side_effect = _capture
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service

    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("tracking.xlsx", b"PK\x03\x04payload", XLSX_CONTENT_TYPE)},
    )

    assert response.status_code == 201
    assert seen["body"] == b"PK\x03\x04payload"
    assert seen["filename"] == "tracking.xlsx"


@pytest.mark.asyncio
async def test_list_documents(test_app: FastAPI, client: AsyncClient, test_user: User) -> None:
    mock_service = AsyncMock()
    mock_service.list_documents.return_value = ([], 0)
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert body["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_get_document(test_app: FastAPI, client: AsyncClient, test_user: User) -> None:
    doc = _make_document(ORGANIZATION_ID, test_user.id)
    mock_service = AsyncMock()
    mock_service.get_document.return_value = doc
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service
    response = await client.get(f"/api/v1/documents/{doc.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["filename"] == "test-safety-doc.pdf"


@pytest.mark.asyncio
async def test_delete_document(test_app: FastAPI, client: AsyncClient) -> None:
    doc_id = uuid.uuid4()
    mock_service = AsyncMock()
    mock_service.delete_document.return_value = None
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service
    response = await client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_upload_invalid_content_type(
    test_app: FastAPI, client: AsyncClient, test_user: User
) -> None:
    from app.core.exceptions import ValidationError

    mock_service = AsyncMock()
    mock_service.upload_streaming.side_effect = ValidationError(
        "Unsupported file type: image/png. Allowed: PDF, DOCX, XLSX, TXT"
    )
    test_app.dependency_overrides[_get_document_service] = lambda: mock_service
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("image.png", b"fake-png", "image/png")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
