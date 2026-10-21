"""Store audit timestamps with their UTC offset.

`audit_log.timestamp` was a timestamp without time zone, so the API served
it with no offset and the audit page showed the UTC value as if it were
local time, unlabeled. The column now carries the offset. Existing values
were written by `now()` on a UTC server, so they are read as UTC.

Revision ID: 042
Revises: 041
Create Date: 2026-10-21
"""

from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN timestamp TYPE TIMESTAMP WITH TIME ZONE "
        "USING timestamp AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN timestamp TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING timestamp AT TIME ZONE 'UTC'"
    )
