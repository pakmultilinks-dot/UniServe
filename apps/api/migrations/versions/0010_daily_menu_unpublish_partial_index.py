"""Allow a replacement daily menu after unpublishing (partial unique index).

The original ``uq_daily_menu_cafeteria_date`` unique constraint applied to
every daily menu row, including ARCHIVED ones. Phase 44 (WS4) unpublishing
archives a published daily menu so a replacement draft can be created for
the same date, so the constraint is replaced by a partial unique index that
excludes archived menus: one ACTIVE (draft/published) menu per
cafeteria/date, archived menus free the slot.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_daily_menu_cafeteria_date", "daily_menus", type_="unique")
    op.create_index(
        "uq_daily_menu_cafeteria_date_active",
        "daily_menus",
        ["cafeteria_id", "menu_date"],
        unique=True,
        postgresql_where=sa.text("status != 'archived'"),
        sqlite_where=sa.text("status != 'archived'"),
    )


def downgrade() -> None:
    # NOTE: re-adding the plain unique constraint fails if archived and
    # active menus share a cafeteria/date — the situation this migration
    # intentionally allows. Remove archived duplicates (keep the active
    # menu) before restoring the constraint.
    op.execute(
        """
        DELETE FROM daily_menus dm
        USING daily_menus keep
        WHERE dm.cafeteria_id = keep.cafeteria_id
          AND dm.menu_date = keep.menu_date
          AND dm.id <> keep.id
          AND dm.status = 'archived'
          AND keep.status <> 'archived'
        """
    )
    op.drop_index("uq_daily_menu_cafeteria_date_active", table_name="daily_menus")
    op.create_unique_constraint(
        "uq_daily_menu_cafeteria_date", "daily_menus", ["cafeteria_id", "menu_date"]
    )
