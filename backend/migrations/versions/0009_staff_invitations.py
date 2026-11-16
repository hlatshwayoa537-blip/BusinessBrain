"""Add staff invitations and membership administration."""
from alembic import op
import sqlalchemy as sa

revision = "0009_staff_invites"
down_revision = "0008_recruitment"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_staff_invitations_business_id", "staff_invitations", ["business_id"])
    op.create_index("ix_staff_invitations_email", "staff_invitations", ["email"])

def downgrade() -> None:
    op.drop_index("ix_staff_invitations_email", table_name="staff_invitations")
    op.drop_index("ix_staff_invitations_business_id", table_name="staff_invitations")
    op.drop_table("staff_invitations")
