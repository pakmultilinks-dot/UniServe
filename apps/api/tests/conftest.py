"""Shared test fixtures for the UniServe test suite.

Provides:
- In-memory SQLite async database for tests
- Database session fixtures
- Pre-authenticated test users (all roles)
- Authenticated client fixtures
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from app.core.database import Base
from app.core.security import hash_password
from app.main import app
from app.modules.cafeterias.models import (
    Cafeteria,
    CafeteriaType,
    OperationalStatus,
)
from app.modules.menus.models import (
    DailyMenu,
    DailyMenuStatus,
    MenuCategory,
    MenuItem,
)
from app.modules.users.models import (
    AccountStatus,
    CafeteriaAssignment,
    Role,
    User,
    UserCategory,
    UserCredential,
    UserSession,
)

# ---------------------------------------------------------------------------
# Async engine — in-memory SQLite per test module (shared across the session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Async engine for the in-memory test database."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional session that rolls back after each test."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


# ---------------------------------------------------------------------------
# HTTPX async client — wired to the FastAPI app
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for testing API endpoints.

    Each test gets its own DB session via the ``db`` fixture, but the
    FastAPI ``get_db`` dependency is overridden per-test so requests
    hit the same in-memory database.
    """
    from app.core.database import get_db

    connection = await engine.connect()
    transaction = await connection.begin()
    test_session = AsyncSession(bind=connection, expire_on_commit=False)

    async def _override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_session.close()
    await transaction.rollback()
    await connection.close()


# ---------------------------------------------------------------------------
# Helper — create a user directly in the DB (bypasses registration)
# ---------------------------------------------------------------------------


async def create_test_user(
    db: AsyncSession,
    *,
    first_name: str = "Test",
    last_name: str = "User",
    university_id: str = "FA22-BSE-001",
    university_email: str = "test.user@lgu.edu.pk",
    password: str = "StrongPass1!",
    role: Role = Role.STUDENT,
    category: UserCategory = UserCategory.STUDENT,
    status: AccountStatus = AccountStatus.ACTIVE,
    email_verified: bool = True,
) -> User:
    """Insert a user + credential directly and return the User object."""
    user = User(
        first_name=first_name,
        last_name=last_name,
        university_id=university_id,
        university_email=university_email.lower().strip(),
        category=category,
        role=role,
        status=status,
        email_verified=email_verified,
    )
    db.add(user)
    await db.flush()

    credential = UserCredential(
        user_id=user.id,
        password_hash=hash_password(password),
    )
    db.add(credential)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# Helper — create a session + tokens for a user
# ---------------------------------------------------------------------------


async def create_user_session(
    db: AsyncSession,
    user: User,
) -> tuple[UserSession, str, str]:
    """Create a session for a user and return (session, access_token, refresh_token)."""
    import secrets

    from app.core.security import create_access_token, create_refresh_token

    session_id = secrets.token_hex(18)
    refresh_jti = secrets.token_hex(18)

    session = UserSession(
        id=session_id,
        user_id=user.id,
        refresh_token_jti=refresh_jti,
        is_active=True,
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"sid": session_id, "role": user.role.value},
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        session_id=session_id,
        jti=refresh_jti,
    )
    return session, access_token, refresh_token


# ---------------------------------------------------------------------------
# Pre-built user fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def student_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="Ali",
        last_name="Khan",
        university_id="FA22-BSE-001",
        university_email="fa22-bse-001@lgu.edu.pk",
        role=Role.STUDENT,
        category=UserCategory.STUDENT,
    )


@pytest_asyncio.fixture
async def faculty_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="Dr. Sara",
        last_name="Ahmed",
        university_id="FAC-1001",
        university_email="sara.ahmed@lgu.edu.pk",
        role=Role.FACULTY,
        category=UserCategory.FACULTY,
    )


@pytest_asyncio.fixture
async def staff_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="Staff",
        last_name="Member",
        university_id="STF-2001",
        university_email="staff@lgu.edu.pk",
        role=Role.CAFETERIA_STAFF,
        category=UserCategory.FACULTY,
    )


@pytest_asyncio.fixture
async def manager_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="Manager",
        last_name="Person",
        university_id="MGR-3001",
        university_email="manager@lgu.edu.pk",
        role=Role.CAFETERIA_MANAGER,
        category=UserCategory.FACULTY,
    )


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    return await create_test_user(
        db,
        first_name="Admin",
        last_name="User",
        university_id="ADM-4001",
        university_email="admin@lgu.edu.pk",
        role=Role.UNIVERSITY_ADMIN,
        category=UserCategory.FACULTY,
    )


