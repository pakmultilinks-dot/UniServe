"""Seed a realistic Student Cafeteria menu for local development.

Run from apps/api after migrations:
    python scripts/seed_student_cafeteria.py

The seed is idempotent: rerunning it updates the demo records instead of
creating duplicate cafeterias, menu items, or daily-menu entries.
"""

import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.cafeterias.models import Cafeteria, CafeteriaType, OperationalStatus
from app.modules.inventory.models import InventoryItem, InventoryUnit
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuItem,
    DailyMenuStatus,
    MenuCategory,
    MenuItem,
)
from app.modules.users.models import User  # noqa: F401

STUDENT_CAFETERIA = {
    "name": "Student Cafeteria",
    "type": CafeteriaType.STUDENT,
    "description": "Affordable meals, snacks, and drinks for the university community.",
    "location": "Main Campus, Ground Floor",
    "operating_hours": "08:00-20:00",
    "timezone": "Asia/Karachi",
}

MENU_ITEMS = [
    {
        "name": "Chicken Biryani",
        "description": "Fragrant basmati rice with spiced chicken and raita.",
        "category": MenuCategory.MAIN_COURSE,
        "price": 22000,
        "preparation_time_minutes": 15,
        "image_url": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Chicken Korma",
        "description": "Creamy, gently spiced chicken curry served with naan or rice.",
        "category": MenuCategory.MAIN_COURSE,
        "price": 24000,
        "preparation_time_minutes": 18,
        "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Daily Salan",
        "description": "The kitchen's fresh daily curry with a rotating seasonal recipe.",
        "category": MenuCategory.MAIN_COURSE,
        "price": 18000,
        "preparation_time_minutes": 12,
        "image_url": "https://images.unsplash.com/photo-1601050690117-94f5f6fa8bd7?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Paratha Roll",
        "description": "Crisp paratha wrapped around seasoned chicken, salad, and sauce.",
        "category": MenuCategory.SNACK,
        "price": 16000,
        "preparation_time_minutes": 10,
        "image_url": "https://images.unsplash.com/photo-1628294895950-9805252327bc?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Samosa",
        "description": "Golden pastry filled with spiced potato and peas.",
        "category": MenuCategory.SNACK,
        "price": 5000,
        "preparation_time_minutes": 5,
        "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Finger Fries",
        "description": "Crisp seasoned fries served hot.",
        "category": MenuCategory.SIDE_DISH,
        "price": 10000,
        "preparation_time_minutes": 8,
        "image_url": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Chai",
        "description": "Freshly brewed milk tea with cardamom.",
        "category": MenuCategory.BEVERAGE,
        "price": 6000,
        "preparation_time_minutes": 5,
        "image_url": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Coffee",
        "description": "Hot brewed coffee for a quick campus pick-me-up.",
        "category": MenuCategory.BEVERAGE,
        "price": 9000,
        "preparation_time_minutes": 5,
        "image_url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Milkshake",
        "description": "Cold, creamy milkshake available in rotating flavors.",
        "category": MenuCategory.BEVERAGE,
        "price": 15000,
        "preparation_time_minutes": 7,
        "image_url": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Coca-Cola",
        "description": "Chilled canned soft drink.",
        "category": MenuCategory.BEVERAGE,
        "price": 8000,
        "preparation_time_minutes": 1,
        "image_url": "https://images.unsplash.com/photo-1629203849820-fdd70d49c38e?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Fanta",
        "description": "Chilled orange soft drink.",
        "category": MenuCategory.BEVERAGE,
        "price": 8000,
        "preparation_time_minutes": 1,
        "image_url": "https://images.unsplash.com/photo-1624517452488-04869289c4ca?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Bottled Water",
        "description": "Sealed bottled drinking water.",
        "category": MenuCategory.BEVERAGE,
        "price": 5000,
        "preparation_time_minutes": 1,
        "image_url": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?auto=format&fit=crop&w=800&q=85",
    },
    {
        "name": "Packet Cake",
        "description": "Individually packed slice of soft vanilla cake.",
        "category": MenuCategory.DESSERT,
        "price": 7000,
        "preparation_time_minutes": 1,
        "image_url": "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=800&q=85",
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        cafeteria_result = await session.execute(
            select(Cafeteria).where(Cafeteria.name == STUDENT_CAFETERIA["name"])
        )
        cafeteria = cafeteria_result.scalar_one_or_none()
        if cafeteria is None:
            cafeteria = Cafeteria(**STUDENT_CAFETERIA, operational_status=OperationalStatus.OPEN, is_active=True)
            session.add(cafeteria)
            await session.flush()
        else:
            for key, value in STUDENT_CAFETERIA.items():
                setattr(cafeteria, key, value)
            cafeteria.operational_status = OperationalStatus.OPEN
            cafeteria.is_active = True

        items_by_name: dict[str, MenuItem] = {}
        for item_data in MENU_ITEMS:
            result = await session.execute(
                select(MenuItem).where(
                    MenuItem.cafeteria_id == cafeteria.id,
                    MenuItem.name == item_data["name"],
                )
            )
            item = result.scalar_one_or_none()
            if item is None:
                item = MenuItem(cafeteria_id=cafeteria.id, **item_data)
                session.add(item)
            else:
                for key, value in item_data.items():
                    setattr(item, key, value)
                item.is_active = True
            item.is_available = item.name != "Packet Cake"
            items_by_name[item.name] = item
        await session.flush()

        for item in items_by_name.values():
            inventory_result = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.cafeteria_id == cafeteria.id,
                    InventoryItem.menu_item_id == item.id,
                )
            )
            inventory = inventory_result.scalar_one_or_none()
            if inventory is None:
                session.add(
                    InventoryItem(
                        cafeteria_id=cafeteria.id,
                        menu_item_id=item.id,
                        quantity=100,
                        unit=InventoryUnit.PORTIONS,
                        low_threshold=10,
                    )
                )
            else:
                inventory.quantity = 100
                inventory.unit = InventoryUnit.PORTIONS
                inventory.low_threshold = 10
        await session.flush()

        menu_result = await session.execute(
            select(DailyMenu).where(
                DailyMenu.cafeteria_id == cafeteria.id,
                DailyMenu.menu_date == date.today(),
            )
        )
        daily_menu = menu_result.scalar_one_or_none()
        if daily_menu is None:
            daily_menu = DailyMenu(
                cafeteria_id=cafeteria.id,
                menu_date=date.today(),
                status=DailyMenuStatus.PUBLISHED,
                published_at=datetime.now(UTC),
            )
            session.add(daily_menu)
            await session.flush()
        else:
            daily_menu.status = DailyMenuStatus.PUBLISHED
            daily_menu.published_at = daily_menu.published_at or datetime.now(UTC)

        existing_result = await session.execute(
            select(DailyMenuItem).where(DailyMenuItem.daily_menu_id == daily_menu.id)
        )
        existing = {entry.menu_item_id: entry for entry in existing_result.scalars().all()}
        for display_order, item in enumerate(items_by_name.values()):
            entry = existing.get(item.id)
            if entry is None:
                session.add(
                    DailyMenuItem(
                        daily_menu_id=daily_menu.id,
                        menu_item_id=item.id,
                        is_available_today=True,
                        display_order=display_order,
                    )
                )
            else:
                entry.is_available_today = True
                entry.display_order = display_order

        await session.commit()
        print(f"Seeded {len(items_by_name)} Student Cafeteria items for {date.today()}.")


if __name__ == "__main__":
    asyncio.run(seed())
