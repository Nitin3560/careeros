"""add job queue key

Revision ID: 91b2c3d4e5f6
Revises: 8af1c2d3e4b5
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "91b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8af1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("queue_key", sa.String(), nullable=True))
    op.create_index("ix_jobs_queue_key", "jobs", ["queue_key"])


def downgrade() -> None:
    op.drop_index("ix_jobs_queue_key", table_name="jobs")
    op.drop_column("jobs", "queue_key")