# ---------------------------------------------------------------------------
# Authenticated client fixtures — include Authorization header
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def student_client(client: AsyncClient, student_user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, student_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


@pytest_asyncio.fixture
async def faculty_client(client: AsyncClient, faculty_user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, faculty_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


@pytest_asyncio.fixture
async def staff_client(client: AsyncClient, staff_user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, staff_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


@pytest_asyncio.fixture
async def manager_client(client: AsyncClient, manager_user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, manager_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User, db: AsyncSession) -> AsyncClient:
    _, access_token, _ = await create_user_session(db, admin_user)
    new_client = AsyncClient(
        transport=client._transport,
        base_url=str(client.base_url),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    yield new_client
    await new_client.aclose()


# ---------------------------------------------------------------------------
# Helper — create a cafeteria directly in the DB
# ---------------------------------------------------------------------------


async def create_test_cafeteria(
    db: AsyncSession,
    *,
    name: str = "Student Cafeteria",
    cafeteria_type: CafeteriaType = CafeteriaType.STUDENT,
    description: str | None = "Main student cafeteria",
    is_active: bool = True,
    operational_status: OperationalStatus = OperationalStatus.OPEN,
) -> Cafeteria:
    """Insert a cafeteria directly and return the Cafeteria object."""
    cafeteria = Cafeteria(
        name=name,
        type=cafeteria_type,
        description=description,
        is_active=is_active,
        operational_status=operational_status,
    )
    db.add(cafeteria)
    await db.flush()
    return cafeteria


# ---------------------------------------------------------------------------
# Helper — create a menu item directly in the DB
# ---------------------------------------------------------------------------


async def create_test_menu_item(
    db: AsyncSession,
    *,
    cafeteria_id: str,
    name: str = "Chicken Biryani",
    category: MenuCategory = MenuCategory.MAIN_COURSE,
    price: int = 25000,  # 250 PKR in paisa
    is_available: bool = True,
) -> MenuItem:
    """Insert a menu item directly and return the MenuItem object."""
    item = MenuItem(
        cafeteria_id=cafeteria_id,
        name=name,
        category=category,
        price=price,
        is_available=is_available,
    )
    db.add(item)
    await db.flush()
    return item


# ---------------------------------------------------------------------------
# Helper — create a daily menu directly in the DB
# ---------------------------------------------------------------------------


async def create_test_daily_menu(
    db: AsyncSession,
    *,
    cafeteria_id: str,
    menu_date=None,
    status: DailyMenuStatus = DailyMenuStatus.DRAFT,
    created_by: str | None = None,
) -> DailyMenu:
    """Insert a daily menu directly and return the DailyMenu object."""
    from datetime import date as date_type

    if menu_date is None:
        menu_date = date_type.today()
    daily_menu = DailyMenu(
        cafeteria_id=cafeteria_id,
        menu_date=menu_date,
        status=status,
        created_by=created_by,
    )
    db.add(daily_menu)
    await db.flush()
    return daily_menu


# ---------------------------------------------------------------------------
# Helper — assign a user to a cafeteria (required for staff/manager scope)
# ---------------------------------------------------------------------------


async def assign_user_to_cafeteria(
    db: AsyncSession,
    user_id: str,
    cafeteria_id: str,
    role: Role = Role.CAFETERIA_MANAGER,
) -> CafeteriaAssignment:
    """Create a CafeteriaAssignment linking a user to a cafeteria."""
    assignment = CafeteriaAssignment(
        user_id=user_id,
        cafeteria_id=cafeteria_id,
        role=role,
    )
    db.add(assignment)
    await db.flush()
    return assignment


# ---------------------------------------------------------------------------
# Pre-built cafeteria fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def student_cafeteria(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(
        db,
        name="Student Cafeteria",
        cafeteria_type=CafeteriaType.STUDENT,
    )


@pytest_asyncio.fixture
async def faculty_cafeteria(db: AsyncSession) -> Cafeteria:
    return await create_test_cafeteria(
        db,
        name="Faculty Cafeteria",
        cafeteria_type=CafeteriaType.FACULTY,
    )
