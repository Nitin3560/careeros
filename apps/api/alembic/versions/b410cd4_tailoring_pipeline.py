"""add tailoring pipeline tables

Revision ID: b410cd4
Revises: c9d0e1f2a3b4
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b410cd4"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "candidate_facts",
        sa.Column("usability", sa.String(), server_default="ACTIVE", nullable=False),
    )
    op.alter_column("candidate_facts", "usability", server_default=None)
    op.create_index("ix_candidate_facts_usability", "candidate_facts", ["usability"])

    op.create_table(
        "ai_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("validated_output", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), server_default="started", nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "application_packets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("fact_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("bullets", postgresql.JSONB(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("resume_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("rejected_claims", postgresql.JSONB(), nullable=True),
        sa.Column(
            "ai_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_runs.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("job_id", "profile_version", name="uq_packet_job_profile_version"),
    )
    op.create_index("ix_packets_status", "application_packets", ["status"])

    op.create_table(
        "answer_bank",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("archetype", sa.String(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("times_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute("ALTER TABLE answer_bank ALTER COLUMN embedding TYPE vector(768) USING embedding::vector")
    op.create_index(
        "ix_answer_bank_embedding",
        "answer_bank",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_answer_bank_embedding", table_name="answer_bank")
    op.drop_table("answer_bank")
    op.drop_index("ix_packets_status", table_name="application_packets")
    op.drop_table("application_packets")
    op.drop_table("ai_runs")
    op.drop_index("ix_candidate_facts_usability", table_name="candidate_facts")
    op.drop_column("candidate_facts", "usability")
