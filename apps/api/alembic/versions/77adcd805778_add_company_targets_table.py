"""add company targets table

Revision ID: 77adcd805778
Revises: be49ab4c2874
Create Date: 2026-08-05 12:42:26.903838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '77adcd805778'
down_revision: Union[str, Sequence[str], None] = 'be49ab4c2874'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'company_targets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('last_ingested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )


def downgrade() -> None:
    op.drop_table('company_targets')
