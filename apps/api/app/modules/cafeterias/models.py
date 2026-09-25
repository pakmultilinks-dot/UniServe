"""Cafeteria domain models.

Defines the cafeteria entity — the independent units that users access.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, StrEnum


class CafeteriaType(str, enum.Enum):
    """Type of cafeteria determining access rules."""

    STUDENT = "student"  # Students and Faculty allowed
    FACULTY = "faculty"  # Only Faculty allowed


class OperationalStatus(str, enum.Enum):
    """Operational status of a cafeteria."""

    OPEN = "open"
    CLOSED = "closed"
    CLOSING_SOON = "closing_soon"
    MAINTENANCE = "maintenance"


class Cafeteria(Base):
    """A university cafeteria.

    Each cafeteria is an independent operational unit with its own
    staff, menu, and orders (in future phases).
    """

    __tablename__ = "cafeterias"
    __table_args__ = (
        Index("idx_cafeteria_type", "type"),
        Index("idx_cafeteria_is_active", "is_active"),
        Index("idx_cafeteria_status", "operational_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[CafeteriaType] = mapped_column(
        StrEnum(CafeteriaType, name="cafeteria_type", create_type=False), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    operating_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Karachi", nullable=False)
    operational_status: Mapped[OperationalStatus] = mapped_column(
        StrEnum(OperationalStatus, name="cafeteria_operational_status", create_type=False),
        default=OperationalStatus.OPEN,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Capacity (Phase 6)
    preparation_capacity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Pickup deadline: closing time for earlier-of rule (Phase 6 auto-expiry)
    closing_time: Mapped[str | None] = mapped_column(String(5), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Cafeteria {self.name} ({self.type.value})>"
