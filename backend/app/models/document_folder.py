import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentFolder(Base):
    """A user-created folder for organizing documents inside the app.

    These are display-only containers. They never touch ``Document.folder_path``,
    which mirrors the source SharePoint hierarchy and is the identity the crawler
    dedupes on — rewriting it would make synced files look new on the next crawl.
    """

    __tablename__ = "document_folders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_folders.id", ondelete="CASCADE"), default=None, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
