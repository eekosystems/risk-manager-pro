import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_folder import DocumentFolder


class DocumentFolderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        organization_id: uuid.UUID,
        name: str,
        created_by: uuid.UUID,
        parent_id: uuid.UUID | None = None,
    ) -> DocumentFolder:
        folder = DocumentFolder(
            organization_id=organization_id,
            name=name,
            parent_id=parent_id,
            created_by=created_by,
        )
        self._db.add(folder)
        await self._db.flush()
        return folder

    async def get_by_id(
        self, folder_id: uuid.UUID, organization_id: uuid.UUID
    ) -> DocumentFolder | None:
        stmt = select(DocumentFolder).where(
            DocumentFolder.id == folder_id,
            DocumentFolder.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[DocumentFolder]:
        stmt = (
            select(DocumentFolder)
            .where(DocumentFolder.organization_id == organization_id)
            .order_by(DocumentFolder.name)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def find_sibling_by_name(
        self,
        organization_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
        exclude_id: uuid.UUID | None = None,
    ) -> DocumentFolder | None:
        """Find a folder with the same name under the same parent (case-insensitive)."""
        stmt = select(DocumentFolder).where(
            DocumentFolder.organization_id == organization_id,
            DocumentFolder.parent_id.is_(None)
            if parent_id is None
            else DocumentFolder.parent_id == parent_id,
            DocumentFolder.name.ilike(name),
        )
        if exclude_id is not None:
            stmt = stmt.where(DocumentFolder.id != exclude_id)
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def update_folder(
        self,
        folder: DocumentFolder,
        name: str | None = None,
        parent_id: uuid.UUID | None = None,
        clear_parent: bool = False,
    ) -> DocumentFolder:
        if name is not None:
            folder.name = name
        if clear_parent:
            folder.parent_id = None
        elif parent_id is not None:
            folder.parent_id = parent_id
        await self._db.flush()
        return folder

    async def delete(self, folder: DocumentFolder) -> None:
        await self._db.delete(folder)
        await self._db.flush()

    async def assign_documents(
        self,
        document_ids: list[uuid.UUID],
        folder_id: uuid.UUID | None,
        organization_id: uuid.UUID,
    ) -> int:
        """Point the given documents at a folder (or root when None). Returns rows moved."""
        if not document_ids:
            return 0
        stmt = (
            update(Document)
            .where(
                Document.id.in_(document_ids),
                Document.organization_id == organization_id,
            )
            .values(folder_id=folder_id)
            .returning(Document.id)
            # The caller only needs the count; skipping session sync keeps this
            # to a single round trip.
            .execution_options(synchronize_session=False)
        )
        result = await self._db.execute(stmt)
        moved = list(result.scalars().all())
        await self._db.flush()
        return len(moved)

    async def count_documents_in_folder(
        self, folder_id: uuid.UUID, organization_id: uuid.UUID
    ) -> int:
        stmt = select(Document.id).where(
            Document.folder_id == folder_id,
            Document.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return len(list(result.scalars().all()))
