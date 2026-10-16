"""Database engine and session management.

Provides async SQLAlchemy engine, session factory, and base model class.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import Enum
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def StrEnum(*args: Any, **kwargs: Any) -> Enum:  # noqa: N802 — intentional alias name
    """Create an Enum that stores .value (string) instead of .name.

    By default, SQLAlchemy's Enum type uses the Python enum member NAME
    (e.g. "STUDENT") for PostgreSQL storage. Our migrations create enum
    types with lowercase VALUES (e.g. "student"). This helper tells
    SQLAlchemy to use .value instead of .name so they match.
    """
    kwargs.setdefault("values_callable", lambda obj: [e.value for e in obj])
    return Enum(*args, **kwargs)


def escape_like(value: str) -> str:
    """Escape LIKE special characters in user-supplied search input.

    A raw ``%`` or ``_`` in user input acts as a wildcard inside ``ilike()``
    (LIKE injection: result-set manipulation). Escape them so the input is
    matched literally. Use with ``.ilike(pattern, escape="\\")``.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session.

    Yields a session and ensures proper cleanup.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
