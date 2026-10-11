"""PostgreSQL integration fixtures (Workstream C) — explicit opt-in only.

This module contains NO globally collectable PostgreSQL tests. Every test in
this package requires ``UNISERVE_INTEGRATION_PG=1`` plus an explicit
``POSTGRES_PASSWORD`` and a disposable target whose name starts with
``uniserve_test``. ``uniserve_prod`` is rejected. The target database is
created, migrated with the real Alembic chain, exercised, and dropped at the
end of the session.

Loop safety (pytest-asyncio 1.x): every engine is created and disposed inside
the event loop that actually uses it. Database lifecycle operations (drop /
create / identity proof) run through ``asyncio.run`` in synchronous fixtures
so no connection pool is ever shared across event loops.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

GATE = "UNISERVE_INTEGRATION_PG"
API_ROOT = Path(__file__).resolve().parents[2]
# Host/port/user default to the same settings the API itself uses; only the
# database name and password must be explicit (the stale-.env trap).
REQUIRED_ENV = ("POSTGRES_DB", "POSTGRES_PASSWORD")


def _gated_target() -> dict[str, str]:
    if os.environ.get(GATE) != "1":
        pytest.skip(
            f"PostgreSQL integration tests require {GATE}=1 (opt-in, "
            "disposable database only)"
        )
    from app.core.config import settings

    env = os.environ
    missing = [key for key in REQUIRED_ENV if not env.get(key, "").strip()]
    if missing:
        pytest.fail(
            f"{GATE}=1 but required environment variables are missing: {missing}"
        )
    db = env["POSTGRES_DB"].strip()
    if db == "uniserve_prod" or not db.startswith("uniserve_test"):
        pytest.fail(
            f"Refusing to use PostgreSQL database {db!r}: integration tests "
            "only accept disposable targets named uniserve_test*"
        )
    return {
        "host": settings.POSTGRES_HOST,
        "port": str(settings.POSTGRES_PORT),
        "user": settings.POSTGRES_USER,
        "password": env["POSTGRES_PASSWORD"],
        "database": db,
    }


def _target_url(target: dict[str, str], database: str | None = None) -> str:
    return (
        f"postgresql+asyncpg://{target['user']}:{target['password']}"
        f"@{target['host']}:{target['port']}/{database or target['database']}"
    )


async def _execute_autocommit(url: str, statement: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def _drop_database(target: dict[str, str]) -> None:
    await _execute_autocommit(
        _target_url(target, database="postgres"),
        f"DROP DATABASE IF EXISTS {target['database']}",
    )


async def _create_database(target: dict[str, str]) -> None:
    await _execute_autocommit(
        _target_url(target, database="postgres"),
        f"CREATE DATABASE {target['database']}",
    )


async def _current_database(target: dict[str, str]) -> str:
    engine = create_async_engine(_target_url(target))
    try:
        async with engine.connect() as conn:
            return str(await conn.scalar(text("SELECT current_database()")))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def pg_target() -> dict[str, str]:
    """Session-scoped target descriptor (pure data — no connections)."""
    return _gated_target()


@pytest.fixture(scope="session")
def pg_migrated(pg_target: dict[str, str]) -> dict[str, str]:
    """Drop + create the disposable database and run real Alembic migrations.

    Synchronous fixture: all lifecycle work happens in throwaway event loops
    (``asyncio.run``) or subprocesses, so no pool is shared across loops.
    """
    asyncio.run(_drop_database(pg_target))
    asyncio.run(_create_database(pg_target))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env=dict(os.environ),
        check=True,
        capture_output=True,
    )
    current = asyncio.run(_current_database(pg_target))
    if current != pg_target["database"]:
        pytest.fail(
            f"Target proof failed: connected to {current!r}, "
            f"expected {pg_target['database']!r}"
        )
    yield pg_target
    asyncio.run(_drop_database(pg_target))


@pytest_asyncio.fixture
async def pg_engine(pg_migrated: dict[str, str]):
    """Per-test engine bound to the test's own event loop."""
    engine = create_async_engine(_target_url(pg_migrated))
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_db(pg_engine):
    """Per-test session on the disposable database; committed, then closed."""
    factory = async_sessionmaker(
        pg_engine, class_=AsyncSession, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
