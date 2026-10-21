"""Re-sync saved prompts after the scoring and accountability rule changes.

The SRA prompt now defines likelihood as the probability of the harmful
outcome, fixes severity per hazard, limits controls to what the airport's
class can operate, and leaves owners and due dates to the airport. System
Analysis performs root cause analysis only when asked or when an event is
described. The Risk Register prompt no longer makes owner and due date
mandatory per action. Saved organization prompts are re-synced from the code
defaults the way migrations 030 through 041 did; downgrade leaves them.

Revision ID: 043
Revises: 042
Create Date: 2026-10-21
"""

import sqlalchemy as sa

from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.prompts import (
        GENERAL_PROMPT,
        PHL_PROMPT,
        RISK_REGISTER_PROMPT,
        SRA_PROMPT,
        SYSTEM_ANALYSIS_PROMPT,
    )

    op.get_bind().execute(
        sa.text(
            "UPDATE organization_settings "
            "SET settings_json = settings_json || jsonb_build_object("
            "    'system_prompt', CAST(:sys AS text), "
            "    'phl_prompt', CAST(:phl AS text), "
            "    'sra_prompt', CAST(:sra AS text), "
            "    'system_analysis_prompt', CAST(:sa AS text), "
            "    'risk_register_prompt', CAST(:rr AS text)"
            "), "
            "updated_at = NOW() "
            "WHERE category = 'prompts'"
        ),
        {
            "sys": GENERAL_PROMPT,
            "phl": PHL_PROMPT,
            "sra": SRA_PROMPT,
            "sa": SYSTEM_ANALYSIS_PROMPT,
            "rr": RISK_REGISTER_PROMPT,
        },
    )


def downgrade() -> None:
    pass
