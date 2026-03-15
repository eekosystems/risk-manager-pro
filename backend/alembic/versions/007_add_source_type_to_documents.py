"""Add source_type to documents table.

Revision ID: 007
Revises: 006
Create Date: 2026-03-15
"""

import sqlalchemy as sa

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

_source_type_enum = sa.Enum(
    "client", "faa", "icao", "easa", "nasa_asrs", "internal",
    name="sourcetype",
)


def upgrade() -> None:
    _source_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "source_type",
            _source_type_enum,
            nullable=False,
            server_default="client",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "source_type")
    _source_type_enum.drop(op.get_bind(), checkfirst=True)
