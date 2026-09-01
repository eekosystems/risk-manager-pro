import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrganizationFolderScope(Base):
    """A SharePoint folder a client account is permitted to import from.

    Document rows are already isolated by organization_id, which stops one
    account reading another's data. This is the other half: it stops an account
    pulling data it was never meant to have out of the shared SharePoint
    library in the first place.

    An account with no scopes imports nothing. The one exception is the
    platform organization, which crawls the whole library as before.
    """

    __tablename__ = "organization_folder_scopes"
    __table_args__ = (
        UniqueConstraint("organization_id", "folder_path", name="uq_organization_folder_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    folder_path: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
