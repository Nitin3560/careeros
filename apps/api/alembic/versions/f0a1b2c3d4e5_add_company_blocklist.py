"""Add company slugs excluded from the daily classified feed."""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e5"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


AGGREGATOR_SLUGS = (
    "globalelitecareers", "usasurveyjob", "svetness", "boxlunch", "centriaautism",
    "insomniacookies", "bestversionmedia", "urpt", "blueskytelepsych",
    "liquidpersonnel", "jobgether",
)


def upgrade() -> None:
    op.create_table(
        "company_blocklist",
        sa.Column("slug", sa.Text(), primary_key=True),
        sa.Column("ats", sa.Text(), nullable=False, server_default="*"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "misses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_misses_created_at", "misses", ["created_at"])
    connection = op.get_bind()
    connection.execute(
        sa.text("INSERT INTO company_blocklist (slug, ats, reason) VALUES (:slug, '*', 'aggregator')"),
        [{"slug": slug} for slug in AGGREGATOR_SLUGS],
    )


def downgrade() -> None:
    op.drop_index("ix_misses_created_at", table_name="misses")
    op.drop_table("misses")
    op.drop_table("company_blocklist")
