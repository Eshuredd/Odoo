"""Add authentication versions, reset tokens, and offline email outbox.

Revision ID: 0002_authentication
Revises: 0001_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_authentication"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Native ADD COLUMN preserves users and audit foreign keys; no users-table rebuild.
    op.add_column("users", sa.Column(
        "auth_version", sa.Integer(),
        sa.CheckConstraint("auth_version >= 0", name=op.f("ck_users_auth_version_nonnegative")),
        nullable=False, server_default=sa.text("0"),
    ))
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE",
                                name=op.f("fk_password_reset_tokens_user_id_users")),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_password_reset_tokens_user_id_consumed_at", "password_reset_tokens",
                    ["user_id", "consumed_at"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_email_outbox_created_at_id", "email_outbox", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_created_at_id", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id_consumed_at", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "auth_version")
