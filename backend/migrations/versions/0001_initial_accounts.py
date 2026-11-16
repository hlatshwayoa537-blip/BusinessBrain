"""Create users, businesses and business memberships."""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial_accounts"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("full_name", sa.String(160), nullable=False), sa.Column("password_hash", sa.String(512), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("businesses", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("industry", sa.String(120), nullable=False), sa.Column("country", sa.String(2), nullable=False, server_default="ZA"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("business_memberships", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(30), nullable=False, server_default="owner"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "business_id", name="uq_user_business_membership"))
    op.create_index("ix_business_memberships_user_id", "business_memberships", ["user_id"])
    op.create_index("ix_business_memberships_business_id", "business_memberships", ["business_id"])

def downgrade() -> None:
    op.drop_index("ix_business_memberships_business_id", table_name="business_memberships")
    op.drop_index("ix_business_memberships_user_id", table_name="business_memberships")
    op.drop_table("business_memberships")
    op.drop_table("businesses")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
