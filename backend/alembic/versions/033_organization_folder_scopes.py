"""Restrict which SharePoint folders a client account may import from.

Document rows were already isolated by organization_id, so one account could
not read another's data. Nothing, however, restricted what an account could
pull out of the shared SharePoint library: /sharepoint/crawl discovered every
file in the drive and imported it into whichever organization ran it. A client
account clicking "Sync from SharePoint" would have ingested every airport's
documents.

This scopes the crawl per account. An account with no scope row imports
nothing; the platform organization keeps crawling the whole library.

Revision ID: 033
Revises: 032
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_folder_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("folder_path", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("organization_id", "folder_path", name="uq_organization_folder_path"),
    )
    op.create_index(
        "ix_organization_folder_scopes_organization_id",
        "organization_folder_scopes",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_folder_scopes_organization_id",
        table_name="organization_folder_scopes",
    )
    op.drop_table("organization_folder_scopes")
