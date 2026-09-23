"""Cafeteria service — business logic for cafeteria management."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsException, NotFoundException
from app.modules.cafeterias.models import Cafeteria, CafeteriaType, OperationalStatus

logger = structlog.get_logger(__name__)


class CafeteriaService:
    """Service for cafeteria CRUD and status management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_cafeteria(
        self,
        *,
        name: str,
        cafeteria_type: CafeteriaType,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        location: str | None = None,
        operating_hours: str | None = None,
        timezone: str = "Asia/Karachi",
    ) -> Cafeteria:
        """Create a new cafeteria (admin only)."""
        # Check uniqueness
        existing = await self.db.execute(select(Cafeteria).where(Cafeteria.name == name))
        if existing.scalar_one_or_none():
            raise AlreadyExistsException("Cafeteria", name)

        cafeteria = Cafeteria(
            name=name,
            type=cafeteria_type,
            description=description,
            phone=phone,
            email=email,
            location=location,
            operating_hours=operating_hours,
            timezone=timezone,
            operational_status=OperationalStatus.OPEN,
            is_active=True,
        )
        self.db.add(cafeteria)
        await self.db.flush()
        logger.info("cafeteria_created", cafeteria_id=cafeteria.id, name=name)
        return cafeteria

    async def list_cafeterias(
        self,
        *,
        is_active: bool | None = None,
        cafeteria_type: CafeteriaType | None = None,
    ) -> list[Cafeteria]:
        """List cafeterias with optional filters."""
        query = select(Cafeteria).order_by(Cafeteria.name)
        if is_active is not None:
            query = query.where(Cafeteria.is_active == is_active)
        if cafeteria_type is not None:
            query = query.where(Cafeteria.type == cafeteria_type)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_cafeteria(self, cafeteria_id: str) -> Cafeteria:
        """Get a cafeteria by ID."""
        result = await self.db.execute(select(Cafeteria).where(Cafeteria.id == cafeteria_id))
        cafeteria = result.scalar_one_or_none()
        if cafeteria is None:
            raise NotFoundException("Cafeteria", cafeteria_id)
        return cafeteria

    async def update_cafeteria(
        self,
        cafeteria_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        location: str | None = None,
        operating_hours: str | None = None,
        timezone: str | None = None,
        is_active: bool | None = None,
    ) -> Cafeteria:
        """Update cafeteria details (admin only)."""
        cafeteria = await self.get_cafeteria(cafeteria_id)

        if name is not None:
            # Check uniqueness if changing name
            existing = await self.db.execute(
                select(Cafeteria).where(Cafeteria.name == name, Cafeteria.id != cafeteria_id)
            )
            if existing.scalar_one_or_none():
                raise AlreadyExistsException("Cafeteria", name)
            cafeteria.name = name

        if description is not None:
            cafeteria.description = description
        if phone is not None:
            cafeteria.phone = phone
        if email is not None:
            cafeteria.email = email
        if location is not None:
            cafeteria.location = location
        if operating_hours is not None:
            cafeteria.operating_hours = operating_hours
        if timezone is not None:
            cafeteria.timezone = timezone
        if is_active is not None:
            cafeteria.is_active = is_active

        await self.db.flush()
        logger.info("cafeteria_updated", cafeteria_id=cafeteria_id)
        return cafeteria

    async def update_operational_status(
        self,
        cafeteria_id: str,
        status: OperationalStatus,
    ) -> Cafeteria:
        """Update cafeteria operational status (manager/admin)."""
        cafeteria = await self.get_cafeteria(cafeteria_id)
        cafeteria.operational_status = status
        await self.db.flush()
        logger.info(
            "cafeteria_status_changed",
            cafeteria_id=cafeteria_id,
            status=status.value,
        )
        return cafeteria
