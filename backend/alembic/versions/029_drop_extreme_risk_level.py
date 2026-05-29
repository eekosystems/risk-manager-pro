"""Drop 'extreme' from risklevel enum and remap existing rows to 'high'.

The FG 5x5 matrix only ever produces low/medium/high; 'extreme' was added in
022 to hold externally-supplied values (imported SRMDs, AI output) but it has
no matrix cell and contradicts the canonical three-tier scale. This migration
collapses the scale back to low/medium/high.

Remaps both enum columns on risk_entries (risk_level, residual_risk_level)
from 'extreme' to 'high', drops any 'extreme' alert-threshold config rows
(the risk_alert_thresholds.risk_level column is a free-form string with a
unique (organization_id, risk_level) constraint, so a straight remap could
collide with an existing 'high' row — those rows are deleted instead), then
rebuilds the risklevel enum type without 'extreme'.

Downgrade re-adds 'extreme' to the enum shape but cannot restore remapped
data — rows downgraded to 'high' stay 'high' (consistent with migration 013).

Revision ID: 029
Revises: 028
Create Date: 2026-05-28
"""

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SELECT pg_advisory_xact_lock(hashtext('risklevel_enum_migration'))")
    op.execute("UPDATE risk_entries SET risk_level = 'high' WHERE risk_level = 'extreme'")
    op.execute(
        "UPDATE risk_entries SET residual_risk_level = 'high' "
        "WHERE residual_risk_level = 'extreme'"
    )
    op.execute("DELETE FROM risk_alert_thresholds WHERE risk_level = 'extreme'")
    op.execute("ALTER TYPE risklevel RENAME TO risklevel_old")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high')")
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN risk_level TYPE risklevel "
        "USING risk_level::text::risklevel"
    )
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN residual_risk_level TYPE risklevel "
        "USING residual_risk_level::text::risklevel"
    )
    op.execute("DROP TYPE risklevel_old")


def downgrade() -> None:
    op.execute("SELECT pg_advisory_xact_lock(hashtext('risklevel_enum_migration'))")
    op.execute("ALTER TYPE risklevel RENAME TO risklevel_old")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high', 'extreme')")
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN risk_level TYPE risklevel "
        "USING risk_level::text::risklevel"
    )
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN residual_risk_level TYPE risklevel "
        "USING residual_risk_level::text::risklevel"
    )
    op.execute("DROP TYPE risklevel_old")
