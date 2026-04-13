"""Create workflows table for PHL/SRA wizard state.

Revision ID: 014
Revises: 013
Create Date: 2026-04-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

_workflow_type_enum = ENUM("phl", "sra", name="workflowtype", create_type=False)
_workflow_status_enum = ENUM(
    "draft", "submitted", "approved", "rejected", name="workflowstatus", create_type=False
)


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN CREATE TYPE workflowtype AS ENUM ('phl', 'sra'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE workflowstatus AS ENUM "
        "('draft', 'submitted', 'approved', 'rejected'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )

    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", _workflow_type_enum, nullable=False),
        sa.Column("status", _workflow_status_enum, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("data", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "risk_entry_id",
            sa.Uuid(),
            sa.ForeignKey("risk_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflows")
    _workflow_status_enum.drop(op.get_bind(), checkfirst=True)
    _workflow_type_enum.drop(op.get_bind(), checkfirst=True)
