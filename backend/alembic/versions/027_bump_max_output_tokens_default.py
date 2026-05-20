"""Raise max_output_tokens to model maximum (16384) for existing orgs.

Bumps the `max_output_tokens` field to 16384 in every existing
`organization_settings` row where category='model'. Orgs that already had a
saved model settings row were stuck on the prior 4096 default because
`get_effective_model_config` reads the saved row before falling back to
DEFAULT_MODEL — so the schema default change alone didn't reach them.

The new value matches the GPT-4o output ceiling on Azure OpenAI and prevents
truncation of long, multi-scenario System Analysis and SRA outputs.

Downgrade restores the prior default (4096).

Revision ID: 027
Revises: 026
Create Date: 2026-05-20
"""

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE organization_settings "
            "SET settings_json = settings_json || jsonb_build_object("
            "    'max_output_tokens', 16384"
            "), "
            "updated_at = NOW() "
            "WHERE category = 'model'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE organization_settings "
            "SET settings_json = settings_json || jsonb_build_object("
            "    'max_output_tokens', 4096"
            "), "
            "updated_at = NOW() "
            "WHERE category = 'model'"
        )
    )
