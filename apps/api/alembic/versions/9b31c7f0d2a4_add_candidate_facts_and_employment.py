"""add candidate facts and employment

Revision ID: 9b31c7f0d2a4
Revises: f1a2b3c4d5e6
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b31c7f0d2a4"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_key", sa.String(), nullable=False),
        sa.Column("fact_value", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fact_key", name="uq_user_candidate_fact"),
    )
    op.create_table(
        "candidate_employment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("employment_type", sa.String(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_facts_user_id", "candidate_facts", ["user_id"])
    op.create_index(
        "ix_candidate_employment_user_id", "candidate_employment", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_employment_user_id", table_name="candidate_employment")
    op.drop_index("ix_candidate_facts_user_id", table_name="candidate_facts")
    op.drop_table("candidate_employment")
    op.drop_table("candidate_facts")
