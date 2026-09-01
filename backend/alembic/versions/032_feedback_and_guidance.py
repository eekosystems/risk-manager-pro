"""User feedback on outputs, and the curated guidance it can be promoted into.

The application had no memory beyond a conversation's own history, so a
correction a user made in one session was gone the next. This adds two tables:
message_feedback captures what users say about an output, and
application_guidance holds the rules a platform admin promotes that feedback
into. Active guidance is injected into the system prompt on every matching
answer, so an approved rule takes effect immediately and stays revocable.

Revision ID: 032
Revises: 031
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None

# Two forms of each enum. The create_type=False variants are what the table
# definitions reference: without that flag op.create_table emits its own
# CREATE TYPE on top of the explicit one below, and the second statement fails
# with "type already exists".
_ENUM_VALUES = {
    "feedbackrating": ("helpful", "not_helpful"),
    "feedbackstatus": ("new", "reviewed", "promoted", "dismissed"),
    "guidancescope": ("global", "organization"),
}

FEEDBACK_RATING = postgresql.ENUM(
    *_ENUM_VALUES["feedbackrating"], name="feedbackrating", create_type=False
)
FEEDBACK_STATUS = postgresql.ENUM(
    *_ENUM_VALUES["feedbackstatus"], name="feedbackstatus", create_type=False
)
GUIDANCE_SCOPE = postgresql.ENUM(
    *_ENUM_VALUES["guidancescope"], name="guidancescope", create_type=False
)
FUNCTION_TYPE = postgresql.ENUM(
    "phl", "sra", "system", "general", "risk_register",
    name="functiontype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in _ENUM_VALUES.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "message_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("rating", FEEDBACK_RATING, nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", FEEDBACK_STATUS, nullable=False, server_default="new"),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("review_note", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_message_feedback_organization_id", "message_feedback", ["organization_id"])
    op.create_index("ix_message_feedback_conversation_id", "message_feedback", ["conversation_id"])
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_index("ix_message_feedback_submitted_by", "message_feedback", ["submitted_by"])
    op.create_index("ix_message_feedback_status", "message_feedback", ["status"])
    op.create_index("ix_message_feedback_created_at", "message_feedback", ["created_at"])

    op.create_table(
        "application_guidance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("scope", GUIDANCE_SCOPE, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("function_type", FUNCTION_TYPE, nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "source_feedback_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message_feedback.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_application_guidance_scope", "application_guidance", ["scope"])
    op.create_index(
        "ix_application_guidance_organization_id", "application_guidance", ["organization_id"]
    )
    op.create_index(
        "ix_application_guidance_function_type", "application_guidance", ["function_type"]
    )
    op.create_index("ix_application_guidance_is_active", "application_guidance", ["is_active"])


def downgrade() -> None:
    op.drop_table("application_guidance")
    op.drop_table("message_feedback")
    bind = op.get_bind()
    for name, values in _ENUM_VALUES.items():
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
