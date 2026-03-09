"""Add invitation_status to users table.

Revision ID: 006
Revises: 005
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "invitation_status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "invitation_status")
