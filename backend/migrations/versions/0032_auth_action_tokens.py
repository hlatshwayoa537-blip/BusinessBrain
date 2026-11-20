"""Add secure password reset tokens and access-token revocation."""

from alembic import op
import sqlalchemy as sa

revision = "0032_auth_action_tokens"
down_revision = "0031_pos_refund_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "user_action_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_action_tokens_token_hash"),
    )
    op.create_index("ix_user_action_tokens_user_id", "user_action_tokens", ["user_id"])
    op.create_index("ix_user_action_tokens_purpose", "user_action_tokens", ["purpose"])


def downgrade() -> None:
    op.drop_index("ix_user_action_tokens_purpose", table_name="user_action_tokens")
    op.drop_index("ix_user_action_tokens_user_id", table_name="user_action_tokens")
    op.drop_table("user_action_tokens")
    op.drop_column("users", "token_version")
