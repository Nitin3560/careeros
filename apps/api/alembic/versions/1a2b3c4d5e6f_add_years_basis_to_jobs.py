"""store the experience parsing rule used by the classifier"""
from alembic import op
import sqlalchemy as sa

revision = "1a2b3c4d5e6f"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("years_basis", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("jobs", "years_basis")
