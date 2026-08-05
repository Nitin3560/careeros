"""add profile match versioning

Revision ID: be49ab4c2874
Revises: 4b658ebcbbc4
Create Date: 2026-08-05 11:36:56.483640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be49ab4c2874'
down_revision: Union[str, Sequence[str], None] = '4b658ebcbbc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'candidate_profiles',
        sa.Column('profile_version', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column(
        'job_matches',
        sa.Column('profile_version', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column(
        'job_matches',
        sa.Column('prompt_version', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column(
        'job_matches',
        sa.Column('is_estimated', sa.Boolean(), server_default='false', nullable=False),
    )
    op.alter_column('candidate_profiles', 'profile_version', server_default=None)
    op.alter_column('job_matches', 'profile_version', server_default=None)
    op.alter_column('job_matches', 'prompt_version', server_default=None)
    op.alter_column('job_matches', 'is_estimated', server_default=None)


def downgrade() -> None:
    op.drop_column('job_matches', 'is_estimated')
    op.drop_column('job_matches', 'prompt_version')
    op.drop_column('job_matches', 'profile_version')
    op.drop_column('candidate_profiles', 'profile_version')
