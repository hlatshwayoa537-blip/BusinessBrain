"""Add provider-native POS line references and durable refund links."""

from alembic import op
import sqlalchemy as sa

revision = "0031_pos_external_refund_references"
down_revision = "0030_payfast_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_transaction_lines", sa.Column("external_line_id", sa.String(180), nullable=True))
    op.add_column("pos_transaction_lines", sa.Column("original_line_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_pos_transaction_lines_original_line_id",
        "pos_transaction_lines",
        "pos_transaction_lines",
        ["original_line_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pos_transaction_lines_original_line_id", "pos_transaction_lines", ["original_line_id"])
    op.create_unique_constraint(
        "uq_pos_transaction_external_line",
        "pos_transaction_lines",
        ["transaction_id", "external_line_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_pos_transaction_external_line", "pos_transaction_lines", type_="unique")
    op.drop_index("ix_pos_transaction_lines_original_line_id", table_name="pos_transaction_lines")
    op.drop_constraint("fk_pos_transaction_lines_original_line_id", "pos_transaction_lines", type_="foreignkey")
    op.drop_column("pos_transaction_lines", "original_line_id")
    op.drop_column("pos_transaction_lines", "external_line_id")
