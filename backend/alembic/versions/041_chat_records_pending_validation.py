"""Chat-saved Risk Register records wait for a person's validation.

The Risk Register chat marked the records it saved "RMP-Validated" on the
prompt's instruction. Validation is the SMS Manager's call, so chat-saved
records now start Pending, and the ones already marked are reset. SharePoint
SRMD imports keep their validated status: they come from signed reports.

Saved organization prompts carry the changed wording, so they are re-synced
from the code defaults the way migrations 030, 034, 035 and 040 did. The
downgrade restores neither the prompt text nor the prior validation status,
since a record a person has since confirmed cannot be told apart.

Revision ID: 041
Revises: 040
Create Date: 2026-10-21
"""

import sqlalchemy as sa

from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def _resync_prompts() -> None:
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


def upgrade() -> None:
    op.execute(
        "UPDATE risk_entries SET validation_status = 'pending' "
        "WHERE source = 'rmp_sp4' AND validation_status = 'rmp_validated'"
    )
    _resync_prompts()


def downgrade() -> None:
    pass
