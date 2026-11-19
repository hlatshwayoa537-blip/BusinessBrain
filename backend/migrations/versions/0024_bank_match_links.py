"""Add explicit source links to bank reconciliation matches."""
from alembic import op
import sqlalchemy as sa

revision = "0024_bank_match_links"
down_revision = "0023_bank_stmt_recon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_statement_transactions", sa.Column("matched_source_type", sa.String(length=24), nullable=True))
    op.add_column("bank_statement_transactions", sa.Column("matched_source_id", sa.String(length=36), nullable=True))
    op.create_unique_constraint(
        "uq_bank_statement_matched_source",
        "bank_statement_transactions",
        ["business_id", "matched_source_type", "matched_source_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_bank_statement_matched_source", "bank_statement_transactions", type_="unique")
    op.drop_column("bank_statement_transactions", "matched_source_id")
    op.drop_column("bank_statement_transactions", "matched_source_type")
