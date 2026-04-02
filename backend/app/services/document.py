import re
import uuid

import structlog
from azure.core.exceptions import AzureError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document, SourceType
from app.models.user import User
from app.repositories.document import DocumentRepository
from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Magic byte signatures for file content validation
_FILE_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
}

_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._\-]")
_MAX_FILENAME_LENGTH = 255


class DocumentService:
    def __init__(self, db: AsyncSession, storage: BlobStorageService) -> None:
        self._repo = DocumentRepository(db)
        self._storage = storage

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Strip path separators and unsafe characters, enforce max length."""
        # Remove any path components
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        # Remove directory traversal patterns
        name = name.replace("..", "")
        # Replace unsafe characters with underscores
        name = _SAFE_FILENAME_RE.sub("_", name)
        # Enforce max length (preserve extension)
        if len(name) > _MAX_FILENAME_LENGTH:
            stem, _, ext = name.rpartition(".")
            max_stem = _MAX_FILENAME_LENGTH - len(ext) - 1
            name = f"{stem[:max_stem]}.{ext}"
        return name or "unnamed"

    @staticmethod
    def _validate_file_content(data: bytes, content_type: str) -> None:
        """Verify file magic bytes match the declared content type."""
        signatures = _FILE_SIGNATURES.get(content_type)
        if signatures is None:
            # text/plain has no reliable magic bytes — skip
            return
        if not any(data[: len(sig)] == sig for sig in signatures):
            raise ValidationError(f"File content does not match declared type {content_type}")

    async def upload(
        self,
        user: User,
        organization_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
        source_type: SourceType = SourceType.CLIENT,
    ) -> Document:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(f"Unsupported file type: {content_type}. Allowed: PDF, DOCX, TXT")

        self._validate_file_content(data, content_type)

        if len(data) > settings.max_file_size_bytes:
            raise ValidationError(
                f"File exceeds maximum size of {settings.max_file_size_bytes // (1024 * 1024)} MB"
            )

        safe_filename = self._sanitize_filename(filename)
        blob_path = f"{organization_id}/{uuid.uuid4()}/{safe_filename}"

        await self._storage.upload(blob_path, data, content_type)

        document = await self._repo.create(
            organization_id=organization_id,
            uploaded_by=user.id,
            filename=safe_filename,
            blob_path=blob_path,
            content_type=content_type,
            size_bytes=len(data),
            source_type=source_type,
        )

        logger.info(
            "document_uploaded",
            document_id=str(document.id),
            filename=safe_filename,
            size_bytes=len(data),
        )

        return document

    async def list_documents(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Document], int]:
        return await self._repo.list_for_organization(organization_id, skip, limit)

    async def get_document(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document:
        document = await self._repo.get_by_id(document_id, organization_id)
        if not document:
            raise NotFoundError("Document", str(document_id))
        return document

    async def delete_document(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        document = await self._repo.get_by_id(document_id, organization_id)
        if not document:
            raise NotFoundError("Document", str(document_id))
        try:
            await self._storage.delete(document.blob_path)
        except AzureError:
            logger.error(
                "blob_delete_failed",
                blob_path=document.blob_path,
                document_id=str(document_id),
                exc_info=True,
            )
        await self._repo.delete(document_id, organization_id)
        logger.info("document_deleted", document_id=str(document_id))
