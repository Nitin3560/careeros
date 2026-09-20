"""add company registry

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column("source_tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("detected_ats", sa.String(), nullable=True),
        sa.Column("detected_slug", sa.Text(), nullable=True),
        sa.Column("workday_host", sa.Text(), nullable=True),
        sa.Column("workday_tenant", sa.Text(), nullable=True),
        sa.Column("workday_site", sa.Text(), nullable=True),
        sa.Column("detection_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("detection_confidence", sa.String(), nullable=True),
        sa.Column("detection_evidence", sa.Text(), nullable=True),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ats_boards.id"), nullable=True),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("detection_status IN ('pending','detected','unsupported','not_found','error')", name="ck_company_registry_detection_status"),
        sa.CheckConstraint("detection_confidence IS NULL OR detection_confidence IN ('high','medium','low')", name="ck_company_registry_detection_confidence"),
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_company_registry_name_domain
        ON company_registry (lower(company_name), coalesce(domain, ''))
    """)
    op.create_index("ix_company_registry_detection", "company_registry", ["detection_status", "last_detected_at"])
    op.create_index("ix_company_registry_board_id", "company_registry", ["board_id"])


def downgrade() -> None:
    op.drop_index("ix_company_registry_board_id", table_name="company_registry")
    op.drop_index("ix_company_registry_detection", table_name="company_registry")
    op.drop_index("uq_company_registry_name_domain", table_name="company_registry")
    op.drop_table("company_registry")
