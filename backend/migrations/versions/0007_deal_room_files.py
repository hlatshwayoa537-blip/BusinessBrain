"""Add private file metadata for Deal Room uploads."""
from alembic import op
import sqlalchemy as sa

revision = "0007_deal_room_files"
down_revision = "0006_deal_room_quotations"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "deal_room_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deal_room_id", sa.String(36), sa.ForeignKey("business_deal_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(180), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Numeric(12, 0), nullable=False),
        sa.Column("storage_key", sa.String(700), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_deal_room_files_deal_room_id", "deal_room_files", ["deal_room_id"])
    op.create_index("ix_deal_room_files_uploader_business_id", "deal_room_files", ["uploader_business_id"])
    op.create_index("ix_deal_room_files_status", "deal_room_files", ["status"])

def downgrade() -> None:
    op.drop_index("ix_deal_room_files_status", table_name="deal_room_files")
    op.drop_index("ix_deal_room_files_uploader_business_id", table_name="deal_room_files")
    op.drop_index("ix_deal_room_files_deal_room_id", table_name="deal_room_files")
    op.drop_table("deal_room_files")
