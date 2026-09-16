"""add company intelligence

Revision ID: 7d8f23b1a9c4
Revises: 6c4c8f2a91b7
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7d8f23b1a9c4"
down_revision: Union[str, Sequence[str], None] = "6c4c8f2a91b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_intelligence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("canonical_domain", sa.String(), nullable=True),
        sa.Column("ats", sa.String(), nullable=True),
        sa.Column("ats_slug", sa.String(), nullable=True),
        sa.Column("careers_url", sa.String(), nullable=True),
        sa.Column("open_job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_grad_job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matching_job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("h1b_lca_1y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "h1b_software_lca_1y",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("perm_3y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "explicit_sponsorship_status",
            sa.String(),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("latest_warn_notice", sa.DateTime(), nullable=True),
        sa.Column("warn_severity", sa.String(), nullable=False, server_default="green"),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column(
            "target_locations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "recruiter_profiles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "intelligence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company", name="uq_company_intelligence_company"),
    )
    op.create_index(
        "ix_company_intelligence_sponsorship",
        "company_intelligence",
        ["explicit_sponsorship_status"],
    )
    op.create_index(
        "ix_company_intelligence_warn",
        "company_intelligence",
        ["warn_severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_intelligence_warn", table_name="company_intelligence")
    op.drop_index("ix_company_intelligence_sponsorship", table_name="company_intelligence")
    op.drop_table("company_intelligence")
