"""Tests for document endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.document import Document, DocumentStatus
from app.models.user import User
from tests.conftest import ORGANIZATION_ID


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
        chunk_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return doc


@pytest.mark.asyncio
async def test_upload_document(client: AsyncClient, test_user: User) -> None:
    doc = _make_document(ORGANIZATION_ID, test_user.id)
    with patch("app.api.v1.documents._get_document_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.upload.return_value = doc
        mock_factory.return_value = mock_service
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
        )
    assert response.status_code == 201
    body = response.json()
    assert "data" in body
    assert body["data"]["filename"] == "test-safety-doc.pdf"


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, test_user: User) -> None:
    with patch("app.api.v1.documents._get_document_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.list_documents.return_value = ([], 0)
        mock_factory.return_value = mock_service
        response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert body["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_get_document(client: AsyncClient, test_user: User) -> None:
    doc = _make_document(ORGANIZATION_ID, test_user.id)
    with patch("app.api.v1.documents._get_document_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.get_document.return_value = doc
        mock_factory.return_value = mock_service
        response = await client.get(f"/api/v1/documents/{doc.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["filename"] == "test-safety-doc.pdf"


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient) -> None:
    doc_id = uuid.uuid4()
    with patch("app.api.v1.documents._get_document_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.delete_document.return_value = None
        mock_factory.return_value = mock_service
        response = await client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_upload_invalid_content_type(
    client: AsyncClient, test_user: User
) -> None:
    from app.core.exceptions import ValidationError

    with patch("app.api.v1.documents._get_document_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.upload.side_effect = ValidationError(
            "Unsupported file type: image/png. Allowed: PDF, DOCX, TXT"
        )
        mock_factory.return_value = mock_service
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("image.png", b"fake-png", "image/png")},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
