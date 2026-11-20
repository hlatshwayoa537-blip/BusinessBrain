"""Index PayFast subscription token for optional-reference ITNs."""

from alembic import op

revision = "0034_payfast_token_index"
down_revision = "0033_payfast_charge_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_payfast_payments_provider_subscription_token",
        "payfast_payments",
        ["provider_subscription_token"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payfast_payments_provider_subscription_token",
        table_name="payfast_payments",
    )
