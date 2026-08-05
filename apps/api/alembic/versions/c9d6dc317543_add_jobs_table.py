"""add jobs table

Revision ID: c9d6dc317543
Revises: abb3caf77ea5
Create Date: 2026-08-03 21:56:38.120267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
revision: str = 'c9d6dc317543'
down_revision: Union[str, Sequence[str], None] = 'abb3caf77ea5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('company', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('description_text', sa.String(), nullable=True),
    sa.Column('application_url', sa.String(), nullable=True),
    sa.Column('date_posted', sa.DateTime(), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('jobs')
