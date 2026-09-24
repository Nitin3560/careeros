"""Persist feed rules, explicit miss reports, and last-viewed watermark."""
from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_feed_company_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company_key", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rule IN ('block', 'aggregator')", name="ck_job_feed_company_rules_rule"),
        sa.UniqueConstraint("company_key", name="uq_job_feed_company_rules_key"),
    )
    op.create_table(
        "job_feed_misses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dedupe_key", sa.Text(), nullable=False, unique=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("found_url", sa.Text(), nullable=True),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_reported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_reported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("cause IN ('not_polled', 'filtered_out', 'wrong_classification')", name="ck_job_feed_misses_cause"),
    )
    op.create_index("ix_job_feed_misses_created", "job_feed_misses", ["last_reported_at"])
    op.create_table(
        "job_feed_coverage_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("found_url", sa.Text(), nullable=True),
        sa.Column("was_in_feed", sa.Boolean(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("cause IS NULL OR cause IN ('not_polled', 'filtered_out', 'wrong_classification')", name="ck_job_feed_coverage_cause"),
        sa.CheckConstraint("(was_in_feed AND cause IS NULL) OR (NOT was_in_feed AND cause IS NOT NULL)", name="ck_job_feed_coverage_cause_matches_result"),
    )
    op.create_index("ix_job_feed_coverage_checked", "job_feed_coverage_checks", ["checked_at"])
    op.create_table(
        "job_feed_state",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("id = 1", name="ck_job_feed_state_singleton"),
    )
    op.execute("INSERT INTO job_feed_state (id) VALUES (1)")
    op.execute("""
        INSERT INTO job_feed_company_rules (company_key, company_name, rule, reason)
        VALUES ('jobgether', 'Jobgether', 'aggregator', 'Second-hand job aggregator')
        ON CONFLICT (company_key) DO NOTHING
    """)
    op.create_index(
        "ix_jobs_classified_feed_recent", "jobs", ["first_seen_at", "board_id"],
        postgresql_where=sa.text("expired_at IS NULL AND classifier_version IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_classified_feed_recent", table_name="jobs")
    op.drop_table("job_feed_state")
    op.drop_index("ix_job_feed_coverage_checked", table_name="job_feed_coverage_checks")
    op.drop_table("job_feed_coverage_checks")
    op.drop_index("ix_job_feed_misses_created", table_name="job_feed_misses")
    op.drop_table("job_feed_misses")
    op.drop_table("job_feed_company_rules")
