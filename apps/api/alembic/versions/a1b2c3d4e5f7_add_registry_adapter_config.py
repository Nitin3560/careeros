"""add registry adapter endpoint configuration

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_registry", sa.Column("adapter_config", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_registry", "adapter_config")
