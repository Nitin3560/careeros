"""add bulk collection poller schema

Revision ID: d3e4f5a6b7c8
Revises: 91b2c3d4e5f6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "91b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ats_boards", sa.Column("tier", sa.String(), nullable=False, server_default="B"))
    op.add_column("ats_boards", sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ats_boards", sa.Column("poll_interval_seconds", sa.Integer(), nullable=False, server_default="3600"))
    op.add_column("ats_boards", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ats_boards", sa.Column("last_status_code", sa.Integer(), nullable=True))
    op.add_column("ats_boards", sa.Column("etag", sa.Text(), nullable=True))
    op.add_column("ats_boards", sa.Column("last_modified", sa.Text(), nullable=True))
    op.add_column("ats_boards", sa.Column("list_hash", sa.String(), nullable=True))
    op.add_column("ats_boards", sa.Column("company_display", sa.Text(), nullable=True))
    op.add_column("ats_boards", sa.Column("empty_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ats_boards", sa.Column("not_found_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_ats_boards_tier", "ats_boards", "tier IN ('A','B','dormant')")
    op.execute("UPDATE ats_boards SET company_display = company_name WHERE company_display IS NULL")
    op.execute("UPDATE ats_boards SET next_poll_at = now() WHERE next_poll_at IS NULL")
    op.execute("UPDATE ats_boards SET tier = CASE WHEN priority = 1 THEN 'A' ELSE 'B' END")
    op.create_index(
        "ix_ats_boards_next_poll_live",
        "ats_boards",
        ["next_poll_at"],
        unique=False,
        postgresql_where=sa.text("status <> 'dead'"),
    )

    op.add_column("jobs", sa.Column("board_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("jobs", sa.Column("raw_payload", postgresql.JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("content_hash", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("description_status", sa.String(), nullable=False, server_default="pending"))
    op.add_column("jobs", sa.Column("description_html", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("description_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("description_next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_jobs_description_status", "jobs", "description_status IN ('ok','pending','failed')"
    )
    op.create_foreign_key("fk_jobs_board_id", "jobs", "ats_boards", ["board_id"], ["id"])
    op.create_index(
        "ix_jobs_active_board_id", "jobs", ["board_id"], unique=False,
        postgresql_where=sa.text("expired_at IS NULL"),
    )
    op.create_index(
        "ix_jobs_active_first_seen_desc", "jobs", [sa.text("first_seen_at DESC")], unique=False,
        postgresql_where=sa.text("expired_at IS NULL"),
    )
    op.create_index(
        "ix_jobs_pending_description", "jobs", ["description_next_attempt_at"], unique=False,
        postgresql_where=sa.text("description_status = 'pending'"),
    )

    op.create_table(
        "poll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *[sa.Column(name, sa.Integer(), nullable=False, server_default="0") for name in (
            "boards_due", "boards_polled", "ok", "not_modified", "unchanged_hash",
            "empty", "failed", "dead", "new_jobs", "updated_jobs", "expired_jobs",
            "reappeared_jobs", "detail_fetches",
        )],
        sa.Column("p50_ms", sa.Float(), nullable=True),
        sa.Column("p95_ms", sa.Float(), nullable=True),
    )
    op.create_index("ix_poll_runs_started_at", "poll_runs", ["started_at"])
    op.execute(
        """
        INSERT INTO ats_boards
            (id, ats, slug, company_name, company_display, status, tier, priority,
             poll_interval_seconds, next_poll_at, consecutive_failures, not_found_count,
             created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'amazon', 'software-development-engineer', 'Amazon', 'Amazon',
             'unknown', 'A', 1, 900, now(), 0, 0, now(), now())
        ON CONFLICT (ats, slug) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_poll_runs_started_at", table_name="poll_runs")
    op.drop_table("poll_runs")
    op.drop_index("ix_jobs_active_first_seen_desc", table_name="jobs")
    op.drop_index("ix_jobs_pending_description", table_name="jobs")
    op.drop_index("ix_jobs_active_board_id", table_name="jobs")
    op.drop_constraint("fk_jobs_board_id", "jobs", type_="foreignkey")
    op.drop_constraint("ck_jobs_description_status", "jobs", type_="check")
    for name in ("description_next_attempt_at", "description_attempts", "description_html", "description_status", "content_hash", "raw_payload", "board_id"):
        op.drop_column("jobs", name)
    op.drop_index("ix_ats_boards_next_poll_live", table_name="ats_boards")
    op.drop_constraint("ck_ats_boards_tier", "ats_boards", type_="check")
    for name in (
        "not_found_count", "empty_since", "company_display", "list_hash", "last_modified",
        "etag", "last_status_code", "last_success_at", "poll_interval_seconds",
        "next_poll_at", "tier",
    ):
        op.drop_column("ats_boards", name)
