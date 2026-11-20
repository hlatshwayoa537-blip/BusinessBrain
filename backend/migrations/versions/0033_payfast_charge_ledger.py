"""Record recurring PayFast charges and index subscription tokens."""

from alembic import op
import sqlalchemy as sa

revision = "0033_payfast_charge_ledger"
down_revision = "0032_auth_action_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_business_subscriptions_provider_subscription_reference",
        "business_subscriptions",
        ["provider_subscription_reference"],
    )
    op.create_table(
        "payfast_charges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("business_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("m_payment_id", sa.String(length=100), nullable=True),
        sa.Column("pf_payment_id", sa.String(length=100), nullable=False),
        sa.Column("provider_subscription_token", sa.String(length=36), nullable=False),
        sa.Column("payment_status", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["business_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pf_payment_id", "payment_status", name="uq_payfast_charge_provider_event"),
    )
    op.create_index("ix_payfast_charges_business_id", "payfast_charges", ["business_id"])
    op.create_index("ix_payfast_charges_subscription_id", "payfast_charges", ["subscription_id"])
    op.create_index("ix_payfast_charges_m_payment_id", "payfast_charges", ["m_payment_id"])
    op.create_index("ix_payfast_charges_provider_subscription_token", "payfast_charges", ["provider_subscription_token"])


def downgrade() -> None:
    op.drop_index("ix_payfast_charges_provider_subscription_token", table_name="payfast_charges")
    op.drop_index("ix_payfast_charges_m_payment_id", table_name="payfast_charges")
    op.drop_index("ix_payfast_charges_subscription_id", table_name="payfast_charges")
    op.drop_index("ix_payfast_charges_business_id", table_name="payfast_charges")
    op.drop_table("payfast_charges")
    op.drop_index("ix_business_subscriptions_provider_subscription_reference", table_name="business_subscriptions")
