"""Normalize menu-item image URLs to host-independent paths (Phase 48).

Seeded and previously persisted ``menu_items.image_url`` values carried
environment-specific origins such as ``http://api.localhost/api/v1/static/food/x.jpg``
or ``http://localhost:8000/api/v1/static/food/x.jpg``. Those break on any
other host (physical Android devices on the LAN, production domains).

Phase 48's URL strategy persists the host-independent reference form::

    /api/v1/static/food/<file>

Web and mobile resolvers attach the configured API origin at render time,
so one database value works on localhost, LAN IPs, and production hosts.

DATA-ONLY migration — no schema change. Postgres-only SQL (the live target);
Alembic migrations are not exercised by the SQLite-based test suite, which
creates its schema via ``Base.metadata.create_all``.

Downgrade is intentionally a no-op: normalized relative references remain
valid in every environment; restoring environment-specific hostnames is not
meaningful data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE menu_items
        SET image_url = '/api/v1/static/food/'
            || substring(
                image_url
                FROM position('/api/v1/static/food/' IN image_url)
                + length('/api/v1/static/food/')
            )
        WHERE image_url LIKE '%/api/v1/static/food/%'
          AND image_url NOT LIKE '/api/v1/static/food/%'
        """
    )


def downgrade() -> None:
    # No-op on purpose — see module docstring.
    pass
