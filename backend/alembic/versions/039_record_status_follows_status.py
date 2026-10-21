"""Bring record_status back in step with the legacy status field.

Adding a mitigation moved a hazard's legacy `status` to Mitigating but left
`record_status` at Open, and the SRMD import wrote the two apart on purpose.
The register list shows one field and the detail view the other, so the same
hazard read "Mitigating" in one place and "Open" in the other. The service
now moves both together; this re-grades the rows written before it did.

Revision ID: 039
Revises: 038
Create Date: 2026-10-20
"""

from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE risk_entries SET record_status = 'in_progress' "
        "WHERE status = 'mitigating' AND record_status = 'open'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE risk_entries SET record_status = 'open' "
        "WHERE status = 'mitigating' AND record_status = 'in_progress'"
    )
