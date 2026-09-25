"""Add `system_guided` to the functiontype PG enum.

System Analysis can now run its 5 Whys root-cause stage as a dialogue: the
model asks one "why" per turn and the user answers. That flow is pinned on
the conversation the same way Risk Register entry is, so it needs its own
FunctionType value. The `functiontype` enum is shared by `conversations`
and `application_guidance`; one ADD VALUE covers both.

PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a transaction
block, so we use alembic's autocommit_block. Downgrade is a no-op for the
same reason migration 021 gives: PostgreSQL has no DROP VALUE for enums.

Revision ID: 037
Revises: 036
Create Date: 2026-09-25
"""

from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE functiontype ADD VALUE IF NOT EXISTS 'system_guided'")


def downgrade() -> None:
    # No-op: PostgreSQL does not support removing a value from an enum.
    pass
