"""Create daily business close and append-only audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "0014_daily_business_close"
down_revision = "0013_invoice_centre"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_business_closes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_name", sa.String(160), nullable=False, server_default="Main branch"),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("expected_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_card", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_other", sa.Numeric(14, 2), nullable=True),
        sa.Column("actual_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("actual_card", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("actual_other", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expenses_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("pos_transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", "branch_name", "business_date", name="uq_daily_close_business_branch_date"),
    )
    op.create_index("ix_daily_business_closes_business_id", "daily_business_closes", ["business_id"])
    op.create_index("ix_daily_business_closes_business_date", "daily_business_closes", ["business_date"])
    op.create_index("ix_daily_business_closes_status", "daily_business_closes", ["status"])
    op.create_table(
        "daily_business_close_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("close_id", sa.String(36), sa.ForeignKey("daily_business_closes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_daily_business_close_audit_close_id", "daily_business_close_audit", ["close_id"])
    op.create_index("ix_daily_business_close_audit_business_id", "daily_business_close_audit", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_business_close_audit_business_id", table_name="daily_business_close_audit")
    op.drop_index("ix_daily_business_close_audit_close_id", table_name="daily_business_close_audit")
    op.drop_table("daily_business_close_audit")
    op.drop_index("ix_daily_business_closes_status", table_name="daily_business_closes")
    op.drop_index("ix_daily_business_closes_business_date", table_name="daily_business_closes")
    op.drop_index("ix_daily_business_closes_business_id", table_name="daily_business_closes")
    op.drop_table("daily_business_closes")
