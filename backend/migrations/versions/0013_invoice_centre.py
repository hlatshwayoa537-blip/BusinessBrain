"""Create tenant-scoped invoices and invoice line items."""
from alembic import op
import sqlalchemy as sa

revision = "0013_invoice_centre"
down_revision = "0012_pos_ingestion"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("customer_name", sa.String(length=180), nullable=False),
        sa.Column("customer_email", sa.String(length=320), nullable=True),
        sa.Column("customer_phone", sa.String(length=40), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "invoice_number", name="uq_invoice_business_number"),
    )
    op.create_index("ix_invoices_business_id", "invoices", ["business_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("invoice_id", sa.String(length=36), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_invoice_line_items_invoice_id", "invoice_line_items", ["invoice_id"])

def downgrade() -> None:
    op.drop_index("ix_invoice_line_items_invoice_id", table_name="invoice_line_items")
    op.drop_table("invoice_line_items")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_business_id", table_name="invoices")
    op.drop_table("invoices")
