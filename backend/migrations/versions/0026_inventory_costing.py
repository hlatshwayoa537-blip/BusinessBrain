"""Store receipt and POS sale unit cost snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0026_inventory_costing"
down_revision = "0025_bank_batch_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_movements", sa.Column("unit_cost", sa.Numeric(14, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_movements", "unit_cost")
