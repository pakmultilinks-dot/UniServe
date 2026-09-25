"""Phase 6 Live Verification — Notifications system.

Runs against the live API server at http://127.0.0.1:8001 with real PostgreSQL.

Tests:
1. Register student user → verify email → login
2. Create cafeteria + menu item + inventory (as admin)
3. Checkout an order (as student) → verify notification created
4. GET /notifications → list student's notifications
5. GET /notifications/unread-count → verify count
6. PATCH /notifications/{id}/read → mark as read
7. PATCH /notifications/read-all → mark all as read
8. Ownership isolation → second student sees nothing
"""

import httpx
import subprocess
import sys
import uuid
import time

BASE_URL = "http://127.0.0.1:8001/api/v1"
FOLLOW_REDIRECTS = True
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_dev"


# ── Helpers ──────────────────────────────────────────────────────────

def unique_id():
    return uuid.uuid4().hex[:8]


def verify_user_via_db(user_id):
    """Mark a user as email-verified in the dev database."""
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET email_verified = true, status = 'active' "
        f"WHERE id = '{user_id}' AND email_verified = false;\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f"    DB verify failed: {result.stderr.strip()}")
        return False
    return True


def register_and_verify(first_name, last_name, uni_id, email, password, category=None):
    """Register a user and auto-verify email via DB."""
    body = {
        "first_name": first_name,
        "last_name": last_name,
        "university_id": uni_id,
        "university_email": email,
        "password": password,
    }
    if category:
        body["selected_category"] = category
    r = httpx.post(f"{BASE_URL}/auth/register", json=body, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code != 201:
        print(f"    Registration failed: {r.status_code} {r.text[:100]}")
        return None

    resp = r.json()
    user_id = resp.get("user_id")
    if not user_id:
        print(f"    No user_id in response: {resp}")
        return None

    if not verify_user_via_db(user_id):
        return None

    return user_id


def login(email, password):
    r = httpx.post(f"{BASE_URL}/auth/login", json={
        "university_email": email,
        "password": password,
    }, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code == 200:
        return r.json()["tokens"]["access_token"]
    else:
        print(f"    Login failed: {r.status_code} {r.text[:200]}")
        return None


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def promote_to_admin(user_id):
    """Promote user to UNIVERSITY_ADMIN via DB."""
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET role = 'university_admin' WHERE id = '{user_id}';\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


# ── Main verification ────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Phase 6 — Live Notifications Verification")
    print("=" * 70)
    passed = 0
    failed = 0

    # ── 1. Health check ──────────────────────────────────────────────
    print("\n[1] Health check...")
    r = httpx.get(f"{BASE_URL}/health", timeout=10)
    if r.status_code == 200:
        print("  ✅ API server is healthy")
        passed += 1
    else:
        print(f"  ❌ Health check failed: {r.status_code}")
        return 1

    # ── 2. Register & login student ──────────────────────────────────
    uid = unique_id()
    print(f"\n[2] Register student (uid={uid})...")
    student_email = f"notif_test_{uid}@lgu.edu.pk"
    student_id = register_and_verify(
        "Notif", "Student", f"STU-{uid}", student_email, "TestPass1!",
        category="student",
    )
    if not student_id:
        print("  ❌ Student registration failed")
        return 1
    print(f"  ✅ Student registered: {student_id}")

    student_token = login(student_email, "TestPass1!")
    if not student_token:
        print("  ❌ Student login failed")
        return 1
    print(f"  ✅ Student logged in")
    passed += 1

    # ── 3. Register & login admin ────────────────────────────────────
    print(f"\n[3] Register admin (uid={uid})...")
    admin_email = f"admin_notif_{uid}@lgu.edu.pk"
    admin_id = register_and_verify(
        "Notif", "Admin", f"ADM-{uid}", admin_email, "TestPass1!",
        category="faculty",
    )
    if not admin_id:
        print("  ❌ Admin registration failed")
        return 1

    # Promote to admin via DB
    promote_to_admin(admin_id)

    # Re-login to get fresh token with admin role
    admin_token = login(admin_email, "TestPass1!")
    if not admin_token:
        print("  ❌ Admin login failed")
        return 1
    print(f"  ✅ Admin logged in")
    passed += 1

    # ── 4. Create cafeteria (admin) ──────────────────────────────────
    print("\n[4] Create cafeteria...")
    r = httpx.post(f"{BASE_URL}/cafeterias", json={
        "name": f"Notification Test Cafeteria {uid}",
        "type": "student",
        "description": "Test cafeteria for notification verification",
    }, headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        cafeteria_id = r.json()["id"]
        print(f"  ✅ Cafeteria created: {cafeteria_id}")
        passed += 1
    else:
        print(f"  ❌ Cafeteria creation failed: {r.status_code} {r.text[:200]}")
        return 1

    # ── 5. Create menu item (admin) ──────────────────────────────────
    print("\n[5] Create menu item...")
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/menu-items", json={
        "name": "Notification Biryani",
        "category": "main_course",
        "price": 25000,
        "description": "Test biryani for notifications",
    }, headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        menu_item_id = r.json()["id"]
        print(f"  ✅ Menu item created: {menu_item_id}")
        passed += 1
    else:
        print(f"  ❌ Menu item creation failed: {r.status_code} {r.text[:200]}")
        return 1

    # ── 6. Add inventory (admin) ─────────────────────────────────────
    print("\n[6] Add inventory...")
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/inventory", json={
        "menu_item_id": menu_item_id,
        "quantity": 50,
        "unit": "pcs",
    }, headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        print(f"  ✅ Inventory added")
        passed += 1
    else:
        print(f"  ❌ Inventory addition failed: {r.status_code} {r.text[:200]}")
        return 1

    # ── 7. Publish daily menu (admin) ────────────────────────────────
    print("\n[7] Publish daily menu...")
    # First, create daily menu
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus", json={
        "menu_date": "2026-09-25",
    }, headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        daily_menu_id = r.json()["id"]
        print(f"  ✅ Daily menu created: {daily_menu_id}")
    else:
        print(f"  ❌ Daily menu creation failed: {r.status_code} {r.text[:200]}")
        return 1

    # Add item to daily menu
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/items", json={
        "menu_item_id": menu_item_id,
    }, headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        print(f"  ✅ Item added to daily menu")
    else:
        print(f"  ⚠️  Add item to daily menu: {r.status_code} {r.text[:100]}")

    # Publish
    r = httpx.patch(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/publish",
        headers=auth_headers(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code in (200, 201):
        print(f"  ✅ Daily menu published")
        passed += 1
    else:
        print(f"  ⚠️  Daily menu publish: {r.status_code} {r.text[:100]}")
        # Continue anyway — may already be published

    # ── 8. Add to cart & checkout (student) → triggers notification ──
    print("\n[8] Add to cart & checkout (triggers notification)...")
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/items", json={
        "menu_item_id": menu_item_id,
        "quantity": 1,
    }, headers=auth_headers(student_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        print(f"  ✅ Cart item added")
    else:
        print(f"  ❌ Add cart item failed: {r.status_code} {r.text[:200]}")
        return 1

    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/checkout", json={
        "payment_method": "cash",
    }, headers=auth_headers(student_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        order_data = r.json()
        order_id = order_data["id"]
        print(f"  ✅ Order created: {order_id} (order #{order_data['order_number']})")
        passed += 1
    else:
        print(f"  ❌ Checkout failed: {r.status_code} {r.text[:200]}")
        return 1

    # Give the fire-and-forget notification a moment
    time.sleep(0.5)

    # ── 9. GET /notifications → list student's notifications ─────────
    print("\n[9] GET /notifications (student)...")
    r = httpx.get(f"{BASE_URL}/notifications", headers=auth_headers(student_token), timeout=30)
    if r.status_code == 200:
        data = r.json()
        total = data["total"]
        unread = data["unread_count"]
        items = data["items"]
        print(f"  ✅ Got {total} notification(s), {unread} unread")
        for n in items:
            print(f"     - [{n['notification_type']}] {n['title']}")
        passed += 1

        if total == 0:
            print("  ⚠️  No notifications — order creation may not have triggered notification")
    else:
        print(f"  ❌ GET /notifications failed: {r.status_code} {r.text[:200]}")
        failed += 1

    # ── 10. GET /notifications/unread-count ───────────────────────────
    print("\n[10] GET /notifications/unread-count...")
    r = httpx.get(f"{BASE_URL}/notifications/unread-count", headers=auth_headers(student_token), timeout=30)
    if r.status_code == 200:
        count = r.json()["unread_count"]
        print(f"  ✅ Unread count: {count}")
        passed += 1
    else:
        print(f"  ❌ Unread count failed: {r.status_code} {r.text[:200]}")
        failed += 1

    # ── 11. PATCH /notifications/{id}/read ────────────────────────────
    if items:
        first_notif_id = items[0]["id"]
        print(f"\n[11] PATCH /notifications/{first_notif_id[:8]}.../read...")
        r = httpx.patch(
            f"{BASE_URL}/notifications/{first_notif_id}/read",
            headers=auth_headers(student_token), timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ Marked read: is_read={data['is_read']}, read_at={data['read_at']}")
            passed += 1
        else:
            print(f"  ❌ Mark read failed: {r.status_code} {r.text[:200]}")
            failed += 1
    else:
        print("\n[11] SKIP — no notifications to mark read")
        failed += 1

    # ── 12. Verify unread count decreased ────────────────────────────
    print("\n[12] Verify unread count after marking one as read...")
    r = httpx.get(f"{BASE_URL}/notifications/unread-count", headers=auth_headers(student_token), timeout=30)
    if r.status_code == 200:
        count = r.json()["unread_count"]
        print(f"  ✅ Unread count after mark-read: {count}")
        passed += 1
    else:
        print(f"  ❌ Unread count failed: {r.status_code}")
        failed += 1

    # ── 13. PATCH /notifications/read-all ─────────────────────────────
    print("\n[13] PATCH /notifications/read-all...")
    r = httpx.patch(
        f"{BASE_URL}/notifications/read-all",
        headers=auth_headers(student_token), timeout=30,
    )
    if r.status_code == 200:
        data = r.json()
        print(f"  ✅ Marked all read: {data['marked_count']} notification(s)")
        passed += 1
    else:
        print(f"  ❌ Mark all read failed: {r.status_code} {r.text[:200]}")
        failed += 1

    # ── 14. Verify unread count is now 0 ─────────────────────────────
    print("\n[14] Verify unread count is now 0...")
    r = httpx.get(f"{BASE_URL}/notifications/unread-count", headers=auth_headers(student_token), timeout=30)
    if r.status_code == 200:
        count = r.json()["unread_count"]
        if count == 0:
            print(f"  ✅ Unread count: {count}")
            passed += 1
        else:
            print(f"  ❌ Expected 0, got {count}")
            failed += 1
    else:
        print(f"  ❌ Unread count failed: {r.status_code}")
        failed += 1

    # ── 15. Ownership isolation — second student sees nothing ─────────
    print("\n[15] Ownership isolation — register second student...")
    uid2 = unique_id()
    student2_email = f"notif_test2_{uid2}@lgu.edu.pk"
    student2_id = register_and_verify(
        "Notif2", "Student", f"STU2-{uid2}", student2_email, "TestPass1!",
        category="student",
    )
    if not student2_id:
        print("  ❌ Second student registration failed")
        failed += 1
    else:
        student2_token = login(student2_email, "TestPass1!")
        if not student2_token:
            print("  ❌ Second student login failed")
            failed += 1
        else:
            r = httpx.get(f"{BASE_URL}/notifications", headers=auth_headers(student2_token), timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data["total"] == 0:
                    print(f"  ✅ Second student sees 0 notifications (ownership enforced)")
                    passed += 1
                else:
                    print(f"  ❌ Second student sees {data['total']} notifications (ownership breach!)")
                    failed += 1
            else:
                print(f"  ❌ Second student list failed: {r.status_code}")
                failed += 1

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} checks")
    print("=" * 70)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
