"""add job_requirements

Revision ID: a7b8c9d0e1f2
Revises: 9b31c7f0d2a4
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "9b31c7f0d2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_requirements",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("key_index", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_job_requirements_status", "job_requirements", ["status"])
    op.create_index(
        "ix_job_requirements_prompt_version",
        "job_requirements",
        ["prompt_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_requirements_prompt_version", table_name="job_requirements")
    op.drop_index("ix_job_requirements_status", table_name="job_requirements")
    op.drop_table("job_requirements")
