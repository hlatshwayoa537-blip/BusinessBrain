"""Add expense due dates, payees and payment metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0022_expense_workflows"
down_revision = "0021_pos_transaction_lines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("finance_transactions", sa.Column("payee_name", sa.String(length=180), nullable=True))
    op.add_column("finance_transactions", sa.Column("due_on", sa.Date(), nullable=True))
    op.add_column("finance_transactions", sa.Column("paid_on", sa.Date(), nullable=True))
    op.add_column("finance_transactions", sa.Column("payment_method", sa.String(length=40), nullable=True))
    op.add_column("finance_transactions", sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))
    op.create_index("ix_finance_transactions_due_on", "finance_transactions", ["due_on"])


def downgrade() -> None:
    op.drop_index("ix_finance_transactions_due_on", table_name="finance_transactions")
    op.drop_column("finance_transactions", "tax_amount")
    op.drop_column("finance_transactions", "payment_method")
    op.drop_column("finance_transactions", "paid_on")
    op.drop_column("finance_transactions", "due_on")
    op.drop_column("finance_transactions", "payee_name")
