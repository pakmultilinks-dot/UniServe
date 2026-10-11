"""Phase 48 — Cafeteria management + menu-image upload tests.

Cafeteria (48A): creation/validation/duplicate/authorization + the
deactivation-safety guarantee (is_active is a filter flag only — menu
items, cafeteria assignments and users must survive a status change).

Images (48B): upload/replace/remove through the real endpoints with magic-
byte validation, size caps, RBAC, shared-reference file safety and
host-independent persisted references.
"""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.menus.models import MenuItem
from app.modules.users.models import CafeteriaAssignment, Role, User
from tests.conftest import (
    assign_user_to_cafeteria,
    create_test_cafeteria,
    create_test_menu_item,
)

# Minimal genuinely-valid 1x1 PNG (magic bytes correct — the only thing the
# backend validates; the file is never decoded server-side).
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c626001000000ffff03000006000557bfabd4000000"
    "0049454e44ae426082"
)

# JPEG: valid SOI/APP0/EOI markers — sufficient for magic-byte validation.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64 + b"\xff\xd9"


@pytest.fixture
def image_storage(tmp_path, monkeypatch):
    """Point the image store at a per-test temp dir — never app/static/food."""
    import app.modules.menus.service as menu_service

    monkeypatch.setattr(menu_service, "MENU_IMAGE_DIR", str(tmp_path))
    return tmp_path


async def _get_manager_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.role == Role.CAFETERIA_MANAGER))
    return result.scalar_one()


# ===================================================================
# 48A — Cafeteria management
# ===================================================================


