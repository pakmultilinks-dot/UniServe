"""Initial database setup — empty migrations directory.

Revision ID: 0000
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema extension and UUID support."""
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")


def downgrade() -> None:
    """Remove extensions."""
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
