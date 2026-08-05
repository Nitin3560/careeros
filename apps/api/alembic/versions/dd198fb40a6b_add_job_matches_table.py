"""add job_matches table

Revision ID: dd198fb40a6b
Revises: 5aa17f6dbc3f
Create Date: 2026-08-04 14:54:36.448676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str = 'dd198fb40a6b'
down_revision: Union[str, Sequence[str], None] = '5aa17f6dbc3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('job_matches',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('overall_score', sa.Integer(), nullable=True),
    sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('missing', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confidence', sa.String(), nullable=True),
    sa.Column('scored_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'job_id', name='uq_user_job_match')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('job_matches')
