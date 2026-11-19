"""Add many-to-one bank settlement batch links."""
from alembic import op
import sqlalchemy as sa
import uuid

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

    # Preserve previously confirmed one-to-one links in the shared uniqueness ledger.
    connection = op.get_bind()
    legacy_rows = connection.execute(sa.text("""
        SELECT id, business_id, matched_source_type, matched_source_id,
               amount, transaction_date, reviewed_by_user_id
        FROM bank_statement_transactions
        WHERE reconciliation_status = 'matched'
          AND matched_source_type IS NOT NULL
          AND matched_source_id IS NOT NULL
          AND reviewed_by_user_id IS NOT NULL
    """)).mappings().all()
    for row in legacy_rows:
        connection.execute(sa.text("""
            INSERT INTO bank_statement_match_links
                (id, business_id, bank_transaction_id, source_type, source_id,
                 signed_amount, source_date, created_by_user_id, created_at)
            VALUES
                (:id, :business_id, :bank_transaction_id, :source_type, :source_id,
                 :signed_amount, :source_date, :created_by_user_id, CURRENT_TIMESTAMP)
            ON CONFLICT (business_id, source_type, source_id) DO NOTHING
        """), {
            "id": str(uuid.uuid4()), "business_id": row["business_id"],
            "bank_transaction_id": row["id"], "source_type": row["matched_source_type"],
            "source_id": row["matched_source_id"], "signed_amount": row["amount"],
            "source_date": row["transaction_date"], "created_by_user_id": row["reviewed_by_user_id"],
        })


def downgrade() -> None:
    op.drop_index("ix_bank_batch_transaction", table_name="bank_statement_match_links")
    op.drop_index("ix_bank_statement_match_links_bank_transaction_id", table_name="bank_statement_match_links")
    op.drop_index("ix_bank_statement_match_links_business_id", table_name="bank_statement_match_links")
    op.drop_table("bank_statement_match_links")
