"""Add VEXION POS terminal registry and subscription foundation."""
from alembic import op
import sqlalchemy as sa

revision = "0016_vexion_billing_foundation"
down_revision = "0015_business_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_pos_terminals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("pos_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_terminal_id", sa.String(180), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("branch_name", sa.String(160), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "external_terminal_id", name="uq_business_pos_terminal_external_id"),
    )
    op.create_index("ix_business_pos_terminals_business_id", "business_pos_terminals", ["business_id"])
    op.create_index("ix_business_pos_terminals_status", "business_pos_terminals", ["status"])

    op.create_table(
        "business_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="not_started"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default="499.00"),
        sa.Column("discounted_unit_price", sa.Numeric(10, 2), nullable=False, server_default="399.00"),
        sa.Column("active_pos_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("referral_discount_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payment_provider", sa.String(40), nullable=True),
        sa.Column("provider_customer_reference", sa.String(180), nullable=True),
        sa.Column("provider_subscription_reference", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", name="uq_business_subscription_business"),
    )
    op.create_index("ix_business_subscriptions_status", "business_subscriptions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_business_subscriptions_status", table_name="business_subscriptions")
    op.drop_table("business_subscriptions")
    op.drop_index("ix_business_pos_terminals_status", table_name="business_pos_terminals")
    op.drop_index("ix_business_pos_terminals_business_id", table_name="business_pos_terminals")
    op.drop_table("business_pos_terminals")
