"""Add `risk_register` to the functiontype PG enum.

Conversations carry a FunctionType enum stored as a PostgreSQL enum
type (`functiontype`) with values 'phl', 'sra', 'system', 'general'.
Sub-Prompt 4 (Risk Register chat) introduces a new 'risk_register'
value. PostgreSQL requires ALTER TYPE ... ADD VALUE to run outside a
transaction block, so we use alembic's autocommit_block.

Downgrade is a no-op: PostgreSQL has no safe DROP VALUE for an enum,
and any rows already tagged 'risk_register' would block the removal
regardless. Roll back application code + this migration together only
on a DB with no risk_register conversations.

Revision ID: 021
Revises: 020
Create Date: 2026-04-18
"""

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE functiontype ADD VALUE IF NOT EXISTS 'risk_register'")


def downgrade() -> None:
    # No-op: PostgreSQL does not support removing a value from an enum.
    pass
