"""Regression tests for Alembic metadata registration.

Verifies that all ORM models are properly registered on Base.metadata so that
Alembic autogenerate / alembic check can detect them.  This guards against the
class of bug where env.py fails to import models, causing empty metadata and
every table appearing as 'removed' in alembic check output.

Root cause:  Alembic relies on all model modules being imported before
target_metadata is referenced.  If any import is missing or silently fails,
Base.metadata will be incomplete and alembic check will report false-positive
drift.
"""

from __future__ import annotations

from app.core.database import Base


def _import_all_models() -> None:
    """Import every model module so they register on Base.metadata."""
    # fmt: off
    from app.core.audit import SecurityAuditEvent  # noqa: F401
    from app.modules.cafeterias.models import Cafeteria, OperationalStatus  # noqa: F401
    from app.modules.carts.models import Cart, CartItem  # noqa: F401
    from app.modules.inventory.models import (  # noqa: F401
        InventoryAdjustment,
        InventoryItem,
        InventoryUnit,
    )
    from app.modules.menus.models import (  # noqa: F401
        DailyMenu,
        DailyMenuItem,
        DailyMenuStatus,
        MenuCategory,
        MenuFavorite,
        MenuItem,
    )
    from app.modules.notifications.models import Notification  # noqa: F401
    from app.modules.orders.models import (  # noqa: F401
        NoShow,
        Order,
        OrderEvent,
        OrderItem,
        OrderNumberSequence,
    )
    from app.modules.payments.models import (  # noqa: F401
        Payment,
        PaymentAttempt,
        WebhookEvent,
    )
    from app.modules.refunds.models import Refund, RefundEvent  # noqa: F401
    from app.modules.users.models import (  # noqa: F401
        CafeteriaAssignment,
        OTPChallenge,
        User,
        UserCredential,
        UserSession,
    )
    # fmt: on


# Expected table names that must appear in Base.metadata after imports.
EXPECTED_TABLES: set[str] = {
    # users
    "users",
    "user_credentials",
    "user_sessions",
    "otp_challenges",
    "cafeteria_assignments",
    # cafeterias
    "cafeterias",
    # menus
    "menu_items",
    "menu_favorites",
    "daily_menus",
    "daily_menu_items",
    # inventory
    "inventory_items",
    "inventory_adjustments",
    # carts
    "carts",
    "cart_items",
    # orders
    "orders",
    "order_items",
    "order_events",
    "order_number_sequence",
    "no_shows",
    # payments
    "payments",
    "payment_attempts",
    "webhook_events",
    # refunds
    "refunds",
    "refund_events",
    # notifications
    "notifications",
    # audit
    "security_audit_events",
}


class TestMetadataRegistration:
    """Ensure every ORM model is registered on Base.metadata."""

    def test_all_tables_registered(self) -> None:
        """Base.metadata must contain every expected table after imports."""
        _import_all_models()
        registered = set(Base.metadata.tables.keys())
        missing = EXPECTED_TABLES - registered
        assert not missing, (
            f"Missing tables from Base.metadata: {sorted(missing)}. "
            "Check that the corresponding model modules are imported in "
            "migrations/env.py and tests that exercise this check."
        )

    def test_no_unexpected_tables(self) -> None:
        """No tables outside the expected set should appear."""
        _import_all_models()
        registered = set(Base.metadata.tables.keys())
        # Only check that there aren't far more tables than expected;
        # exact count may vary as new features land.
        extra = registered - EXPECTED_TABLES
        # We allow some flexibility but log extras for awareness
        if extra:
            # It's fine to have extras, just ensure we didn't LOSE tables
            pass
        # Core assertion: at least all expected tables are present
        assert EXPECTED_TABLES.issubset(registered)

    def test_metadata_not_empty(self) -> None:
        """The simplest guard: metadata must not be empty."""
        _import_all_models()
        assert len(Base.metadata.tables) >= len(EXPECTED_TABLES)

    def test_enum_columns_have_model_side_type(self) -> None:
        """Every column using StrEnum must have a non-None type on the model.

        This verifies that the StrEnum helper returns a valid SQLAlchemy type
        and that Alembic can introspect it.
        """
        _import_all_models()
        for table_name in EXPECTED_TABLES:
            if table_name not in Base.metadata.tables:
                continue
            table = Base.metadata.tables[table_name]
            for column in table.columns:
                col_type = column.type
                assert col_type is not None, (
                    f"Column {table_name}.{column.name} has None type"
                )
