"""Add POS-agnostic connections and normalized sales transactions."""
from alembic import op
import sqlalchemy as sa

revision = "0012_pos_ingestion"
down_revision = "0011_finance_records"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "pos_connections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("integration_method", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pos_connections_business_id", "pos_connections", ["business_id"])
    op.create_index("ix_pos_connections_status", "pos_connections", ["status"])
    op.create_table(
        "pos_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", sa.String(length=36), sa.ForeignKey("pos_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_transaction_id", sa.String(length=180), nullable=False),
        sa.Column("branch_name", sa.String(length=160), nullable=True),
        sa.Column("till_name", sa.String(length=120), nullable=True),
        sa.Column("transaction_type", sa.String(length=12), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connection_id", "external_transaction_id", name="uq_pos_connection_external_transaction"),
    )
    op.create_index("ix_pos_transactions_business_id", "pos_transactions", ["business_id"])
    op.create_index("ix_pos_transactions_connection_id", "pos_transactions", ["connection_id"])
    op.create_index("ix_pos_transactions_transaction_type", "pos_transactions", ["transaction_type"])
    op.create_index("ix_pos_transactions_occurred_at", "pos_transactions", ["occurred_at"])

def downgrade() -> None:
    op.drop_index("ix_pos_transactions_occurred_at", table_name="pos_transactions")
    op.drop_index("ix_pos_transactions_transaction_type", table_name="pos_transactions")
    op.drop_index("ix_pos_transactions_connection_id", table_name="pos_transactions")
    op.drop_index("ix_pos_transactions_business_id", table_name="pos_transactions")
    op.drop_table("pos_transactions")
    op.drop_index("ix_pos_connections_status", table_name="pos_connections")
    op.drop_index("ix_pos_connections_business_id", table_name="pos_connections")
    op.drop_table("pos_connections")
