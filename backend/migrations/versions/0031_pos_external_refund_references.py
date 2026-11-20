"""Add provider-native POS line references and durable refund links."""

from alembic import op
import sqlalchemy as sa

revision = "0031_pos_refund_refs"
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
    # Recover original-line links for historical inventory-tracked refunds.
    # Older unmapped refund lines did not persist this relationship.
    op.execute("""
        UPDATE pos_transaction_lines AS refund_line
        SET original_line_id = movement.source_id
        FROM inventory_movements AS movement
        JOIN pos_transactions AS refund_transaction
          ON refund_transaction.id = movement.source_event_id
        WHERE movement.source_line_id = refund_line.id
          AND movement.source_type = 'pos_return'
          AND refund_transaction.transaction_type = 'refund'
          AND movement.source_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_constraint("uq_pos_transaction_external_line", "pos_transaction_lines", type_="unique")
    op.drop_index("ix_pos_transaction_lines_original_line_id", table_name="pos_transaction_lines")
    op.drop_constraint("fk_pos_transaction_lines_original_line_id", "pos_transaction_lines", type_="foreignkey")
    op.drop_column("pos_transaction_lines", "original_line_id")
    op.drop_column("pos_transaction_lines", "external_line_id")
