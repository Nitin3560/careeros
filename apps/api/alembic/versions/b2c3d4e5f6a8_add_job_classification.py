"""add deterministic job classification fields"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

def upgrade():
    columns = [
        ("title_normalized", sa.Text()), ("is_tech_title", sa.Boolean()),
        ("tech_subfield", sa.Text()), ("is_senior_title", sa.Boolean()),
        ("seniority_level", sa.Text()), ("is_new_grad_title", sa.Boolean()),
        ("employment_type", sa.Text()), ("location_class", sa.Text()),
        ("location_reason", sa.Text()), ("sponsorship_block", sa.Boolean()),
        ("sponsorship_evidence", sa.Text()), ("min_years_required", sa.Integer()),
        ("min_years_alternatives", postgresql.JSONB()), ("years_source", sa.Text()),
        ("parse_tier", sa.SmallInteger()), ("exclusion_reasons", sa.ARRAY(sa.Text())),
        ("classifier_version", sa.Integer()),
    ]
    for name, typ in columns:
        op.add_column("jobs", sa.Column(name, typ, nullable=True))
    op.create_index("ix_jobs_classifier_version", "jobs", ["classifier_version"])
    op.create_index("ix_jobs_active_tech", "jobs", [sa.text("first_seen_at DESC")],
                    postgresql_where=sa.text("expired_at IS NULL AND is_tech_title AND NOT is_senior_title"))

def downgrade():
    op.drop_index("ix_jobs_active_tech", table_name="jobs")
    op.drop_index("ix_jobs_classifier_version", table_name="jobs")
    for name in ("classifier_version", "exclusion_reasons", "parse_tier", "years_source", "min_years_alternatives", "min_years_required", "sponsorship_evidence", "sponsorship_block", "location_reason", "location_class", "employment_type", "is_new_grad_title", "seniority_level", "is_senior_title", "tech_subfield", "is_tech_title", "title_normalized"):
        op.drop_column("jobs", name)
