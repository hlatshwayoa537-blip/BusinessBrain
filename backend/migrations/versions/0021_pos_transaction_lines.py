"""Store POS item lines for product-level stock reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "0021_pos_transaction_lines"
down_revision = "0020_inventory_stock_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_transaction_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(36), sa.ForeignKey("pos_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(80), nullable=True),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("inventory_item_id", sa.String(36), sa.ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("transaction_id", "line_number", name="uq_pos_transaction_line_number"),
    )
    op.create_index("ix_pos_transaction_lines_transaction_id", "pos_transaction_lines", ["transaction_id"])
    op.create_index("ix_pos_transaction_lines_business_id", "pos_transaction_lines", ["business_id"])
    op.create_index("ix_pos_transaction_lines_sku", "pos_transaction_lines", ["sku"])
    op.create_index("ix_pos_transaction_lines_inventory_item_id", "pos_transaction_lines", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index("ix_pos_transaction_lines_inventory_item_id", table_name="pos_transaction_lines")
    op.drop_index("ix_pos_transaction_lines_sku", table_name="pos_transaction_lines")
    op.drop_index("ix_pos_transaction_lines_business_id", table_name="pos_transaction_lines")
    op.drop_index("ix_pos_transaction_lines_transaction_id", table_name="pos_transaction_lines")
    op.drop_table("pos_transaction_lines")
