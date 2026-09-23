"""store sponsorship classifier rule"""
from alembic import op
import sqlalchemy as sa
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None
def upgrade(): op.add_column("jobs", sa.Column("sponsorship_rule", sa.Text(), nullable=True))
def downgrade(): op.drop_column("jobs", "sponsorship_rule")
