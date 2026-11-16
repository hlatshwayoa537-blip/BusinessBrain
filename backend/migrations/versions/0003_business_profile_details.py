"""Add business profile and contact details."""
from alembic import op
import sqlalchemy as sa

revision = "0003_business_profile_details"
down_revision = "0002_business_profile_image"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("businesses", sa.Column("registration_number", sa.String(length=100), nullable=True))
    op.add_column("businesses", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column("businesses", sa.Column("contact_email", sa.String(length=320), nullable=True))
    op.add_column("businesses", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("businesses", sa.Column("address_line", sa.String(length=255), nullable=True))
    op.add_column("businesses", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("businesses", sa.Column("province", sa.String(length=120), nullable=True))
    op.add_column("businesses", sa.Column("postal_code", sa.String(length=24), nullable=True))
    op.add_column("businesses", sa.Column("description", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("businesses", "description")
    op.drop_column("businesses", "postal_code")
    op.drop_column("businesses", "province")
    op.drop_column("businesses", "city")
    op.drop_column("businesses", "address_line")
    op.drop_column("businesses", "phone")
    op.drop_column("businesses", "contact_email")
    op.drop_column("businesses", "website")
    op.drop_column("businesses", "registration_number")
