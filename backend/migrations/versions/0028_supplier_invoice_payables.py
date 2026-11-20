"""Supplier accounts payable and payment ledger."""
from alembic import op
import sqlalchemy as sa

revision = "0028_supplier_invoice_payables"
down_revision = "0027_supplier_invoice_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_invoice_payables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("supplier_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invoice_id", name="uq_supplier_invoice_payable_invoice"),
    )
    for column in ("business_id", "invoice_id", "supplier_id", "status"):
        op.create_index(f"ix_supplier_invoice_payables_{column}", "supplier_invoice_payables", [column])
    op.create_table(
        "supplier_invoice_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payable_id", sa.String(36), sa.ForeignKey("supplier_invoice_payables.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("supplier_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_supplier_invoice_payment_idempotency"),
    )
    for column in ("business_id", "payable_id", "invoice_id"):
        op.create_index(f"ix_supplier_invoice_payments_{column}", "supplier_invoice_payments", [column])


def downgrade() -> None:
    op.drop_table("supplier_invoice_payments")
    op.drop_table("supplier_invoice_payables")
