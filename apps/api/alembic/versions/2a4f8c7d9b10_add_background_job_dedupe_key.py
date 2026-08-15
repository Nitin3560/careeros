"""add background job dedupe key

Revision ID: 2a4f8c7d9b10
Revises: 50962ab1a1f0
Create Date: 2026-08-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2a4f8c7d9b10"
down_revision: Union[str, Sequence[str], None] = "50962ab1a1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("background_jobs", sa.Column("dedupe_key", sa.String(), nullable=True))
    op.create_index(
        "ix_background_jobs_dedupe_key",
        "background_jobs",
        ["dedupe_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_dedupe_key", table_name="background_jobs")
    op.drop_column("background_jobs", "dedupe_key")
