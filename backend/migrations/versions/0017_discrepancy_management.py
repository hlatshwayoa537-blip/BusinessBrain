"""Add discrepancy case management and audit events."""
from alembic import op
import sqlalchemy as sa

revision = "0017_discrepancy_management"
down_revision = "0016_vexion_billing_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discrepancies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("daily_close_id", sa.String(36), sa.ForeignKey("daily_business_closes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False, server_default="reconciliation"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("business_id", "daily_close_id", "assigned_to_user_id", "priority", "status"):
        op.create_index(f"ix_discrepancies_{column}", "discrepancies", [column])
    op.create_table(
        "discrepancy_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("discrepancy_id", sa.String(36), sa.ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_discrepancy_events_discrepancy_id", "discrepancy_events", ["discrepancy_id"])
    op.create_index("ix_discrepancy_events_business_id", "discrepancy_events", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_discrepancy_events_business_id", table_name="discrepancy_events")
    op.drop_index("ix_discrepancy_events_discrepancy_id", table_name="discrepancy_events")
    op.drop_table("discrepancy_events")
    for column in ("status", "priority", "assigned_to_user_id", "daily_close_id", "business_id"):
        op.drop_index(f"ix_discrepancies_{column}", table_name="discrepancies")
    op.drop_table("discrepancies")
