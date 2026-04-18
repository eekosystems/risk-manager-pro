"""Seed `risk_register_prompt` field on every saved prompts row.

Sub-Prompt 4 (Risk Register / Hazard Management Module) is now a
first-class editable prompt. `PromptsPayload` requires this field to
be present, so every existing `organization_settings` row where
category='prompts' must have it backfilled to avoid validation errors
on load.

This migration reads the current RISK_REGISTER_PROMPT default from
`app.services.prompts` and sets it on every row that lacks the field.
Rows that already contain a value (e.g., a human has already edited
the prompt) are left alone.

Downgrade removes the field from saved rows so the schema stays
consistent if you roll back application code.

Revision ID: 020
Revises: 019
Create Date: 2026-04-18
"""

import sqlalchemy as sa

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.prompts import RISK_REGISTER_PROMPT

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE organization_settings "
            "SET settings_json = settings_json || jsonb_build_object("
            "    'risk_register_prompt', CAST(:rr AS text)"
            "), "
            "updated_at = NOW() "
            "WHERE category = 'prompts' "
            "  AND NOT (settings_json ? 'risk_register_prompt')"
        ),
        {"rr": RISK_REGISTER_PROMPT},
    )


def downgrade() -> None:
    op.execute(
        "UPDATE organization_settings "
        "SET settings_json = settings_json - 'risk_register_prompt', "
        "    updated_at = NOW() "
        "WHERE category = 'prompts' "
        "  AND settings_json ? 'risk_register_prompt'"
    )
