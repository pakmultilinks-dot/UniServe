"""Tests for cafeteria management endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.cafeterias.models import CafeteriaType
from app.modules.users.models import Role, User
from tests.conftest import assign_user_to_cafeteria, create_test_cafeteria

# ===================================================================
# Create Cafeteria
# ===================================================================


@pytest.mark.asyncio
async def test_create_cafeteria_admin(admin_client: AsyncClient):
    """Admin can create a cafeteria."""
    response = await admin_client.post(
        "/api/v1/cafeterias/",
        json={
            "name": "New Cafeteria",
            "type": "student",
            "description": "A new cafeteria",
            "phone": "+92-42-1234567",
            "location": "Building A, Ground Floor",
            "timezone": "Asia/Karachi",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Cafeteria"
    assert data["type"] == "student"
    assert data["operational_status"] == "open"
    assert data["is_active"] is True
    assert data["timezone"] == "Asia/Karachi"


@pytest.mark.asyncio
async def test_create_cafeteria_not_admin(student_client: AsyncClient):
    """Students cannot create cafeterias."""
    response = await student_client.post(
        "/api/v1/cafeterias/",
        json={"name": "Student Caf", "type": "student"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_cafeteria_duplicate_name(admin_client: AsyncClient, db):
    """Cannot create a cafeteria with a duplicate name."""
    await create_test_cafeteria(db, name="Existing Cafeteria")
    response = await admin_client.post(
        "/api/v1/cafeterias/",
        json={"name": "Existing Cafeteria", "type": "faculty"},
    )
    assert response.status_code == 409  # AlreadyExists


@pytest.mark.asyncio
async def test_create_cafeteria_validation(admin_client: AsyncClient):
    """Invalid timezone is rejected."""
    response = await admin_client.post(
        "/api/v1/cafeterias/",
        json={"name": "Bad TZ", "type": "student", "timezone": "invalid"},
    )
    assert response.status_code == 422


# ===================================================================
# List Cafeterias
# ===================================================================


@pytest.mark.asyncio
async def test_list_cafeterias_empty(admin_client: AsyncClient):
    """List cafeterias when none exist."""
    response = await admin_client.get("/api/v1/cafeterias/")
    assert response.status_code == 200
    data = response.json()
    assert data["cafeterias"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_cafeterias_with_data(admin_client: AsyncClient, db):
    """List cafeterias returns created items."""
    await create_test_cafeteria(db, name="Caf A", cafeteria_type=CafeteriaType.STUDENT)
    await create_test_cafeteria(db, name="Caf B", cafeteria_type=CafeteriaType.FACULTY)
    response = await admin_client.get("/api/v1/cafeterias/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_cafeterias_filter_type(admin_client: AsyncClient, db):
    """Filter cafeterias by type."""
    await create_test_cafeteria(db, name="Student Caf", cafeteria_type=CafeteriaType.STUDENT)
    await create_test_cafeteria(db, name="Faculty Caf", cafeteria_type=CafeteriaType.FACULTY)
    response = await admin_client.get("/api/v1/cafeterias/?cafeteria_type=faculty")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["cafeterias"][0]["name"] == "Faculty Caf"


# ===================================================================
# Get Cafeteria
# ===================================================================


@pytest.mark.asyncio
async def test_get_cafeteria(admin_client: AsyncClient, db):
    """Get a specific cafeteria by ID."""
    caf = await create_test_cafeteria(db, name="Get Me")
    response = await admin_client.get(f"/api/v1/cafeterias/{caf.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_cafeteria_not_found(admin_client: AsyncClient):
    """Get a non-existent cafeteria returns 404."""
    response = await admin_client.get("/api/v1/cafeterias/nonexistent-id")
    assert response.status_code == 404


# ===================================================================
# Update Cafeteria
# ===================================================================


@pytest.mark.asyncio
async def test_update_cafeteria_admin(admin_client: AsyncClient, db):
    """Admin can update cafeteria details."""
    caf = await create_test_cafeteria(db, name="Old Name")
    response = await admin_client.put(
        f"/api/v1/cafeterias/{caf.id}",
        json={"name": "New Name", "description": "Updated description"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_cafeteria_not_admin(manager_client: AsyncClient, db):
    """Managers cannot update cafeteria details."""
    caf = await create_test_cafeteria(db, name="Test Caf")
    response = await manager_client.put(
        f"/api/v1/cafeterias/{caf.id}",
        json={"name": "Hacked"},
    )
    assert response.status_code == 403


# ===================================================================
# Update Operational Status
# ===================================================================


@pytest.mark.asyncio
async def test_update_status_manager(manager_client: AsyncClient, db):
    """Manager can update operational status for their assigned cafeteria."""
    caf = await create_test_cafeteria(db, name="Status Caf")
    # Assign the manager to this cafeteria
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    mgr = result.scalar_one()
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    response = await manager_client.patch(
        f"/api/v1/cafeterias/{caf.id}/status",
        json={"status": "maintenance"},
    )
    assert response.status_code == 200
    assert response.json()["operational_status"] == "maintenance"


@pytest.mark.asyncio
async def test_update_status_student_forbidden(student_client: AsyncClient, db):
    """Students cannot update operational status."""
    caf = await create_test_cafeteria(db, name="Status Caf")
    response = await student_client.patch(
        f"/api/v1/cafeterias/{caf.id}/status",
        json={"status": "closed"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_status_staff_forbidden(staff_client: AsyncClient, db):
    """Staff cannot update operational status."""
    caf = await create_test_cafeteria(db, name="Status Caf")
    response = await staff_client.patch(
        f"/api/v1/cafeterias/{caf.id}/status",
        json={"status": "closed"},
    )
    assert response.status_code == 403


# ===================================================================
# Student access to faculty cafeteria is denied
# ===================================================================


@pytest.mark.asyncio
async def test_student_cannot_access_faculty_cafeteria(student_client: AsyncClient, db):
    """Students cannot access the faculty cafeteria."""
    caf = await create_test_cafeteria(db, name="Faculty Only", cafeteria_type=CafeteriaType.FACULTY)
    response = await student_client.get(f"/api/v1/cafeterias/{caf.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_faculty_can_access_student_cafeteria(faculty_client: AsyncClient, db):
    """Faculty can access the student cafeteria."""
    caf = await create_test_cafeteria(db, name="Student Caf", cafeteria_type=CafeteriaType.STUDENT)
    response = await faculty_client.get(f"/api/v1/cafeterias/{caf.id}")
    assert response.status_code == 200
