"""Per-org risk alert thresholds.

Revision ID: 015
Revises: 014
Create Date: 2026-04-13
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_alert_thresholds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("max_open_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "risk_level", name="uq_org_risk_level"),
    )


def downgrade() -> None:
    op.drop_table("risk_alert_thresholds")
