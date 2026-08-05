"""add applications table

Revision ID: 4b658ebcbbc4
Revises: 931a170a7af3
Create Date: 2026-08-04 21:45:25.241660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
revision: str = '4b658ebcbbc4'
down_revision: Union[str, Sequence[str], None] = '931a170a7af3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('applications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('resume_version_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('notes', sa.String(), nullable=True),
    sa.Column('applied_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['resume_version_id'], ['resume_versions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'job_id', name='uq_user_job_application')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('applications')
