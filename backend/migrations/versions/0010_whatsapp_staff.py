"""Add WhatsApp-based staff invitations and member phone numbers."""
from alembic import op
import sqlalchemy as sa

revision = "0010_whatsapp_staff"
down_revision = "0009_staff_invites"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=24), nullable=True))
    op.alter_column("staff_invitations", "email", existing_type=sa.String(length=320), nullable=True)
    op.add_column("staff_invitations", sa.Column("phone", sa.String(length=24), nullable=True))
    op.execute("UPDATE staff_invitations SET phone = '00000000' WHERE phone IS NULL")
    op.alter_column("staff_invitations", "phone", existing_type=sa.String(length=24), nullable=False)
    op.create_index("ix_staff_invitations_phone", "staff_invitations", ["phone"])

def downgrade() -> None:
    op.drop_index("ix_staff_invitations_phone", table_name="staff_invitations")
    op.drop_column("staff_invitations", "phone")
    op.alter_column("staff_invitations", "email", existing_type=sa.String(length=320), nullable=False)
    op.drop_column("users", "phone")
