"""Add inventory item catalogue and immutable stock movement ledger."""
from alembic import op
import sqlalchemy as sa

revision = "0020_inventory_stock_ledger"
down_revision = "0019_supplier_purchasing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(80), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("unit", sa.String(24), nullable=False, server_default="unit"),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "sku", name="uq_inventory_item_business_sku"),
    )
    op.create_index("ix_inventory_items_business_id", "inventory_items", ["business_id"])
    op.create_index("ix_inventory_items_is_active", "inventory_items", ["is_active"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_item_id", sa.String(36), sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(24), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("location", sa.String(120), nullable=False, server_default="Main"),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("source_line_id", sa.String(36), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_event_id", "source_line_id", name="uq_inventory_source_receipt_line"),
    )
    op.create_index("ix_inventory_movements_business_id", "inventory_movements", ["business_id"])
    op.create_index("ix_inventory_movements_inventory_item_id", "inventory_movements", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_inventory_item_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_business_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_inventory_items_is_active", table_name="inventory_items")
    op.drop_index("ix_inventory_items_business_id", table_name="inventory_items")
    op.drop_table("inventory_items")
