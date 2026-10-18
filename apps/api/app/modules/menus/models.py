"""Menu domain models.

Defines menu items, daily menus, and menu favorites for the cafeteria system.
"""

import enum
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.users.models import User

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, StrEnum

# ---- Menu Category ----


class MenuCategory(str, enum.Enum):
    """Fixed menu item categories."""

    BREAKFAST = "breakfast"
    MAIN_COURSE = "main_course"
    SIDE_DISH = "side_dish"
    DESSERT = "dessert"
    BEVERAGE = "beverage"
    SNACK = "snack"
    SALAD = "salad"
    SOUP = "soup"


# ---- Daily Menu Status ----


class DailyMenuStatus(str, enum.Enum):
    """Status of a daily menu."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ---- Menu Item ----


class MenuItem(Base):
    """A menu item offered by a cafeteria.

    Menu items are reusable across multiple daily menus.
    They belong to exactly one cafeteria.
    """

    __tablename__ = "menu_items"
    __table_args__ = (
        Index("idx_menu_item_cafeteria", "cafeteria_id"),
        Index("idx_menu_item_category", "category"),
        Index("idx_menu_item_is_active", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[MenuCategory] = mapped_column(
        StrEnum(MenuCategory, name="menu_category", create_type=False), nullable=False
    )
    price: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Price in smallest currency unit (paisa)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Image bytes as a data URI ("data:image/png;base64,...").
    # Render's free plan has an EPHEMERAL filesystem: files written under
    # app/static/food at runtime are wiped on every redeploy, so uploaded
    # images must live in the database. image_url keeps its host-independent
    # "/api/v1/static/food/<file>" form and is served by the API route.
    image_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    dietary_info: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: vegetarian, halal, etc.
    allergens: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: nuts, dairy, gluten, etc.
    preparation_time_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    daily_menu_items: Mapped[list["DailyMenuItem"]] = relationship(
        "DailyMenuItem", back_populates="menu_item", lazy="selectin"
    )
    favorites: Mapped[list["MenuFavorite"]] = relationship(
        "MenuFavorite", back_populates="menu_item", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MenuItem {self.name} ({self.category.value})>"


# ---- Daily Menu ----


class DailyMenu(Base):
    """A daily menu for a specific cafeteria on a specific date.

    Menus start as drafts, can have items added/removed,
    and are published when ready for students to view.
    Published menus are immutable (historical preservation).
    """

    __tablename__ = "daily_menus"
    __table_args__ = (
        Index("idx_daily_menu_cafeteria", "cafeteria_id"),
        Index("idx_daily_menu_date", "menu_date"),
        Index("idx_daily_menu_status", "status"),
        # Phase 44 (WS4): one ACTIVE menu per cafeteria/date. ARCHIVED
        # daily menus (unpublished) are excluded so a replacement draft
        # can be created for the same date after unpublishing.
        Index(
            "uq_daily_menu_cafeteria_date_active",
            "cafeteria_id",
            "menu_date",
            unique=True,
            postgresql_where=text("status != 'archived'"),
            sqlite_where=text("status != 'archived'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cafeteria_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cafeterias.id", ondelete="CASCADE"), nullable=False
    )
    menu_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DailyMenuStatus] = mapped_column(
        StrEnum(DailyMenuStatus, name="daily_menu_status", create_type=False),
        default=DailyMenuStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    items: Mapped[list["DailyMenuItem"]] = relationship(
        "DailyMenuItem", back_populates="daily_menu", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DailyMenu {self.menu_date} ({self.status.value})>"


# ---- Daily Menu Item (Junction) ----


class DailyMenuItem(Base):
    """Junction between DailyMenu and MenuItem.

    Tracks which items are on a daily menu and their display order.
    Published menus preserve historical prices via special_price.
    """

    __tablename__ = "daily_menu_items"
    __table_args__ = (
        Index("idx_daily_menu_item_menu", "daily_menu_id"),
        Index("idx_daily_menu_item_item", "menu_item_id"),
        UniqueConstraint("daily_menu_id", "menu_item_id", name="uq_daily_menu_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    daily_menu_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_menus.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    special_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Override price for this day
    is_available_today: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    daily_menu: Mapped["DailyMenu"] = relationship("DailyMenu", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="daily_menu_items")

    def __repr__(self) -> str:
        return f"<DailyMenuItem menu={self.daily_menu_id} item={self.menu_item_id}>"


# ---- Menu Favorite ----


class MenuFavorite(Base):
    """A user's favorite menu item.

    Students and faculty can mark items as favorites for quick access.
    """

    __tablename__ = "menu_favorites"
    __table_args__ = (
        Index("idx_menu_favorite_user", "user_id"),
        Index("idx_menu_favorite_item", "menu_item_id"),
        UniqueConstraint("user_id", "menu_item_id", name="uq_menu_favorite"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    menu_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")  # noqa: F821
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="favorites")

    def __repr__(self) -> str:
        return f"<MenuFavorite user={self.user_id} item={self.menu_item_id}>"
