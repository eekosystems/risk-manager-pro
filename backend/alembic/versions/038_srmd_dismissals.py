"""Remember SharePoint SRMD hazards an organization deleted from its register.

SRMD hazards are now imported onto the Risk Register automatically instead
of through a manual import step. Deleting an imported hazard would otherwise
be undone by the next import, so each deletion records the entry's
`srmd_ref` here and the import and the scan summary skip it.

Revision ID: 038
Revises: 037
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "srmd_dismissals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("srmd_ref", sa.String(length=64), nullable=False),
        sa.Column(
            "dismissed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("organization_id", "srmd_ref", name="uq_srmd_dismissals_org_srmd_ref"),
    )
    op.create_index("ix_srmd_dismissals_organization_id", "srmd_dismissals", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_srmd_dismissals_organization_id", table_name="srmd_dismissals")
    op.drop_table("srmd_dismissals")
