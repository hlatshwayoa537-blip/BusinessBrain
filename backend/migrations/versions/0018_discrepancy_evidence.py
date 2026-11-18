"""Add private evidence attachments to discrepancy cases."""
from alembic import op
import sqlalchemy as sa

revision = "0018_discrepancy_evidence"
down_revision = "0017_discrepancy_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discrepancy_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("discrepancy_id", sa.String(36), sa.ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_filename", sa.String(180), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(700), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_discrepancy_evidence_discrepancy_id", "discrepancy_evidence", ["discrepancy_id"])
    op.create_index("ix_discrepancy_evidence_business_id", "discrepancy_evidence", ["business_id"])
    op.create_index("ix_discrepancy_evidence_status", "discrepancy_evidence", ["status"])


def downgrade() -> None:
    op.drop_index("ix_discrepancy_evidence_status", table_name="discrepancy_evidence")
    op.drop_index("ix_discrepancy_evidence_business_id", table_name="discrepancy_evidence")
    op.drop_index("ix_discrepancy_evidence_discrepancy_id", table_name="discrepancy_evidence")
    op.drop_table("discrepancy_evidence")
