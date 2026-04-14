"""Flip severity scale so 1=Catastrophic (worst) and 5=Minimal (best).

Previous scheme: 1=Minimal, 2=Minor, 3=Major, 4=Hazardous, 5=Catastrophic.
New scheme:      1=Catastrophic, 2=Hazardous, 3=Major, 4=Minor, 5=Minimal.

Existing risk_entries.severity values are remapped via (6 - severity). The
risk_level column is preserved because the RISK_MATRIX is also flipped in
code so the same hazard yields the same risk level.

Revision ID: 016
Revises: 015
Create Date: 2026-04-14
"""

from alembic import op

revision = "016"
down_revision = "015"
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
