"""Expand risk_entries + mitigations for Sub-Prompt 4 (Risk Register).

Adds the full Sub-Prompt 4 schema to `risk_entries`:
- airport_identifier, potential_credible_outcome, operational_domain,
  sub_location, hazard_category_5m, hazard_category_icao,
  risk_matrix_applied, existing_controls, residual_risk_level,
  record_status, validation_status, source, sync_status,
  acm_cross_reference, related_record_ids, audit_trail_json
- extends RiskLevel enum with 'extreme'

Adds `verification_method` to `mitigations`.

Creates `airport_sub_locations` table (per-airport sub-location library,
per-organization).

Backfills new fields on existing rows with safe defaults:
- risk_matrix_applied='faa_5x5'
- record_status derived from legacy status (open/mitigating→in_progress,
  closed→closed, accepted→monitoring)
- validation_status='pending'
- source='manual_entry'
- sync_status='fg_only'

Downgrade removes all new columns and the sub-location table. It does
NOT attempt to remove the 'extreme' enum value from risklevel (PG can't
drop enum values cleanly).

Revision ID: 022
Revises: 021
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


OPERATIONAL_DOMAIN_VALUES = (
    "movement_area",
    "non_movement_area",
    "ramp",
    "terminal",
    "landside",
    "user_defined",
)
HAZARD_5M_VALUES = ("human", "machine", "medium", "mission", "management")
HAZARD_ICAO_VALUES = ("technical", "human", "organizational", "environmental")
RISK_MATRIX_APPLIED_VALUES = ("airport_specific", "faa_5x5", "conservative_default")
RECORD_STATUS_VALUES = ("open", "in_progress", "pending_assessment", "closed", "monitoring")
VALIDATION_STATUS_VALUES = ("rmp_validated", "user_reported", "pending")
RECORD_SOURCE_VALUES = (
    "rmp_sp1",
    "rmp_sp2",
    "rmp_sp3",
    "rmp_sp4",
    "manual_entry",
    "fg_push",
    "client_push",
)
SYNC_STATUS_VALUES = ("fg_only", "client_only", "dual_in_sync", "dual_pending")


def upgrade() -> None:
    # --- Extend risklevel enum with 'extreme' (must run outside a tx block) ---
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'extreme'")

    # --- Create new enum types ---
    op.execute(
        "CREATE TYPE operationaldomain AS ENUM "
        f"({', '.join(repr(v) for v in OPERATIONAL_DOMAIN_VALUES)})"
    )
    op.execute(
        "CREATE TYPE hazardcategory5m AS ENUM "
        f"({', '.join(repr(v) for v in HAZARD_5M_VALUES)})"
    )
    op.execute(
        "CREATE TYPE hazardcategoryicao AS ENUM "
        f"({', '.join(repr(v) for v in HAZARD_ICAO_VALUES)})"
    )
    op.execute(
        "CREATE TYPE riskmatrixapplied AS ENUM "
        f"({', '.join(repr(v) for v in RISK_MATRIX_APPLIED_VALUES)})"
    )
    op.execute(
        "CREATE TYPE recordstatus AS ENUM "
        f"({', '.join(repr(v) for v in RECORD_STATUS_VALUES)})"
    )
    op.execute(
        "CREATE TYPE validationstatus AS ENUM "
        f"({', '.join(repr(v) for v in VALIDATION_STATUS_VALUES)})"
    )
    op.execute(
        "CREATE TYPE recordsource AS ENUM "
        f"({', '.join(repr(v) for v in RECORD_SOURCE_VALUES)})"
    )
    op.execute(
        "CREATE TYPE syncstatus AS ENUM "
        f"({', '.join(repr(v) for v in SYNC_STATUS_VALUES)})"
    )

    # --- Add columns to risk_entries ---
    op.add_column(
        "risk_entries", sa.Column("airport_identifier", sa.String(20), nullable=True)
    )
    op.create_index(
        "ix_risk_entries_airport_identifier",
        "risk_entries",
        ["airport_identifier"],
    )
    op.add_column(
        "risk_entries",
        sa.Column("potential_credible_outcome", sa.Text(), nullable=True),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "operational_domain",
            sa.Enum(*OPERATIONAL_DOMAIN_VALUES, name="operationaldomain"),
            nullable=True,
        ),
    )
    op.add_column(
        "risk_entries", sa.Column("sub_location", sa.String(255), nullable=True)
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "hazard_category_5m",
            sa.Enum(*HAZARD_5M_VALUES, name="hazardcategory5m"),
            nullable=True,
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "hazard_category_icao",
            sa.Enum(*HAZARD_ICAO_VALUES, name="hazardcategoryicao"),
            nullable=True,
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "risk_matrix_applied",
            sa.Enum(*RISK_MATRIX_APPLIED_VALUES, name="riskmatrixapplied"),
            nullable=False,
            server_default="faa_5x5",
        ),
    )
    op.add_column("risk_entries", sa.Column("existing_controls", sa.Text(), nullable=True))
    op.add_column(
        "risk_entries",
        sa.Column(
            "residual_risk_level",
            sa.Enum("low", "medium", "high", "extreme", name="risklevel"),
            nullable=True,
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "record_status",
            sa.Enum(*RECORD_STATUS_VALUES, name="recordstatus"),
            nullable=False,
            server_default="open",
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "validation_status",
            sa.Enum(*VALIDATION_STATUS_VALUES, name="validationstatus"),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "source",
            sa.Enum(*RECORD_SOURCE_VALUES, name="recordsource"),
            nullable=False,
            server_default="manual_entry",
        ),
    )
    op.add_column(
        "risk_entries",
        sa.Column(
            "sync_status",
            sa.Enum(*SYNC_STATUS_VALUES, name="syncstatus"),
            nullable=False,
            server_default="fg_only",
        ),
    )
    op.add_column(
        "risk_entries", sa.Column("acm_cross_reference", sa.Text(), nullable=True)
    )
    op.add_column(
        "risk_entries",
        sa.Column("related_record_ids", ARRAY(PG_UUID(as_uuid=True)), nullable=True),
    )
    op.add_column(
        "risk_entries", sa.Column("audit_trail_json", JSONB, nullable=True)
    )

    # --- Backfill record_status from legacy status column ---
    op.execute(
        """
        UPDATE risk_entries
        SET record_status = CASE status
            WHEN 'open' THEN 'open'::recordstatus
            WHEN 'mitigating' THEN 'in_progress'::recordstatus
            WHEN 'closed' THEN 'closed'::recordstatus
            WHEN 'accepted' THEN 'monitoring'::recordstatus
            ELSE 'open'::recordstatus
        END
        """
    )

    # --- Extend mitigations ---
    op.add_column(
        "mitigations", sa.Column("verification_method", sa.Text(), nullable=True)
    )

    # --- Create airport_sub_locations table ---
    op.create_table(
        "airport_sub_locations",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("airport_identifier", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "airport_identifier",
            "name",
            name="uq_airport_sub_location",
        ),
    )


def downgrade() -> None:
    # --- Drop airport_sub_locations ---
    op.drop_table("airport_sub_locations")

    # --- Mitigations ---
    op.drop_column("mitigations", "verification_method")

    # --- risk_entries columns (reverse order) ---
    op.drop_column("risk_entries", "audit_trail_json")
    op.drop_column("risk_entries", "related_record_ids")
    op.drop_column("risk_entries", "acm_cross_reference")
    op.drop_column("risk_entries", "sync_status")
    op.drop_column("risk_entries", "source")
    op.drop_column("risk_entries", "validation_status")
    op.drop_column("risk_entries", "record_status")
    op.drop_column("risk_entries", "residual_risk_level")
    op.drop_column("risk_entries", "existing_controls")
    op.drop_column("risk_entries", "risk_matrix_applied")
    op.drop_column("risk_entries", "hazard_category_icao")
    op.drop_column("risk_entries", "hazard_category_5m")
    op.drop_column("risk_entries", "sub_location")
    op.drop_column("risk_entries", "operational_domain")
    op.drop_column("risk_entries", "potential_credible_outcome")
    op.drop_index("ix_risk_entries_airport_identifier", "risk_entries")
    op.drop_column("risk_entries", "airport_identifier")

    # --- Drop new enum types ---
    op.execute("DROP TYPE IF EXISTS syncstatus")
    op.execute("DROP TYPE IF EXISTS recordsource")
    op.execute("DROP TYPE IF EXISTS validationstatus")
    op.execute("DROP TYPE IF EXISTS recordstatus")
    op.execute("DROP TYPE IF EXISTS riskmatrixapplied")
    op.execute("DROP TYPE IF EXISTS hazardcategoryicao")
    op.execute("DROP TYPE IF EXISTS hazardcategory5m")
    op.execute("DROP TYPE IF EXISTS operationaldomain")
    # Note: 'extreme' cannot be safely removed from risklevel. Rows using it
    # must be updated or deleted manually before rolling back application code.