@pytest.mark.asyncio
async def test_a_admin_can_create_cafeteria(admin_client: AsyncClient, db):
    """A. Admin creates a cafeteria through the real endpoint."""
    response = await admin_client.post(
        "/api/v1/cafeterias/",
        json={
            "name": "Phase48 Test Cafeteria",
            "type": "student",
            "description": "Created by Phase 48 E2E",
            "location": "Annex Block",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Phase48 Test Cafeteria"
    assert data["type"] == "student"
    assert data["is_active"] is True
    assert data["operational_status"] == "open"


@pytest.mark.asyncio
async def test_b_invalid_cafeteria_request_rejected(admin_client: AsyncClient):
    """B. Invalid requests (empty name / bad type / bad timezone) rejected."""
    bad_empty_name = await admin_client.post(
        "/api/v1/cafeterias/", json={"name": "", "type": "student"}
    )
    assert bad_empty_name.status_code == 422

    bad_type = await admin_client.post(
        "/api/v1/cafeterias/", json={"name": "Bad Type", "type": "nonexistent"}
    )
    assert bad_type.status_code == 422

    bad_timezone = await admin_client.post(
        "/api/v1/cafeterias/",
        json={"name": "Bad TZ", "type": "student", "timezone": "NotATZ"},
    )
    assert bad_timezone.status_code == 422


@pytest.mark.asyncio
async def test_c_duplicate_cafeteria_conflict(admin_client: AsyncClient, db):
    """C. Duplicate name → 409 per existing backend rules."""
    first = await admin_client.post(
        "/api/v1/cafeterias/", json={"name": "Dup Cafeteria", "type": "faculty"}
    )
    assert first.status_code == 201

    duplicate = await admin_client.post(
        "/api/v1/cafeterias/", json={"name": "Dup Cafeteria", "type": "student"}
    )
    assert duplicate.status_code == 409
    assert "Cafeteria already exists" in duplicate.json()["detail"]


@pytest.mark.asyncio
async def test_d_non_admin_cannot_create_cafeteria(
    student_client: AsyncClient, staff_client: AsyncClient, manager_client: AsyncClient
):
    """D. Non-admin roles are refused cafeteria creation."""
    payload = {"name": "Nope", "type": "student"}
    for client in (student_client, staff_client, manager_client):
        response = await client.post("/api/v1/cafeterias/", json=payload)
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_e_deactivation_preserves_assignments_menu_and_users(
    admin_client: AsyncClient, manager_user: User, db
):
    """E. Deactivation is a flag — assignments, menu items and users survive."""
    preserved = await create_test_cafeteria(db, name="Preexisting Cafeteria")
    caf = await create_test_cafeteria(db, name="Keep Me Cafeteria")
    mgr = manager_user
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Survivor Dish")

    response = await admin_client.put(
        f"/api/v1/cafeterias/{caf.id}", json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Assignment intact
    assignment = await db.execute(
        select(CafeteriaAssignment).where(CafeteriaAssignment.user_id == mgr.id)
    )
    assert assignment.scalar_one_or_none() is not None
    # Menu item intact
    still_there = await db.execute(
        select(MenuItem).where(MenuItem.id == item.id)
    )
    assert still_there.scalar_one() is not None
    # User intact
    user = await db.execute(select(User).where(User.id == mgr.id))
    assert user.scalar_one() is not None
    # Pre-existing cafeterias still listed alongside the deactivated one
    listing = await admin_client.get("/api/v1/cafeterias/")
    assert listing.status_code == 200
    names = {c["name"] for c in listing.json()["cafeterias"]}
    assert "Keep Me Cafeteria" in names
    assert "Preexisting Cafeteria" in names


@pytest.mark.asyncio
async def test_f_update_cafeteria_admin_only_and_status_regression(
    admin_client: AsyncClient, manager_client: AsyncClient, db
):
    """F. PUT is admin-only; operational-status PATCH keeps working."""
    caf = await create_test_cafeteria(db, name="Authz Cafeteria")

    forbidden = await manager_client.put(
        f"/api/v1/cafeterias/{caf.id}", json={"is_active": False}
    )
    assert forbidden.status_code == 403

    renamed = await admin_client.put(
        f"/api/v1/cafeterias/{caf.id}", json={"name": "Renamed Cafeteria"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed Cafeteria"

    status = await admin_client.patch(
        f"/api/v1/cafeterias/{caf.id}/status", json={"status": "maintenance"}
    )
    assert status.status_code == 200
    assert status.json()["operational_status"] == "maintenance"


# ===================================================================
# 48B — Menu item images
# ===================================================================


async def _create_item_via_api(
    admin_client: AsyncClient, db, *, name: str = "Image Test Dish"
) -> tuple[str, str]:
    """Create a cafeteria + menu item through the real API; return ids."""
    caf = await admin_client.post(
        "/api/v1/cafeterias/",
        json={"name": f"Img Caf {name}", "type": "student"},
    )
    assert caf.status_code == 201
    caf_id = caf.json()["id"]
    item = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/",
        json={"name": name, "category": "main_course", "price": 25000},
    )
    assert item.status_code == 201
    return caf_id, item.json()["id"]


@pytest.mark.asyncio
async def test_g_valid_image_upload_succeeds(
    admin_client: AsyncClient, db, image_storage
):
    """G + K + P. Valid upload persists a host-independent reference."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Upload Dish")

    response = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=PNG_1PX,
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["image_url"] is not None
    assert data["image_url"].startswith("/api/v1/static/food/")
    assert data["image_url"].endswith(".png")
    assert "localhost" not in data["image_url"]
    assert "127.0.0.1" not in data["image_url"]
    assert "api.localhost" not in data["image_url"]
    # File physically written to the (patched) store with a generated name
    files = os.listdir(image_storage)
    assert len(files) == 1
    assert files[0].endswith(".png")
    assert "/" not in files[0] and "\\" not in files[0]
    # Reference is persisted — a fresh GET returns the same value
    fresh = await admin_client.get(f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}")
    assert fresh.json()["image_url"] == data["image_url"]


@pytest.mark.asyncio
async def test_h_invalid_file_type_rejected(
    admin_client: AsyncClient, db, image_storage
):
    """H. Wrong MIME, wrong magic bytes and non-image bodies are rejected."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="BadType Dish")

    not_an_image = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=b"<html>definitely not an image</html>",
        headers={"Content-Type": "image/png"},
    )
    assert not_an_image.status_code == 400
    assert "Unsupported image type" in not_an_image.json()["detail"]

    text_plain = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=b"hello",
        headers={"Content-Type": "text/plain"},
    )
    assert text_plain.status_code == 400

    mismatch = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=JPEG_BYTES,
        headers={"Content-Type": "image/png"},
    )
    assert mismatch.status_code == 400
    assert "does not match its declared image type" in mismatch.json()["detail"]

    # Nothing was stored or referenced
    fresh = await admin_client.get(f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}")
    assert fresh.json()["image_url"] is None
    assert os.listdir(image_storage) == []


@pytest.mark.asyncio
async def test_i_oversized_image_rejected(
    admin_client: AsyncClient, db, image_storage, monkeypatch
):
    """I. Oversized uploads are rejected before any file is written."""
    import app.modules.menus.service as menu_service

    monkeypatch.setattr(menu_service, "MAX_MENU_IMAGE_BYTES", 64)
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Big Dish")

    response = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=JPEG_BYTES,  # > 64 bytes
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 400
    assert "Image must be" in response.json()["detail"]
    assert os.listdir(image_storage) == []


@pytest.mark.asyncio
async def test_j_unauthorized_upload_rejected(
    admin_client: AsyncClient,
    student_client: AsyncClient,
    staff_client: AsyncClient,
    db,
    image_storage,
):
    """J. Students and unassigned staff cannot upload images."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="RBAC Dish")

    for client in (student_client, staff_client):
        response = await client.post(
            f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
            content=PNG_1PX,
            headers={"Content-Type": "image/png"},
        )
        assert response.status_code == 403
    assert os.listdir(image_storage) == []


@pytest.mark.asyncio
async def test_j2_assigned_manager_can_upload_and_cross_cafeteria_forbidden(
    admin_client: AsyncClient, manager_client: AsyncClient, db, image_storage
):
    """Manager with assignment may upload; a foreign cafeteria path is refused."""
    caf = await create_test_cafeteria(db, name="Mgr Image Cafeteria")
    mgr = await _get_manager_user(db)
    await assign_user_to_cafeteria(db, mgr.id, caf.id)
    item = await create_test_menu_item(db, cafeteria_id=caf.id, name="Mgr Dish")

    ok = await manager_client.post(
        f"/api/v1/cafeterias/{caf.id}/menu-items/{item.id}/image",
        content=PNG_1PX,
        headers={"Content-Type": "image/png"},
    )
    assert ok.status_code == 200
    assert ok.json()["image_url"].startswith("/api/v1/static/food/")

    other_caf = await create_test_cafeteria(db, name="Foreign Cafeteria")
    cross = await manager_client.post(
        f"/api/v1/cafeterias/{other_caf.id}/menu-items/{item.id}/image",
        content=JPEG_BYTES,
        headers={"Content-Type": "image/jpeg"},
    )
    assert cross.status_code in (403, 404)


@pytest.mark.asyncio
async def test_l_image_replacement(admin_client: AsyncClient, db, image_storage):
    """L. Replacing an image swaps the reference; old file cleaned when orphaned."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Replace Dish")

    first = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=JPEG_BYTES,
        headers={"Content-Type": "image/jpeg"},
    )
    first_url = first.json()["image_url"]
    assert first_url.endswith(".jpg")

    second = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=PNG_1PX,
        headers={"Content-Type": "image/png"},
    )
    second_url = second.json()["image_url"]
    assert second_url != first_url
    assert second_url.endswith(".png")

    files = os.listdir(image_storage)
    # Old file was orphaned by this replacement → removed; new file present.
    assert len(files) == 1
    assert second_url.endswith(files[0])


