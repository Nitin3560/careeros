"""add job ingestion lifecycle

Revision ID: 6c4c8f2a91b7
Revises: e4f1a2b3c9d8
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6c4c8f2a91b7"
down_revision: Union[str, Sequence[str], None] = "e4f1a2b3c9d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("canonical_url", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("identity_key", sa.String(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column("jobs", sa.Column("expired_at", sa.DateTime(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("ingestion_status", sa.String(), nullable=False, server_default="new"),
    )
    op.add_column(
        "jobs",
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("UPDATE jobs SET first_seen_at = retrieved_at WHERE first_seen_at IS NULL")
    op.execute("UPDATE jobs SET last_seen_at = retrieved_at WHERE last_seen_at IS NULL")
    op.alter_column("jobs", "first_seen_at", nullable=False)
    op.alter_column("jobs", "last_seen_at", nullable=False)
    op.create_index("ix_jobs_identity_key", "jobs", ["identity_key"])
    op.create_index("ix_jobs_ingestion_status", "jobs", ["ingestion_status"])
    op.create_index("ix_jobs_last_seen_at", "jobs", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_last_seen_at", table_name="jobs")
    op.drop_index("ix_jobs_ingestion_status", table_name="jobs")
    op.drop_index("ix_jobs_identity_key", table_name="jobs")
    op.drop_column("jobs", "seen_count")
    op.drop_column("jobs", "ingestion_status")
    op.drop_column("jobs", "expired_at")
    op.drop_column("jobs", "last_verified_at")
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "first_seen_at")
    op.drop_column("jobs", "identity_key")
    op.drop_column("jobs", "canonical_url")
