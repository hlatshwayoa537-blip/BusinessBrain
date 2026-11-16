"""Add opt-in Business Network directory visibility."""
from alembic import op
import sqlalchemy as sa

revision = "0004_business_network_visibility"
down_revision = "0003_business_profile_details"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("businesses", sa.Column("directory_listed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("businesses", sa.Column("public_email", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("businesses", sa.Column("public_phone", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("businesses", sa.Column("public_website", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("businesses", sa.Column("public_location", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column("businesses", "public_location")
    op.drop_column("businesses", "public_website")
    op.drop_column("businesses", "public_phone")
    op.drop_column("businesses", "public_email")
    op.drop_column("businesses", "directory_listed")
