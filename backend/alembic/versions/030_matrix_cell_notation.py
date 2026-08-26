"""Repoint saved prompts at likelihood-letter / severity-number cell notation.

Risk scores are now written the way the Risk Register matrix reads: likelihood
is the row LETTER (A-Frequent … E-Extremely Improbable), severity is the column
NUMBER (1-Catastrophic … 5-Minimal), and the cell label is letter-then-number
("C2"). The prompt defaults in `app.services.prompts` carry that notation, and
`rr_tools._display_severity_to_stored` inverts the reported severity into the
stored scale (1=Minimal … 5=Catastrophic) when a record is saved.

An organization with a saved `prompts` row does not read those defaults — it
reads its own copy, which still describes severity as a LETTER A-E. Its model
therefore reports severity on the old scale while the tool boundary inverts on
the new one, and a Catastrophic hazard lands in the Minimal corner of the
matrix. This migration brings every saved row onto the new notation so both
sides of that boundary agree.

Updates the four fields composed from GENERAL_PROMPT (`system_prompt`,
`phl_prompt`, `sra_prompt`, `system_analysis_prompt`) plus
`risk_register_prompt`, for every `organization_settings` row where
category='prompts'. Values are read from `app.services.prompts` at migration
time, so the code must already carry the new notation when this runs (true for
any deployment that bundles this migration).

Leaves `document_interpretation_prompt` and `indexing_instructions` untouched —
neither describes matrix notation.

Locally edited prompts are overwritten. That is deliberate: a saved row on the
old notation is precisely the condition that misplaces records, so leaving edits
in place would leave the defect in place. Capture any customizations before
upgrading and reapply them via the Settings UI.

Downgrade is a no-op — the prior text is not preserved here. To revert, check
out prompts.py at the prior revision and replay the settings via the UI.

Revision ID: 030
Revises: 029
Create Date: 2026-08-26
"""

import sqlalchemy as sa

from alembic import op

revision = "030"
down_revision = "029"
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

    bind = op.get_bind()
    bind.execute(
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
    """No-op — the prior prompt text is not preserved."""
