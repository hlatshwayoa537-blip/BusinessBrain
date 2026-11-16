"""Add optional business profile image."""
from alembic import op
import sqlalchemy as sa

revision = "0002_business_profile_image"
down_revision = "0001_initial_accounts"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("businesses", sa.Column("profile_image_data_url", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("businesses", "profile_image_data_url")
