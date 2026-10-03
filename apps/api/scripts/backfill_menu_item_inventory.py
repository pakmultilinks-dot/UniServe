"""Backfill zero-stock inventory records for menu items missing one (P1).

Phase 43 (closing Phase 42 P1): menu items created before the Phase 41
auto-inventory fix (or seeded directly) have no inventory_items row, which
made checkout fail with a raw-UUID error. This script creates the missing
records with the same defaults as MenuService.create_menu_item:
quantity=0, unit=PORTIONS, low_threshold=10.

The item stays unavailable until staff explicitly restocks it — the script
never fabricates stock and never touches existing inventory rows.

Idempotent: safe to re-run; only rows that do not exist are created.

Usage (inside the API container, which carries the app + DB env):
    docker cp apps/api/scripts/backfill_menu_item_inventory.py uniserve_api:/app/scripts/
    docker exec uniserve_api python scripts/backfill_menu_item_inventory.py
"""

import asyncio

from app.core.database import async_session_factory
from app.modules.cafeterias.models import Cafeteria  # noqa: F401
from app.modules.inventory.service import backfill_missing_inventory_records
from app.modules.menus.models import MenuItem  # noqa: F401

# Imported so SQLAlchemy can configure mappers for related models
# (InventoryAdjustment has a relationship to User; inventory_items.cafeteria_id
# references cafeterias.id). Same pattern as the existing seed scripts.
from app.modules.users.models import User  # noqa: F401


async def main() -> None:
    async with async_session_factory() as session:
        summary = await backfill_missing_inventory_records(session)
        await session.commit()

    print("Inventory backfill complete.")
    print(f"  Menu items scanned : {summary['menu_items_scanned']}")
    print(f"  Records created    : {summary['records_created']}")
    print("  (quantity=0, unit=PORTIONS, low_threshold=10; existing rows untouched)")


if __name__ == "__main__":
    asyncio.run(main())
