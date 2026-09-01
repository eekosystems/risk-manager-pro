import uuid

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.folder_scope import OrganizationFolderScope
from app.models.organization import Organization

logger = structlog.get_logger(__name__)

MAX_SCOPES_PER_ORGANIZATION = 50


def _normalize(path: str) -> str:
    return path.strip().strip("/")


def is_within_airport_root(folder_path: str) -> bool:
    """True when a path sits inside the configured airport-documents subtree.

    The outer guard that has always existed: it blocks traversal and any path
    outside the airport root, so no scope can be pointed at, say,
    ``Confidential/Executive``.
    """
    candidate = _normalize(folder_path)
    if not candidate or ".." in candidate:
        return False
    root = _normalize(settings.sharepoint_airport_root_folder)
    if not root:
        return True
    return candidate == root or candidate.startswith(f"{root}/")


def path_is_within(candidate: str, allowed_root: str) -> bool:
    """True when ``candidate`` is ``allowed_root`` or sits beneath it."""
    normalized = _normalize(candidate)
    root = _normalize(allowed_root)
    if not normalized or ".." in normalized:
        return False
    return normalized == root or normalized.startswith(f"{root}/")


class FolderScopeService:
    """Which SharePoint folders a client account may import from.

    Tenant isolation on the documents table stops an account reading another's
    data. This stops an account pulling data it was never granted out of the
    shared library to begin with.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_paths(self, organization_id: uuid.UUID) -> list[str]:
        stmt = (
            select(OrganizationFolderScope.folder_path)
            .where(OrganizationFolderScope.organization_id == organization_id)
            .order_by(OrganizationFolderScope.folder_path)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def set_paths(
        self,
        organization_id: uuid.UUID,
        folder_paths: list[str],
        created_by: uuid.UUID,
    ) -> list[str]:
        """Replace an account's scopes wholesale. Returns the stored paths."""
        if len(folder_paths) > MAX_SCOPES_PER_ORGANIZATION:
            raise ValidationError(
                f"An account cannot have more than {MAX_SCOPES_PER_ORGANIZATION} folders"
            )

        cleaned: list[str] = []
        for raw in folder_paths:
            path = _normalize(raw)
            if not path:
                raise ValidationError("A folder path cannot be empty")
            if not is_within_airport_root(path):
                raise ValidationError(f"'{path}' is outside the permitted SharePoint airport root")
            if path not in cleaned:
                cleaned.append(path)

        await self._db.execute(
            delete(OrganizationFolderScope).where(
                OrganizationFolderScope.organization_id == organization_id
            )
        )
        for path in cleaned:
            self._db.add(
                OrganizationFolderScope(
                    organization_id=organization_id,
                    folder_path=path,
                    created_by=created_by,
                )
            )
        await self._db.flush()
        return cleaned

    async def allowed_roots(self, organization: Organization) -> list[str] | None:
        """Roots this organization may import from.

        ``None`` means unrestricted — the platform organization keeps crawling
        the whole library, which is how Faith Group's own account has always
        worked. An empty list means the account is scoped to nothing and must
        import nothing.
        """
        paths = await self.list_paths(organization.id)
        if paths:
            return paths
        if organization.is_platform:
            return None
        return []

    async def is_path_allowed(self, organization: Organization, folder_path: str) -> bool:
        """Whether this organization may sync the given folder."""
        if not is_within_airport_root(folder_path):
            return False
        roots = await self.allowed_roots(organization)
        if roots is None:
            return True
        return any(path_is_within(folder_path, root) for root in roots)
