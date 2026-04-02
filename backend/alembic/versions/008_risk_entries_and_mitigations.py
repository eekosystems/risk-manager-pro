"""Add risk_entries and mitigations tables.

Revision ID: 008
Revises: 007
Create Date: 2026-03-15
"""

import sqlalchemy as sa

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

_risk_status_enum = sa.Enum("open", "mitigating", "closed", "accepted", name="riskstatus")
_risk_level_enum = sa.Enum("low", "medium", "serious", "high", name="risklevel")
_mitigation_status_enum = sa.Enum(
    "pending", "in_progress", "completed", "cancelled", name="mitigationstatus"
)


def upgrade() -> None:
    _risk_status_enum.create(op.get_bind(), checkfirst=True)
    _risk_level_enum.create(op.get_bind(), checkfirst=True)
    _mitigation_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "risk_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hazard", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("likelihood", sa.String(1), nullable=False),
        sa.Column("risk_level", _risk_level_enum, nullable=False),
        sa.Column("status", _risk_status_enum, nullable=False, server_default="open"),
        sa.Column("function_type", sa.String(20), nullable=False, server_default="general"),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "mitigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "risk_entry_id",
            sa.Uuid(),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("status", _mitigation_status_enum, nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mitigations")
    op.drop_table("risk_entries")
    _mitigation_status_enum.drop(op.get_bind(), checkfirst=True)
    _risk_level_enum.drop(op.get_bind(), checkfirst=True)
    _risk_status_enum.drop(op.get_bind(), checkfirst=True)
