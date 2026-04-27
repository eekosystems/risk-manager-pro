"""Recompute stored risk_level for cells whose color changed in the FG matrix.

Five matrix cells were re-graded to match Faith Group's published 5x5:
  A3, B3   :  high   -> medium
  C4, D3, E2 : medium -> low

Existing risk_entries.risk_level was stamped at insert time via the old
matrix, so rows at those coordinates carry stale color labels even though
the live matrix display picks the right color from the lookup table.

This migration realigns the stored value with the new matrix. Severity
remains stored as 1=Minimal..5=Catastrophic per migration 017, so the
coordinates below use stored severity.

Revision ID: 024
Revises: 023
Create Date: 2026-04-27
"""

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


_FORWARD: list[tuple[str, int, str]] = [
    ("A", 3, "medium"),
    ("B", 3, "medium"),
    ("C", 2, "low"),
    ("D", 3, "low"),
    ("E", 4, "low"),
]

_REVERSE: list[tuple[str, int, str]] = [
    ("A", 3, "high"),
    ("B", 3, "high"),
    ("C", 2, "medium"),
    ("D", 3, "medium"),
    ("E", 4, "medium"),
]


def _apply(rows: list[tuple[str, int, str]]) -> None:
    for likelihood, severity, level in rows:
        op.execute(
            f"UPDATE risk_entries SET risk_level = '{level}' "
            f"WHERE likelihood = '{likelihood}' AND severity = {severity}"
        )


def upgrade() -> None:
    _apply(_FORWARD)


def downgrade() -> None:
    _apply(_REVERSE)
