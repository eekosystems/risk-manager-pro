"""Make audit_log append-only (tamper-resistant).

Enforces SOC 2 CC7.2/CC7.3 at the database layer: audit records may be
inserted and read, but never updated, deleted, or truncated. A BEFORE
trigger raises on any UPDATE/DELETE/TRUNCATE regardless of the connecting
role (including the table owner), and UPDATE/DELETE/TRUNCATE are additionally
revoked from PUBLIC as defence in depth.

The application only ever INSERTs and SELECTs audit_log, so this changes no
runtime behaviour — it removes a capability nothing uses.

Revision ID: 028
Revises: 027
Create Date: 2026-05-26
"""

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_truncate
            BEFORE TRUNCATE ON audit_log
            FOR EACH STATEMENT EXECUTE FUNCTION audit_log_prevent_mutation();
        """
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_prevent_mutation();")
