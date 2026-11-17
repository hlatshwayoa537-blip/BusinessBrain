"""Create direct business referral tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0015_business_referrals"
down_revision = "0014_daily_business_close"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_referral_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referral_code", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("business_id", name="uq_business_referral_profile_business"),
        sa.UniqueConstraint("referral_code", name="uq_business_referral_profile_code"),
    )
    op.create_index("ix_business_referral_profiles_business_id", "business_referral_profiles", ["business_id"])
    op.create_index("ix_business_referral_profiles_referral_code", "business_referral_profiles", ["referral_code"])

    op.create_table(
        "business_referrals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("referrer_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_payment"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("referred_business_id", name="uq_referral_referred_business"),
    )
    op.create_index("ix_business_referrals_referrer_business_id", "business_referrals", ["referrer_business_id"])
    op.create_index("ix_business_referrals_referred_business_id", "business_referrals", ["referred_business_id"])
    op.create_index("ix_business_referrals_status", "business_referrals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_business_referrals_status", table_name="business_referrals")
    op.drop_index("ix_business_referrals_referred_business_id", table_name="business_referrals")
    op.drop_index("ix_business_referrals_referrer_business_id", table_name="business_referrals")
    op.drop_table("business_referrals")
    op.drop_index("ix_business_referral_profiles_referral_code", table_name="business_referral_profiles")
    op.drop_index("ix_business_referral_profiles_business_id", table_name="business_referral_profiles")
    op.drop_table("business_referral_profiles")
