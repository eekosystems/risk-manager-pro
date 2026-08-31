"""User-created folders for organizing documents in the app.

Documents uploaded through the front end carry no folder_path (that column
mirrors the SharePoint hierarchy and is only set by the crawler), so every
upload lands in one flat list at the root of the Indexed Files tree. This adds
a real folder entity plus a documents.folder_id assignment so users can create
folders and drag files into them.

folder_id is deliberately separate from folder_path: the crawler dedupes on
(filename, folder_path), so rewriting that column would make a moved file look
new on the next sync and re-download it as a duplicate.

Revision ID: 031
Revises: 030
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_folders",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_document_folders_organization_id", "document_folders", ["organization_id"]
    )
    op.create_index("ix_document_folders_parent_id", "document_folders", ["parent_id"])

    op.add_column(
        "documents",
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.drop_column("documents", "folder_id")
    op.drop_index("ix_document_folders_parent_id", table_name="document_folders")
    op.drop_index("ix_document_folders_organization_id", table_name="document_folders")
    op.drop_table("document_folders")
