"""Index PayFast subscription token for optional-reference ITNs.

Build this index concurrently so the API startup migration does not take a
write-blocking table lock on the live payments table.
"""

from alembic import op

revision = "0034_payfast_token_index"
down_revision = "0033_payfast_charge_ledger"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_payfast_payments_provider_subscription_token"


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY cannot run inside Alembic's normal transaction.
    # IF NOT EXISTS makes retries safe if a previous deployment completed the
    # index build but did not finish recording the Alembic revision.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            "ON payfast_payments (provider_subscription_token)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
