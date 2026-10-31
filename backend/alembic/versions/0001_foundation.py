"""Create foundational users and audit logs.

Revision ID: 0001_foundation
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(320, collation="NOCASE"), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.Enum(
            "admin", "staff", "customer", name="user_role",
            native_enum=False, create_constraint=True,
        ), nullable=False),
        sa.Column("is_active", sa.Boolean(create_constraint=True, name="user_is_active"),
                  nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL",
                                name=op.f("fk_audit_logs_actor_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_entity_entity_id", "audit_logs", ["entity", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("users")
