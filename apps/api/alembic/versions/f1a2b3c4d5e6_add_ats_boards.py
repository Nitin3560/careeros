"""add ats boards registry

Revision ID: f1a2b3c4d5e6
Revises: 8fd6a4b2c931
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f1a2b3c4d5e6"
down_revision = "8fd6a4b2c931"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "ats_boards",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ats", sa.String, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("company_name", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="unknown"),
        sa.Column("job_count", sa.Integer, nullable=True),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String, nullable=True),
        sa.Column(
            "consecutive_failures",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("source_list", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("ats", "slug", name="uq_ats_board"),
    )
    op.create_index("ix_ats_boards_status", "ats_boards", ["status"])
    op.create_index(
        "ix_ats_boards_last_ingested",
        "ats_boards",
        ["last_ingested_at"],
    )
    op.add_column("jobs", sa.Column("eligible", sa.Boolean, nullable=True))
    op.add_column("jobs", sa.Column("skip_reason", sa.String, nullable=True))
    op.add_column("jobs", sa.Column("matched_pattern", sa.String, nullable=True))
    op.add_column("jobs", sa.Column("filter_version", sa.Integer, nullable=True))
    op.create_index("ix_jobs_eligible", "jobs", ["eligible"])
    op.create_index("uq_jobs_external_id", "jobs", ["external_id"], unique=True)


def downgrade():
    op.drop_index("uq_jobs_external_id", table_name="jobs")
    op.drop_index("ix_jobs_eligible", table_name="jobs")
    op.drop_column("jobs", "filter_version")
    op.drop_column("jobs", "matched_pattern")
    op.drop_column("jobs", "skip_reason")
    op.drop_column("jobs", "eligible")
    op.drop_index("ix_ats_boards_last_ingested", table_name="ats_boards")
    op.drop_index("ix_ats_boards_status", table_name="ats_boards")
    op.drop_table("ats_boards")
