"""Add auditable bank statement imports and reconciliation review."""
from alembic import op
import sqlalchemy as sa

revision = "0023_bank_stmt_recon"
down_revision = "0022_expense_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("filename", sa.String(length=180), nullable=False),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bank_statement_imports_business_id", "bank_statement_imports", ["business_id"])
    op.create_table(
        "bank_statement_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_id", sa.String(length=36), sa.ForeignKey("bank_statement_imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ZAR"),
        sa.Column("running_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=20), nullable=False, server_default="unmatched"),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "fingerprint", name="uq_bank_statement_business_fingerprint"),
    )
    op.create_index("ix_bank_statement_transactions_business_id", "bank_statement_transactions", ["business_id"])
    op.create_index("ix_bank_statement_transactions_import_id", "bank_statement_transactions", ["import_id"])
    op.create_index("ix_bank_statement_transactions_transaction_date", "bank_statement_transactions", ["transaction_date"])
    op.create_index("ix_bank_statement_transactions_reconciliation_status", "bank_statement_transactions", ["reconciliation_status"])


def downgrade() -> None:
    op.drop_table("bank_statement_transactions")
    op.drop_table("bank_statement_imports")
