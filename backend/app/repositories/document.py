import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        organization_id: uuid.UUID,
        uploaded_by: uuid.UUID,
        filename: str,
        blob_path: str,
        content_type: str,
        size_bytes: int,
    ) -> Document:
        document = Document(
            organization_id=organization_id,
            uploaded_by=uploaded_by,
            filename=filename,
            blob_path=blob_path,
            content_type=content_type,
            size_bytes=size_bytes,
        )
        self._db.add(document)
        await self._db.flush()
        return document

    async def get_by_id(
        self, document_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Document], int]:
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.organization_id == organization_id)
        )
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: DocumentStatus,
        chunk_count: int = 0,
        error_message: str | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> None:
        if organization_id is not None:
            stmt = select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
        else:
            stmt = select(Document).where(Document.id == document_id)
        result = await self._db.execute(stmt)
        document = result.scalar_one_or_none()
        if document:
            document.status = status
            document.chunk_count = chunk_count
            if error_message:
                document.error_message = error_message
            await self._db.flush()

    async def get_by_id_system(self, document_id: uuid.UUID) -> Document | None:
        """Fetch document without org filter — trusted background processors only."""
        stmt = select(Document).where(Document.id == document_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        document = await self.get_by_id(document_id, organization_id)
        if not document:
            return False
        await self._db.delete(document)
        await self._db.flush()
        return True
