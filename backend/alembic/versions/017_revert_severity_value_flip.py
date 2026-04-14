"""Revert the severity value flip from migration 016.

Migration 016 remapped stored severity values via (6 - severity) when we
thought the internal scheme was changing. The actual desired change is
display-only: stored values stay 1=Minimal…5=Catastrophic, but the UI
shows a flipped display number (1=Catastrophic). Re-flip the data to
restore the original stored values.

Revision ID: 017
Revises: 016
Create Date: 2026-04-14
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE risk_entries SET severity = 6 - severity "
        "WHERE severity BETWEEN 1 AND 5"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE risk_entries SET severity = 6 - severity "
        "WHERE severity BETWEEN 1 AND 5"
    )
