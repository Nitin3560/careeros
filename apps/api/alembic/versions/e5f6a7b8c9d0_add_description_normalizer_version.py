"""track the description text normalizer version

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("description_normalizer_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("jobs", "description_normalizer_version")
