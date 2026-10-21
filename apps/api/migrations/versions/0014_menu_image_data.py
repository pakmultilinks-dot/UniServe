"""Menu image bytes stored in the database.

Render's free plan has an EPHEMERAL filesystem: files written at runtime
under ``app/static/food`` are wiped on every redeploy, so uploaded menu
images 404 after the next deploy. This adds an ``image_data`` column
holding the image as a data URI (``data:image/png;base64,...``) so images
survive redeploys. ``image_url`` keeps its host-independent
``/api/v1/static/food/<file>`` form and is served by an API route that
reads the DB first and falls back to disk.

Reversible: dropping the column restores the previous schema (images
uploaded before the migration keep working via the disk fallback).
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("menu_items", sa.Column("image_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("menu_items", "image_data")
