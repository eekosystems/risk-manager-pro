"""Add folder_path column to documents table.

Revision ID: 010
Revises: 009
Create Date: 2026-04-07
"""

import sqlalchemy as sa

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("folder_path", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "folder_path")
