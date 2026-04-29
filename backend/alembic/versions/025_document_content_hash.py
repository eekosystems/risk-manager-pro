"""Add content_hash column for upload deduplication.

Adds a per-document SHA-256 content hash plus a composite index on
(organization_id, content_hash) so duplicate-detection queries are fast
within a tenant. The column is nullable to accommodate pre-existing
documents that were ingested before hashing was wired up.

Revision ID: 025
Revises: 024
Create Date: 2026-04-29
"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
    )
    op.create_index(
        "ix_documents_org_content_hash",
        "documents",
        ["organization_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_org_content_hash", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "content_hash")
