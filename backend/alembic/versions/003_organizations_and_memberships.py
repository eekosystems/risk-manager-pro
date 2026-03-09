"""Add organizations, memberships, and migrate from tenant_id

Revision ID: 003
Revises: 002
Create Date: 2026-03-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "archived", name="organizationstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("is_platform", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("settings_json", JSONB, nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # 2. Create organization_memberships table
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "role",
            sa.Enum("org_admin", "analyst", "viewer", name="membershiprole"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("invited_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
    )

    # 3. Data migration: create organizations from distinct tenant_ids in users
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, status, is_platform)
        SELECT DISTINCT tenant_id, 'Organization ' || ROW_NUMBER() OVER (ORDER BY tenant_id),
               'org-' || SUBSTRING(tenant_id::text, 1, 8), 'active', false
        FROM users
        WHERE tenant_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # 4. Data migration: create memberships from users
    role_mapping = """
        INSERT INTO organization_memberships (id, user_id, organization_id, role, is_active)
        SELECT gen_random_uuid(), id, tenant_id,
               CASE role
                   WHEN 'admin' THEN 'org_admin'::membershiprole
                   WHEN 'analyst' THEN 'analyst'::membershiprole
                   WHEN 'viewer' THEN 'viewer'::membershiprole
                   ELSE 'viewer'::membershiprole
               END,
               true
        FROM users
        WHERE tenant_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """
    op.execute(role_mapping)

    # 5. Add organization_id to conversations, copy from tenant_id, then add FK
    op.add_column("conversations", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE conversations SET organization_id = tenant_id")
    op.alter_column("conversations", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_conversations_organization_id",
        "conversations",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.drop_index("ix_conversations_tenant_id", "conversations")
    op.drop_column("conversations", "tenant_id")

    # 6. Add organization_id to documents, copy from tenant_id, then add FK
    op.add_column("documents", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE documents SET organization_id = tenant_id")
    op.alter_column("documents", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_organization_id",
        "documents",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.drop_index("ix_documents_tenant_id", "documents")
    op.drop_column("documents", "tenant_id")

    # 7. Add organization_id to audit_log (nullable FK)
    op.add_column(
        "audit_log",
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_audit_log_organization_id", "audit_log", ["organization_id"])

    # 8. Add is_platform_admin to users
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default="false"),
    )

    # 9. Drop tenant_id and role from users
    op.drop_index("ix_users_tenant_id", "users")
    op.drop_column("users", "tenant_id")
    op.drop_column("users", "role")

    # 10. Drop userrole enum type
    op.execute("DROP TYPE IF EXISTS userrole")


def downgrade() -> None:
    # Re-add role and tenant_id to users
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'analyst', 'viewer')")
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum("admin", "analyst", "viewer", name="userrole"),
            nullable=False,
            server_default="viewer",
        ),
    )
    op.add_column("users", sa.Column("tenant_id", sa.Uuid(), nullable=True))

    # Restore tenant_id and role from memberships
    op.execute(
        """
        UPDATE users SET
            tenant_id = om.organization_id,
            role = CASE om.role
                WHEN 'org_admin' THEN 'admin'::userrole
                WHEN 'analyst' THEN 'analyst'::userrole
                WHEN 'viewer' THEN 'viewer'::userrole
            END
        FROM organization_memberships om
        WHERE om.user_id = users.id
        """
    )
    op.alter_column("users", "tenant_id", nullable=False)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # Drop is_platform_admin
    op.drop_column("users", "is_platform_admin")

    # Drop org FK from audit_log
    op.drop_index("ix_audit_log_organization_id", "audit_log")
    op.drop_column("audit_log", "organization_id")

    # Re-add tenant_id to documents
    op.add_column("documents", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE documents SET tenant_id = organization_id")
    op.alter_column("documents", "tenant_id", nullable=False)
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.drop_constraint("fk_documents_organization_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_organization_id", "documents")
    op.drop_column("documents", "organization_id")

    # Re-add tenant_id to conversations
    op.add_column("conversations", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE conversations SET tenant_id = organization_id")
    op.alter_column("conversations", "tenant_id", nullable=False)
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.drop_constraint("fk_conversations_organization_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_organization_id", "conversations")
    op.drop_column("conversations", "organization_id")

    # Drop memberships and organizations
    op.drop_table("organization_memberships")
    op.execute("DROP TYPE IF EXISTS membershiprole")
    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS organizationstatus")
