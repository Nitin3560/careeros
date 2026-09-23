"""tune jobs for HOT updates and missing-count expiry

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_jobs_last_seen_at", table_name="jobs", if_exists=True)
    op.add_column(
        "jobs",
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("""
        ALTER TABLE jobs SET (
            fillfactor = 85,
            autovacuum_vacuum_scale_factor = 0.02,
            autovacuum_vacuum_threshold = 5000,
            autovacuum_analyze_scale_factor = 0.01,
            autovacuum_analyze_threshold = 5000,
            autovacuum_vacuum_cost_delay = 2,
            autovacuum_vacuum_cost_limit = 2000
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE jobs RESET (fillfactor, autovacuum_vacuum_scale_factor, autovacuum_vacuum_threshold, autovacuum_analyze_scale_factor, autovacuum_analyze_threshold, autovacuum_vacuum_cost_delay, autovacuum_vacuum_cost_limit)")
    op.drop_column("jobs", "missing_count")
    op.create_index("ix_jobs_last_seen_at", "jobs", ["last_seen_at"])
