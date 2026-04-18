"""Promote RMP Core Logic Prompt to v20260415.

Updates the four prompt fields composed from GENERAL_PROMPT
(`system_prompt`, `phl_prompt`, `sra_prompt`, `system_analysis_prompt`)
for every `organization_settings` row where category='prompts'. Values
are read from `app.services.prompts` at migration time, so the code
must already be on v20260415 when this migration runs (true for any
deployment that bundles this migration).

Leaves `document_interpretation_prompt` and `indexing_instructions`
untouched.

Downgrade is a no-op — the v20260402 text is not preserved here. To
revert, check out prompts.py at the prior revision and replay the
settings via the UI.

Revision ID: 019
Revises: 018
Create Date: 2026-04-18
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.prompts import (
        GENERAL_PROMPT,
        PHL_PROMPT,
        SRA_PROMPT,
        SYSTEM_ANALYSIS_PROMPT,
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE organization_settings "
            "SET settings_json = settings_json || jsonb_build_object("
            "    'system_prompt', CAST(:sys AS text), "
            "    'phl_prompt', CAST(:phl AS text), "
            "    'sra_prompt', CAST(:sra AS text), "
            "    'system_analysis_prompt', CAST(:sa AS text)"
            "), "
            "updated_at = NOW() "
            "WHERE category = 'prompts'"
        ),
        {
            "sys": GENERAL_PROMPT,
            "phl": PHL_PROMPT,
            "sra": SRA_PROMPT,
            "sa": SYSTEM_ANALYSIS_PROMPT,
        },
    )


def downgrade() -> None:
    # No-op: v20260402 text is not preserved in this migration.
    pass
