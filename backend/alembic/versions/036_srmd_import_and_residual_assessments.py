"""Store SharePoint SRMD hazards as risk entries and track residual re-assessments.

The Risk Register showed SRMD hazards straight from the extraction cache, so
they could not carry editable mitigations. They are now imported as risk
entries: `srmd_ref` keys each (airport, hazard) so a re-import never
duplicates, and the source report's name and link are kept. The residual is
stored as a matrix cell (`residual_severity` / `residual_likelihood`)
alongside the existing band.

`residual_assessments` holds each SP3 re-assessment run after a mitigation
change. A run only proposes a residual; an authorized user confirms it
before the record changes.

Downgrade maps imported entries' source back to 'manual_entry' so the enum
value can be dropped; the SRMD provenance columns are removed with it.

Revision ID: 036
Revises: 035
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None

_RECORD_SOURCES_BEFORE = (
    "rmp_sp1",
    "rmp_sp2",
    "rmp_sp3",
    "rmp_sp4",
    "manual_entry",
    "fg_push",
    "client_push",
)
_ASSESSMENT_STATUSES = ("pending", "proposed", "confirmed", "dismissed", "failed", "superseded")


def upgrade() -> None:
    op.execute("ALTER TYPE recordsource ADD VALUE IF NOT EXISTS 'sharepoint_srmd'")

    op.add_column("risk_entries", sa.Column("residual_severity", sa.Integer(), nullable=True))
    op.add_column(
        "risk_entries", sa.Column("residual_likelihood", sa.String(length=1), nullable=True)
    )
    op.add_column("risk_entries", sa.Column("srmd_ref", sa.String(length=64), nullable=True))
    op.add_column(
        "risk_entries", sa.Column("source_document_name", sa.String(length=500), nullable=True)
    )
    op.add_column("risk_entries", sa.Column("source_document_url", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_risk_entries_org_srmd_ref", "risk_entries", ["organization_id", "srmd_ref"]
    )

    status_enum = postgresql.ENUM(*_ASSESSMENT_STATUSES, name="residualassessmentstatus")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "residual_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "risk_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="residualassessmentstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column(
            "requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("residual_severity", sa.Integer(), nullable=True),
        sa.Column("residual_likelihood", sa.String(length=1), nullable=True),
        sa.Column(
            "residual_risk_level",
            postgresql.ENUM(name="risklevel", create_type=False),
            nullable=True,
        ),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index(
        "ix_residual_assessments_organization_id", "residual_assessments", ["organization_id"]
    )
    op.create_index(
        "ix_residual_assessments_risk_entry_id", "residual_assessments", ["risk_entry_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_residual_assessments_risk_entry_id", table_name="residual_assessments")
    op.drop_index("ix_residual_assessments_organization_id", table_name="residual_assessments")
    op.drop_table("residual_assessments")
    op.execute("DROP TYPE IF EXISTS residualassessmentstatus")

    op.drop_constraint("uq_risk_entries_org_srmd_ref", "risk_entries", type_="unique")
    op.drop_column("risk_entries", "source_document_url")
    op.drop_column("risk_entries", "source_document_name")
    op.drop_column("risk_entries", "srmd_ref")
    op.drop_column("risk_entries", "residual_likelihood")
    op.drop_column("risk_entries", "residual_severity")

    op.execute("UPDATE risk_entries SET source = 'manual_entry' WHERE source = 'sharepoint_srmd'")
    op.execute("ALTER TYPE recordsource RENAME TO recordsource_old")
    op.execute(
        f"CREATE TYPE recordsource AS ENUM ({', '.join(repr(v) for v in _RECORD_SOURCES_BEFORE)})"
    )
    op.execute("ALTER TABLE risk_entries ALTER COLUMN source DROP DEFAULT")
    op.execute(
        "ALTER TABLE risk_entries ALTER COLUMN source TYPE recordsource "
        "USING source::text::recordsource"
    )
    op.execute("ALTER TABLE risk_entries ALTER COLUMN source SET DEFAULT 'manual_entry'")
    op.execute("DROP TYPE recordsource_old")
