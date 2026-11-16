"""Add structured quotations to private Deal Rooms."""
from alembic import op
import sqlalchemy as sa

revision = "0006_deal_room_quotations"
down_revision = "0005_business_conversations_deal_rooms"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "deal_room_quotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deal_room_id", sa.String(36), sa.ForeignKey("business_deal_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference", sa.String(40), nullable=False, unique=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("line_items_json", sa.Text(), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("response_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deal_room_quotations_deal_room_id", "deal_room_quotations", ["deal_room_id"])
    op.create_index("ix_deal_room_quotations_issuer_business_id", "deal_room_quotations", ["issuer_business_id"])
    op.create_index("ix_deal_room_quotations_reference", "deal_room_quotations", ["reference"])
    op.create_index("ix_deal_room_quotations_status", "deal_room_quotations", ["status"])

def downgrade() -> None:
    op.drop_index("ix_deal_room_quotations_status", table_name="deal_room_quotations")
    op.drop_index("ix_deal_room_quotations_reference", table_name="deal_room_quotations")
    op.drop_index("ix_deal_room_quotations_issuer_business_id", table_name="deal_room_quotations")
    op.drop_index("ix_deal_room_quotations_deal_room_id", table_name="deal_room_quotations")
    op.drop_table("deal_room_quotations")
