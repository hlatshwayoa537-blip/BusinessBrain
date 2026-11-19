"""Add many-to-one bank settlement batch links."""
from alembic import op
import sqlalchemy as sa

revision = "0025_bank_batch_links"
down_revision = "0024_bank_match_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_match_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_transaction_id", sa.String(length=36), sa.ForeignKey("bank_statement_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False, server_default="pos"),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("signed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "source_type", "source_id", name="uq_bank_batch_source_business"),
        sa.UniqueConstraint("bank_transaction_id", "source_type", "source_id", name="uq_bank_batch_transaction_source"),
    )
    op.create_index("ix_bank_statement_match_links_business_id", "bank_statement_match_links", ["business_id"])
    op.create_index("ix_bank_statement_match_links_bank_transaction_id", "bank_statement_match_links", ["bank_transaction_id"])
    op.create_index("ix_bank_batch_transaction", "bank_statement_match_links", ["business_id", "bank_transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_bank_batch_transaction", table_name="bank_statement_match_links")
    op.drop_index("ix_bank_statement_match_links_bank_transaction_id", table_name="bank_statement_match_links")
    op.drop_index("ix_bank_statement_match_links_business_id", table_name="bank_statement_match_links")
    op.drop_table("bank_statement_match_links")
