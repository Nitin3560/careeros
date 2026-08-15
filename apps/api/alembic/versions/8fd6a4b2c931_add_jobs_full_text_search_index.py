"""add jobs full text search index

Revision ID: 8fd6a4b2c931
Revises: 2a4f8c7d9b10
Create Date: 2026-08-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "8fd6a4b2c931"
down_revision: Union[str, Sequence[str], None] = "2a4f8c7d9b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_jobs_title_search_vector
        ON jobs
        USING gin (to_tsvector('english', coalesce(title, '')))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_title_search_vector")
