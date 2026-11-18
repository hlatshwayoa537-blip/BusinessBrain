"""Add supplier directory and purchase order workflow."""
from alembic import op
import sqlalchemy as sa

revision = "0019_supplier_purchasing"
down_revision = "0018_discrepancy_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("contact_name", sa.String(160), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_number", sa.String(80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "name", name="uq_supplier_business_name"),
    )
    op.create_index("ix_suppliers_business_id", "suppliers", ["business_id"])
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "reference", name="uq_purchase_order_business_reference"),
    )
    for column in ("business_id", "supplier_id", "status"):
        op.create_index(f"ix_purchase_orders_{column}", "purchase_orders", [column])
    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(14, 3), nullable=False),
        sa.Column("quantity_received", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_order_lines_purchase_order_id", "purchase_order_lines", ["purchase_order_id"])
    op.create_index("ix_purchase_order_lines_business_id", "purchase_order_lines", ["business_id"])
    op.create_table(
        "purchase_order_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_order_events_purchase_order_id", "purchase_order_events", ["purchase_order_id"])
    op.create_index("ix_purchase_order_events_business_id", "purchase_order_events", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_order_events_business_id", table_name="purchase_order_events")
    op.drop_index("ix_purchase_order_events_purchase_order_id", table_name="purchase_order_events")
    op.drop_table("purchase_order_events")
    op.drop_index("ix_purchase_order_lines_business_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_purchase_order_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    for column in ("status", "supplier_id", "business_id"):
        op.drop_index(f"ix_purchase_orders_{column}", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_suppliers_is_active", table_name="suppliers")
    op.drop_index("ix_suppliers_business_id", table_name="suppliers")
    op.drop_table("suppliers")
