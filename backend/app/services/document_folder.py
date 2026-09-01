import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.document_folder import DocumentFolder
from app.repositories.document import DocumentRepository
from app.repositories.document_folder import DocumentFolderRepository

logger = structlog.get_logger(__name__)

MAX_FOLDER_NAME_LENGTH = 255
MAX_FOLDER_DEPTH = 10
MAX_MOVE_BATCH = 500


class DocumentFolderService:
    """In-app folder organization for the document index.

    Folders are shared across the organization and never propagate to
    SharePoint — moving a document only rewrites ``Document.folder_id``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._repo = DocumentFolderRepository(db)
        self._documents = DocumentRepository(db)

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Folder name cannot be empty")
        if len(cleaned) > MAX_FOLDER_NAME_LENGTH:
            raise ValidationError(f"Folder name cannot exceed {MAX_FOLDER_NAME_LENGTH} characters")
        if "/" in cleaned or "\\" in cleaned:
            raise ValidationError("Folder name cannot contain path separators")
        return cleaned

    async def _require_folder(
        self, folder_id: uuid.UUID, organization_id: uuid.UUID
    ) -> DocumentFolder:
        folder = await self._repo.get_by_id(folder_id, organization_id)
        if folder is None:
            raise NotFoundError("Folder", str(folder_id))
        return folder

    async def _ancestors(
        self, folder: DocumentFolder, organization_id: uuid.UUID
    ) -> list[DocumentFolder]:
        """Walk from a folder's parent to the root, newest ancestor first."""
        chain: list[DocumentFolder] = []
        seen: set[uuid.UUID] = {folder.id}
        current_id = folder.parent_id
        while current_id is not None:
            if current_id in seen:
                # Defensive: a cycle should be impossible, but never loop forever.
                break
            parent = await self._repo.get_by_id(current_id, organization_id)
            if parent is None:
                break
            chain.append(parent)
            seen.add(parent.id)
            current_id = parent.parent_id
        return chain

    async def _assert_depth_allows_child(
        self, parent: DocumentFolder, organization_id: uuid.UUID
    ) -> None:
        depth = len(await self._ancestors(parent, organization_id)) + 1
        if depth >= MAX_FOLDER_DEPTH:
            raise ValidationError(
                f"Folders cannot be nested more than {MAX_FOLDER_DEPTH} levels deep"
            )

    async def _assert_name_available(
        self,
        organization_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        clash = await self._repo.find_sibling_by_name(
            organization_id, name, parent_id, exclude_id=exclude_id
        )
        if clash is not None:
            raise ConflictError(f"A folder named '{name}' already exists here")

    async def list_folders(self, organization_id: uuid.UUID) -> list[DocumentFolder]:
        return await self._repo.list_for_organization(organization_id)

    async def create_folder(
        self,
        organization_id: uuid.UUID,
        created_by: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
    ) -> DocumentFolder:
        clean = self._clean_name(name)
        if parent_id is not None:
            parent = await self._require_folder(parent_id, organization_id)
            await self._assert_depth_allows_child(parent, organization_id)
        await self._assert_name_available(organization_id, clean, parent_id)
        return await self._repo.create(
            organization_id=organization_id,
            name=clean,
            created_by=created_by,
            parent_id=parent_id,
        )

    async def rename_folder(
        self, folder_id: uuid.UUID, organization_id: uuid.UUID, name: str
    ) -> DocumentFolder:
        folder = await self._require_folder(folder_id, organization_id)
        clean = self._clean_name(name)
        await self._assert_name_available(
            organization_id, clean, folder.parent_id, exclude_id=folder.id
        )
        return await self._repo.update_folder(folder, name=clean)

    async def move_folder(
        self,
        folder_id: uuid.UUID,
        organization_id: uuid.UUID,
        parent_id: uuid.UUID | None,
    ) -> DocumentFolder:
        folder = await self._require_folder(folder_id, organization_id)
        if parent_id == folder.id:
            raise ValidationError("A folder cannot be moved into itself")

        if parent_id is not None:
            parent = await self._require_folder(parent_id, organization_id)
            ancestors = await self._ancestors(parent, organization_id)
            if any(a.id == folder.id for a in ancestors):
                raise ValidationError("A folder cannot be moved into one of its own subfolders")
            await self._assert_depth_allows_child(parent, organization_id)

        await self._assert_name_available(
            organization_id, folder.name, parent_id, exclude_id=folder.id
        )
        return await self._repo.update_folder(
            folder, parent_id=parent_id, clear_parent=parent_id is None
        )

    async def delete_folder(self, folder_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        """Remove a folder and its subfolders. Documents inside are unfiled, never deleted."""
        folder = await self._require_folder(folder_id, organization_id)
        await self._repo.delete(folder)

    async def move_documents(
        self,
        document_ids: list[uuid.UUID],
        folder_id: uuid.UUID | None,
        organization_id: uuid.UUID,
    ) -> int:
        if not document_ids:
            raise ValidationError("No documents specified")
        if len(document_ids) > MAX_MOVE_BATCH:
            raise ValidationError(f"Cannot move more than {MAX_MOVE_BATCH} documents at once")
        if folder_id is not None:
            await self._require_folder(folder_id, organization_id)

        found = await self._documents.get_documents_by_ids(document_ids, organization_id)
        if len(found) != len(set(document_ids)):
            raise NotFoundError("Document", "one or more of the requested documents")

        return await self._repo.assign_documents(document_ids, folder_id, organization_id)
