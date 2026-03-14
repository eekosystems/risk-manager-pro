import uuid

import structlog
from azure.core.exceptions import AzureError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document
from app.models.user import User
from app.repositories.document import DocumentRepository
from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


class DocumentService:
    def __init__(self, db: AsyncSession, storage: BlobStorageService) -> None:
        self._repo = DocumentRepository(db)
        self._storage = storage

    async def upload(
        self,
        user: User,
        organization_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Document:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(f"Unsupported file type: {content_type}. Allowed: PDF, DOCX, TXT")

        if len(data) > settings.max_file_size_bytes:
            raise ValidationError(
                f"File exceeds maximum size of {settings.max_file_size_bytes // (1024 * 1024)} MB"
            )

        blob_path = f"{organization_id}/{uuid.uuid4()}/{filename}"

        await self._storage.upload(blob_path, data, content_type)

        document = await self._repo.create(
            organization_id=organization_id,
            uploaded_by=user.id,
            filename=filename,
            blob_path=blob_path,
            content_type=content_type,
            size_bytes=len(data),
        )

        logger.info(
            "document_uploaded",
            document_id=str(document.id),
            filename=filename,
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
