"""Customer invoice receipts and accounts receivable ledger."""
import sqlalchemy as sa
from alembic import op

revision = "0029_customer_invoice_receivables"
down_revision = "0028_supplier_invoice_payables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_invoice_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_customer_invoice_payment_idempotency"),
    )
    for column in ("business_id", "invoice_id"):
        op.create_index(f"ix_customer_invoice_payments_{column}", "customer_invoice_payments", [column])


def downgrade() -> None:
    op.drop_table("customer_invoice_payments")
