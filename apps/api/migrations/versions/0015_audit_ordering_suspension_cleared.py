"""Add ``ordering_suspension_cleared`` to the ``audit_event_type`` enum.

The admin endpoint ``POST /users/{id}/clear-ordering-suspension`` logs an
audit event of this type. ``audit_event_type`` is a native PostgreSQL enum
(created in 0001 with a fixed value list), so the value must be added to the
type before the endpoint can write audit rows — otherwise inserts fail with
``invalid input value for enum audit_event_type``.

``ALTER TYPE ... ADD VALUE IF NOT EXISTS`` is a no-op when the value is
already present (idempotent), and PostgreSQL 12+ permits it inside a
transaction as long as the new value is not used in the same transaction.
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_event_type "
        "ADD VALUE IF NOT EXISTS 'ordering_suspension_cleared'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    # The extra value is harmless — leave it in place.
    pass
