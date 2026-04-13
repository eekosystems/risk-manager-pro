"""Drop 'serious' from risklevel enum and remap existing rows to 'high'.

Revision ID: 013
Revises: 012
Create Date: 2026-04-12
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SELECT pg_advisory_xact_lock(hashtext('risklevel_enum_migration'))")
    op.execute("UPDATE risk_entries SET risk_level = 'high' WHERE risk_level = 'serious'")
    op.execute("ALTER TYPE risklevel RENAME TO risklevel_old")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high')")
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN risk_level TYPE risklevel "
        "USING risk_level::text::risklevel"
    )
    op.execute("DROP TYPE risklevel_old")


def downgrade() -> None:
    op.execute("SELECT pg_advisory_xact_lock(hashtext('risklevel_enum_migration'))")
    op.execute("ALTER TYPE risklevel RENAME TO risklevel_old")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'serious', 'high')")
    op.execute(
        "ALTER TABLE risk_entries "
        "ALTER COLUMN risk_level TYPE risklevel "
        "USING risk_level::text::risklevel"
    )
    op.execute("DROP TYPE risklevel_old")