@pytest.mark.asyncio
async def test_o_shared_image_reference_not_deleted(
    admin_client: AsyncClient, db, image_storage
):
    """O. A file referenced by another menu item survives replacement/removal."""
    caf_id, item_a = await _create_item_via_api(admin_client, db, name="Shared A")
    # Item B lives in the SAME cafeteria — the backend correctly refuses
    # cross-cafeteria image operations otherwise (verify_resource_cafeteria).
    item_b_resp = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/",
        json={"name": "Shared B", "category": "main_course", "price": 18000},
    )
    assert item_b_resp.status_code == 201
    item_b = item_b_resp.json()["id"]

    # Both items point at the same stored file (simulates seeded shared refs).
    shared_name = "shared-photo.jpg"
    with open(os.path.join(image_storage, shared_name), "wb") as f:
        f.write(JPEG_BYTES)
    shared_url = f"/api/v1/static/food/{shared_name}"
    for item_id in (item_a, item_b):
        row = await db.execute(select(MenuItem).where(MenuItem.id == item_id))
        row.scalar_one().image_url = shared_url
    await db.flush()

    # Replace A's image → shared file must survive (B still references it)
    replaced = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_a}/image",
        content=PNG_1PX,
        headers={"Content-Type": "image/png"},
    )
    assert replaced.status_code == 200
    assert os.path.isfile(os.path.join(image_storage, shared_name))

    # Remove B's image → now unreferenced → file cleaned up safely
    removed = await admin_client.delete(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_b}/image"
    )
    assert removed.status_code == 200
    assert removed.json()["image_url"] is None
    assert not os.path.isfile(os.path.join(image_storage, shared_name))


