"""Persistent cache for SharePoint risk-outcome extractions.

Every container replica restart wiped the importer's in-memory cache,
forcing a full LLM re-extraction of every PDF in the library on the next
scan. That burst saturated the gpt-4o deployment's TPM quota and starved
concurrent user chat requests.

This table persists each per-file extraction so subsequent scans (across
restarts and replicas) can skip files whose drive_item_id + size +
content_type are unchanged on the current schema version.

Revision ID: 026
Revises: 025
Create Date: 2026-05-03
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_outcome_cache",
        sa.Column("drive_item_id", sa.String(length=255), primary_key=True),
        sa.Column("cache_key", sa.String(length=500), nullable=False),
        sa.Column("airport_identifier", sa.String(length=50), nullable=False),
        sa.Column("source_file", sa.String(length=500), nullable=False),
        sa.Column("risks_json", postgresql.JSONB, nullable=False),
        sa.Column("risks_flagged_json", postgresql.JSONB, nullable=False),
        sa.Column("notes_json", postgresql.JSONB, nullable=False),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_risk_outcome_cache_airport",
        "risk_outcome_cache",
        ["airport_identifier"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_outcome_cache_airport", table_name="risk_outcome_cache")
    op.drop_table("risk_outcome_cache")
