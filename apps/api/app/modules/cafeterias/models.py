"""Cafeteria domain models.

Defines the cafeteria entity — the independent units that users access.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
        Enum(CafeteriaType, name="cafeteria_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    operating_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Karachi", nullable=False)
    operational_status: Mapped[OperationalStatus] = mapped_column(
        Enum(OperationalStatus, name="cafeteria_operational_status"),
        default=OperationalStatus.OPEN,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Cafeteria {self.name} ({self.type.value})>"
