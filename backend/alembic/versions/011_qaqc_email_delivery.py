"""Extend QA/QC notifications: new trigger types + delivery log.

Revision ID: 011
Revises: 010
Create Date: 2026-04-12
"""

import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'risk_updated'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'mitigation_created'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'document_indexed'")

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deliverychannel AS ENUM ('in_app', 'email');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deliverystatus AS ENUM ('pending', 'sent', 'failed', 'skipped');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "notification_delivery_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "notification_id",
            sa.Uuid(),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "channel",
            sa.Enum("in_app", "email", name="deliverychannel", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "sent",
                "failed",
                "skipped",
                name="deliverystatus",
                create_type=False,
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_notification_delivery_log_status_attempted",
        "notification_delivery_log",
        ["status", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_delivery_log_status_attempted",
        table_name="notification_delivery_log",
    )
    op.drop_table("notification_delivery_log")
    sa.Enum(name="deliverystatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="deliverychannel").drop(op.get_bind(), checkfirst=True)
