"""Create private business conversations and deal rooms."""
from alembic import op
import sqlalchemy as sa

revision = "0005_business_conversations"
down_revision = "0004_business_network_visibility"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "business_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("host_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invitation_message", sa.Text(), nullable=True),
        sa.Column("access_password_hash", sa.String(512), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_invitations_host_business_id", "business_invitations", ["host_business_id"])
    op.create_index("ix_business_invitations_invited_business_id", "business_invitations", ["invited_business_id"])
    op.create_index("ix_business_invitations_status", "business_invitations", ["status"])
    op.create_table(
        "business_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("host_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invitation_id", sa.String(36), sa.ForeignKey("business_invitations.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_conversations_host_business_id", "business_conversations", ["host_business_id"])
    op.create_index("ix_business_conversations_invited_business_id", "business_conversations", ["invited_business_id"])
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("business_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_table(
        "business_deal_rooms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("business_conversations.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="discussion"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_deal_rooms_conversation_id", "business_deal_rooms", ["conversation_id"])
    op.create_table(
        "deal_room_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deal_room_id", sa.String(36), sa.ForeignKey("business_deal_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deal_room_messages_deal_room_id", "deal_room_messages", ["deal_room_id"])

def downgrade() -> None:
    op.drop_table("deal_room_messages")
    op.drop_index("ix_business_deal_rooms_conversation_id", table_name="business_deal_rooms")
    op.drop_table("business_deal_rooms")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_business_conversations_invited_business_id", table_name="business_conversations")
    op.drop_index("ix_business_conversations_host_business_id", table_name="business_conversations")
    op.drop_table("business_conversations")
    op.drop_index("ix_business_invitations_status", table_name="business_invitations")
    op.drop_index("ix_business_invitations_invited_business_id", table_name="business_invitations")
    op.drop_index("ix_business_invitations_host_business_id", table_name="business_invitations")
    op.drop_table("business_invitations")
