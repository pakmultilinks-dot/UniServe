"""Add password failed attempts and lockout fields to user_credentials.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_credentials",
        sa.Column("password_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_credentials",
        sa.Column("password_locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_credentials", "password_locked_until")
    op.drop_column("user_credentials", "password_failed_attempts")
