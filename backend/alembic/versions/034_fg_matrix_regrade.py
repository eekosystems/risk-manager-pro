"""Re-grade five FG 5x5 cells and move the split cell from D1 to E1.

Faith Group asked for the on-screen matrix to change:
  A3, B3 : medium -> high   (Frequent / Probable + Major)
  C4     : low    -> medium (Remote + Minor)
  D3     : low    -> medium (Extremely Remote + Major)
  E1     : medium -> high   (Extremely Improbable + Catastrophic, now the
                             split cell; reported as High unless an
                             airport-specific matrix says otherwise)
  D1     : unchanged, high  (no longer rendered split)

Stored risk_level was stamped at insert time, so rows at those coordinates
carry the old band. Severity is stored 1=Minimal..5=Catastrophic, so the
coordinates below use stored severity (display 3 -> stored 3, display 4 ->
stored 2, display 1 -> stored 5).

Saved organization prompts embed the band table, so they are re-synced from
the code defaults the same way migration 030 did. As there, downgrade
restores the stored bands but not the prior prompt text.

Revision ID: 034
Revises: 033
Create Date: 2026-09-14
"""

import sqlalchemy as sa

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


_FORWARD: list[tuple[str, int, str]] = [
    ("A", 3, "high"),
    ("B", 3, "high"),
    ("C", 2, "medium"),
    ("D", 3, "medium"),
    ("E", 5, "high"),
]

_REVERSE: list[tuple[str, int, str]] = [
    ("A", 3, "medium"),
    ("B", 3, "medium"),
    ("C", 2, "low"),
    ("D", 3, "low"),
    ("E", 5, "medium"),
]


def _apply(rows: list[tuple[str, int, str]]) -> None:
    bind = op.get_bind()
    for likelihood, severity, level in rows:
        bind.execute(
            sa.text(
                "UPDATE risk_entries SET risk_level = :level "
                "WHERE likelihood = :likelihood AND severity = :severity"
            ),
            {"level": level, "likelihood": likelihood, "severity": severity},
        )


def _resync_prompts() -> None:
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


def upgrade() -> None:
    _apply(_FORWARD)
    _resync_prompts()


def downgrade() -> None:
    _apply(_REVERSE)
