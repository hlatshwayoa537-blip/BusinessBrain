"""Persist PayFast subscription payment attempts and verified transactions."""
import sqlalchemy as sa
from alembic import op

revision = "0030_payfast_payments"
down_revision = "0029_customer_receivables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payfast_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("business_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("m_payment_id", sa.String(80), nullable=False),
        sa.Column("pf_payment_id", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("terminal_count", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("referral_discount_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("provider_subscription_token", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("m_payment_id", name="uq_payfast_payment_reference"),
        sa.UniqueConstraint("pf_payment_id", name="uq_payfast_provider_payment"),
    )
    op.create_index("ix_payfast_payments_business_id", "payfast_payments", ["business_id"])
    op.create_index("ix_payfast_payments_subscription_id", "payfast_payments", ["subscription_id"])
    op.create_index("ix_payfast_payments_status", "payfast_payments", ["status"])


def downgrade() -> None:
    op.drop_table("payfast_payments")
