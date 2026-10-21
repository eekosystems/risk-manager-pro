"""Record disposition and the AE review requirement as fields.

The SRA's disposition ("Further mitigation or AE acceptance required") and
whether a record awaits Accountable Executive review lived only in the Notes
text, so nobody could filter for records awaiting AE review. Both are columns
now. The flag is backfilled from the bands: a High initial or residual risk
requires AE review.

Saved organization prompts list the record schema, so they are re-synced from
the code defaults the way migrations 030, 034 and 035 did. Downgrade drops the
columns but does not restore the prior prompt text.

Revision ID: 040
Revises: 039
Create Date: 2026-10-21
"""

import sqlalchemy as sa

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None

DISPOSITION = sa.Enum(
    "accept",
    "accept_with_conditions",
    "reject",
    "further_mitigation_required",
    name="disposition",
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
    DISPOSITION.create(op.get_bind(), checkfirst=True)
    op.add_column("risk_entries", sa.Column("disposition", DISPOSITION, nullable=True))
    op.add_column(
        "risk_entries",
        sa.Column(
            "ae_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "UPDATE risk_entries SET ae_review_required = TRUE "
        "WHERE risk_level = 'high' OR residual_risk_level = 'high'"
    )
    _resync_prompts()


def downgrade() -> None:
    op.drop_column("risk_entries", "ae_review_required")
    op.drop_column("risk_entries", "disposition")
    DISPOSITION.drop(op.get_bind(), checkfirst=True)
