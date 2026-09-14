"""Re-grade FG 5x5 cell E3 from Low to Medium.

Faith Group asked for E3 (Extremely Improbable + Major) to read Medium,
matching the D3 change in migration 034. Stored risk_level was stamped at
insert time, so rows at that coordinate carry the old band. Severity is
stored 1=Minimal..5=Catastrophic; Major is 3 in both display and stored
order.

Saved organization prompts embed the band table, so they are re-synced from
the code defaults the same way migrations 030 and 034 did. As there,
downgrade restores the stored band but not the prior prompt text.

Revision ID: 035
Revises: 034
Create Date: 2026-09-14
"""

import sqlalchemy as sa

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def _set_band(level: str) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE risk_entries SET risk_level = :level "
            "WHERE likelihood = 'E' AND severity = 3"
        ),
        {"level": level},
    )


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
    _set_band("medium")
    _resync_prompts()


def downgrade() -> None:
    _set_band("low")
