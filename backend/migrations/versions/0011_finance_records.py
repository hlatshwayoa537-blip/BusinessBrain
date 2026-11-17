"""Create business finance transaction records."""
from alembic import op
import sqlalchemy as sa

revision = "0011_finance_records"
down_revision = "0010_whatsapp_staff"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="paid"),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finance_transactions_business_id", "finance_transactions", ["business_id"])
    op.create_index("ix_finance_transactions_kind", "finance_transactions", ["kind"])
    op.create_index("ix_finance_transactions_status", "finance_transactions", ["status"])
    op.create_index("ix_finance_transactions_occurred_on", "finance_transactions", ["occurred_on"])

def downgrade() -> None:
    op.drop_index("ix_finance_transactions_occurred_on", table_name="finance_transactions")
    op.drop_index("ix_finance_transactions_status", table_name="finance_transactions")
    op.drop_index("ix_finance_transactions_kind", table_name="finance_transactions")
    op.drop_index("ix_finance_transactions_business_id", table_name="finance_transactions")
    op.drop_table("finance_transactions")
