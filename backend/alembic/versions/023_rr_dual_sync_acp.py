"""Dual Risk Register infrastructure — sync links, pending changes, ACP, closures.

Creates:
- `risk_record_links` — FG RR ↔ Client RR record pairs.
- `pending_sync_changes` — review queue for dual-record edits.
- `airport_context_profiles` — per-airport institutional memory (FG-scoped).
- `acp_intelligence_items` — external safety events requiring consultant review.
- `closure_approvals` — AE sign-off log for High/Extreme record closures.

Extends the `notificationtype` PG enum with sync / ACP / closure events.

Downgrade drops all new tables. Enum values are left in place (PG can't
safely remove them).

Revision ID: 023
Revises: 022
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


NEW_NOTIFICATION_VALUES = (
    "sync_pending_review",
    "acp_flag_raised",
    "closure_approval_requested",
    "closure_approval_decided",
)


def upgrade() -> None:
    # --- Extend notificationtype enum (must run outside a tx) ---
    with op.get_context().autocommit_block():
        for value in NEW_NOTIFICATION_VALUES:
            op.execute(
                f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{value}'"
            )

    # --- risk_record_links ---
    op.create_table(
        "risk_record_links",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fg_risk_entry_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "client_risk_entry_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("airport_identifier", sa.String(20), nullable=False, index=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="active"
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "fg_risk_entry_id", "client_risk_entry_id", name="uq_rr_link_pair"
        ),
    )

    # --- pending_sync_changes ---
    op.create_table(
        "pending_sync_changes",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "link_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_record_links.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "source_risk_entry_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_organization_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_organization_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("diff_json", JSONB, nullable=False),
        sa.Column(
            "initiator_user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )

    # --- airport_context_profiles ---
    op.create_table(
        "airport_context_profiles",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("airport_identifier", sa.String(20), nullable=False, index=True),
        sa.Column("system_profile", sa.Text(), nullable=True),
        sa.Column("known_risk_factors", sa.Text(), nullable=True),
        sa.Column("stakeholder_notes", sa.Text(), nullable=True),
        sa.Column("operational_impact_history", sa.Text(), nullable=True),
        sa.Column("extra_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "organization_id", "airport_identifier", name="uq_acp_per_airport"
        ),
    )

    # --- acp_intelligence_items ---
    op.create_table(
        "acp_intelligence_items",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "acp_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("airport_context_profiles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("airport_identifier", sa.String(20), nullable=False, index=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("external_url", sa.String(1000), nullable=True),
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "decision",
            sa.String(40),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column(
            "decided_by",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column(
            "linked_risk_entry_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )

    # --- closure_approvals ---
    op.create_table(
        "closure_approvals",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "risk_entry_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("risk_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("request_note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column(
            "approver_user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("closure_approvals")
    op.drop_table("acp_intelligence_items")
    op.drop_table("airport_context_profiles")
    op.drop_table("pending_sync_changes")
    op.drop_table("risk_record_links")
    # Note: notificationtype enum values are not removed (PG limitation).
