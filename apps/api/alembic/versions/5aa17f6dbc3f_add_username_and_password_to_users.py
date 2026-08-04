"""add username and password to users

Revision ID: 5aa17f6dbc3f
Revises: c9d6dc317543
Create Date: 2026-08-04 14:06:51.662002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5aa17f6dbc3f'
down_revision: Union[str, Sequence[str], None] = 'c9d6dc317543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.execute(
        "UPDATE users "
        "SET username = 'legacy_' || replace(id::text, '-', ''), "
        "password_hash = "
        "'$2b$12$ASOCCETlZSGsRLmh/ByroeVbJdtjpMyayC1UCysZh4ExqyCsVv2CW' "
        "WHERE username IS NULL"
    )
    op.alter_column("users", "username", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "email", existing_type=sa.VARCHAR(), nullable=True)
    op.create_unique_constraint("uq_users_username", "users", ["username"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.alter_column("users", "email", existing_type=sa.VARCHAR(), nullable=False)
    op.drop_column("users", "password_hash")
    op.drop_column("users", "username")
