"""add ats board priority

Revision ID: 8af1c2d3e4b5
Revises: 7d8f23b1a9c4
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8af1c2d3e4b5"
down_revision: Union[str, Sequence[str], None] = "7d8f23b1a9c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ats_boards",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
    )
    op.create_index("ix_ats_boards_priority", "ats_boards", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_ats_boards_priority", table_name="ats_boards")
    op.drop_column("ats_boards", "priority")
