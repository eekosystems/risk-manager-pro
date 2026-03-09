"""Add last_activity column to users for session timeout

Revision ID: 004
Revises: 003
Create Date: 2026-03-04
"""

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_activity", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_activity")
