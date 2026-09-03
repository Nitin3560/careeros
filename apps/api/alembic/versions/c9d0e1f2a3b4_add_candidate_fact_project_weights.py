"""add candidate fact project weights

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_user_candidate_fact", "candidate_facts", type_="unique")
    op.add_column("candidate_facts", sa.Column("project", sa.String(), nullable=True))
    op.add_column(
        "candidate_facts",
        sa.Column("project_weight", sa.Integer(), server_default="1", nullable=False),
    )
    op.alter_column("candidate_facts", "project_weight", server_default=None)
    op.create_index("ix_candidate_facts_project", "candidate_facts", ["project"])
    op.create_index(
        "ix_candidate_facts_user_project",
        "candidate_facts",
        ["user_id", "project"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_facts_user_project", table_name="candidate_facts")
    op.drop_index("ix_candidate_facts_project", table_name="candidate_facts")
    op.drop_column("candidate_facts", "project_weight")
    op.drop_column("candidate_facts", "project")
    op.create_unique_constraint(
        "uq_user_candidate_fact",
        "candidate_facts",
        ["user_id", "fact_key"],
    )