@pytest.mark.asyncio
async def test_m_n_remove_image_keeps_item_usable(
    admin_client: AsyncClient, db, image_storage
):
    """M + N. Removal clears the reference; the item keeps all its data."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Remove Dish")

    uploaded = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=JPEG_BYTES,
        headers={"Content-Type": "image/jpeg"},
    )
    assert uploaded.status_code == 200

    removed = await admin_client.delete(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image"
    )
    assert removed.status_code == 200
    data = removed.json()
    assert data["image_url"] is None
    # Item data intact
    assert data["name"] == "Remove Dish"
    assert data["price"] == 25000
    assert data["category"] == "main_course"
    assert data["is_available"] is True
    assert data["is_active"] is True
    # Orphaned file cleaned up
    assert os.listdir(image_storage) == []

    # Idempotent: removing again is a no-op success
    again = await admin_client.delete(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image"
    )
    assert again.status_code == 200
    assert again.json()["image_url"] is None


@pytest.mark.asyncio
async def test_p_seeded_style_urls_are_not_written_by_upload(
    admin_client: AsyncClient, db, image_storage
):
    """P. Uploads never persist host-specific origins (localhost/api.localhost)."""
    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Purity Dish")
    response = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=JPEG_BYTES,
        headers={"Content-Type": "image/jpeg"},
    )
    url = response.json()["image_url"]
    for bad in ("localhost", "127.0.0.1", "api.localhost", "http://", "https://"):
        assert bad not in url


@pytest.mark.asyncio
async def test_seeded_cafeterias_untouched_by_image_flow(
    admin_client: AsyncClient, db, image_storage
):
    """Pre-existing cafeterias/menu items remain intact after 48A/48B actions."""
    # Data that existed BEFORE the image flow (test-DB analogue of seed data).
    preexisting_caf = await create_test_cafeteria(db, name="Long Standing Cafeteria")
    preexisting_item = await create_test_menu_item(
        db, cafeteria_id=preexisting_caf.id, name="Classic Dish", price=15000
    )
    before = await admin_client.get(f"/api/v1/cafeterias/{preexisting_caf.id}")
    assert before.status_code == 200
    assert before.json()["name"] == "Long Standing Cafeteria"

    caf_id, item_id = await _create_item_via_api(admin_client, db, name="Flow Dish")
    uploaded = await admin_client.post(
        f"/api/v1/cafeterias/{caf_id}/menu-items/{item_id}/image",
        content=PNG_1PX,
        headers={"Content-Type": "image/png"},
    )
    assert uploaded.status_code == 200

    listing2 = await admin_client.get("/api/v1/cafeterias/")
    names2 = {c["name"] for c in listing2.json()["cafeterias"]}
    assert "Long Standing Cafeteria" in names2
    intact = await db.execute(
        select(MenuItem).where(MenuItem.id == preexisting_item.id)
    )
    row = intact.scalar_one()
    assert row.name == "Classic Dish"
    assert row.price == 15000
    assert row.image_url is None
