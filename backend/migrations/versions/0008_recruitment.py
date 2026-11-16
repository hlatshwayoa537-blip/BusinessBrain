"""Create BusinessBrain recruitment vacancies and applicant records."""
from alembic import op
import sqlalchemy as sa

revision = "0008_recruitment"
down_revision = "0007_deal_room_files"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("job_postings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("location", sa.String(180), nullable=True),
        sa.Column("employment_type", sa.String(30), nullable=False, server_default="full_time"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_job_postings_business_id", "job_postings", ["business_id"])
    op.create_index("ix_job_postings_status", "job_postings", ["status"])
    op.create_table("job_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicant_name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("location", sa.String(180), nullable=True),
        sa.Column("experience", sa.String(80), nullable=True),
        sa.Column("resume_url", sa.String(500), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_job_applications_job_id", "job_applications", ["job_id"])
    op.create_index("ix_job_applications_status", "job_applications", ["status"])

def downgrade() -> None:
    op.drop_index("ix_job_applications_status", table_name="job_applications")
    op.drop_index("ix_job_applications_job_id", table_name="job_applications")
    op.drop_table("job_applications")
    op.drop_index("ix_job_postings_status", table_name="job_postings")
    op.drop_index("ix_job_postings_business_id", table_name="job_postings")
    op.drop_table("job_postings")
