"""Phase 7 Live Verification — Reporting & Analytics APIs.

Runs against the live API server at http://127.0.0.1:8001 with real PostgreSQL.
Tests 10 representative cases covering authorization, data correctness, and edge cases.

NOTE: Newly registered users require email OTP verification before login.
      This script auto-verifies users via direct DB update (dev environment only).
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

passed = 0
failed = 0


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
    return result.returncode == 0


def set_user_role_db(user_id, role):
    """Set a user's role directly in DB (dev environment only)."""
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET role = '{role}' WHERE id = '{user_id}';\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


def register_and_verify(first_name, last_name, uni_id, email, password, category=None, role=None):
    """Register a user and auto-verify + optionally change role via DB."""
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
        print("    No user_id in response")
        return None
    verify_user_via_db(user_id)
    if role and role not in ("student", "faculty"):
        set_user_role_db(user_id, role)
    return user_id


def login(email, password):
    r = httpx.post(f"{BASE_URL}/auth/login", json={
        "university_email": email,
        "password": password,
    }, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code == 200:
        return r.json()["tokens"]["access_token"]
    print(f"    Login failed: {r.status_code} {r.text[:200]}")
    return None


def auth_header(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  {detail}")


def create_cafeteria(token, name, loc=None):
    """Create a cafeteria and return its id."""
    body = {
        "name": name,
        "type": "student",
        "location": loc or f"Building {unique_id()}",
        "operating_hours": "Mon-Sun 08:00-20:00",
    }
    r = httpx.post(f"{BASE_URL}/cafeterias", json=body,
                   headers=auth_header(token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        return r.json().get("id")
    print(f"    create_cafeteria failed: {r.status_code} {r.text[:200]}")
    return None


def create_menu_item(token, cafeteria_id, name, price):
    body = {
        "name": name,
        "description": f"Test item {name}",
        "price": price,
        "category": "main_course",
        "is_available": True,
    }
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/menu-items", json=body,
                   headers=auth_header(token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        return r.json().get("id")
    print(f"    create_menu_item failed: {r.status_code} {r.text[:200]}")
    return None


# ── Setup ────────────────────────────────────────────────────────────

def setup():
    """Create test users and cafeteria."""
    print("\n🔧 Setting up test users and cafeteria...")

    uid = unique_id()

    # Admin — register as faculty, then change role via DB
    register_and_verify("Admin", "User", f"ADM-{uid}", f"fa22-adm{uid[:4]}@lgu.edu.pk", "Admin123!",
                         role="university_admin")
    admin_token = login(f"fa22-adm{uid[:4]}@lgu.edu.pk", "Admin123!")

    # Manager — register as student, then change role
    uid2 = unique_id()
    register_and_verify("Manager", "User", f"MGR-{uid2}", f"fa22-mgr{uid2[:4]}@lgu.edu.pk", "Manager123!",
                         role="cafeteria_manager")
    mgr_token = login(f"fa22-mgr{uid2[:4]}@lgu.edu.pk", "Manager123!")

    # Staff — register as student, then change role
    uid3 = unique_id()
    register_and_verify("Staff", "User", f"STF-{uid3}", f"fa22-stf{uid3[:4]}@lgu.edu.pk", "Staff123!",
                         role="cafeteria_staff")
    stf_token = login(f"fa22-stf{uid3[:4]}@lgu.edu.pk", "Staff123!")

    # Student — stays as student
    uid4 = unique_id()
    register_and_verify("Student", "User", f"STU-{uid4}", f"fa22-stu{uid4[:4]}@lgu.edu.pk", "Student123!")
    stu_token = login(f"fa22-stu{uid4[:4]}@lgu.edu.pk", "Student123!")

    if not all([admin_token, mgr_token, stf_token, stu_token]):
        print("  ⚠️  Some users failed to set up — continuing with what we have")

    # Create cafeteria
    caf_id = create_cafeteria(admin_token, f"TestCafe-{unique_id()}")

    # Assign manager & staff to cafeteria via DB
    if caf_id:
        for token, role in [(mgr_token, "cafeteria_manager"), (stf_token, "cafeteria_staff")]:
            r = httpx.get(f"{BASE_URL}/auth/me", headers=auth_header(token), timeout=30)
            if r.status_code == 200:
                uid_val = r.json().get("id")
                cmd = (
                    f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
                    f"\"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
                    f"VALUES (gen_random_uuid()::text, '{uid_val}', '{caf_id}', '{role}', NOW()) "
                    f"ON CONFLICT DO NOTHING;\""
                )
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

    return admin_token, mgr_token, stf_token, stu_token, caf_id


# ── Live Test Cases ──────────────────────────────────────────────────

def run_tests(admin_token, mgr_token, stf_token, stu_token, caf_id):
    print("\n🧪 Running live verification tests...\n")

    # ── Test 1: Admin access to sales report ──
    print("Test 1: Admin access to sales report")
    r = httpx.get(f"{BASE_URL}/reports/sales",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Admin gets 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        data = r.json()
        check("Response has 'summary' key", "summary" in data, f"keys: {list(data.keys())}")
        check("Summary has 'total_revenue'", "total_revenue" in data.get("summary", {}))

    # ── Test 2: Manager access own cafeteria ──
    print("\nTest 2: Manager access own cafeteria performance")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/performance",
                  headers=auth_header(mgr_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Manager gets 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    # ── Test 3: Manager cross-cafeteria denied ──
    print("\nTest 3: Manager cross-cafeteria IDOR denied")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/nonexistent-caf-id/performance",
                  headers=auth_header(mgr_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Manager gets 403/404 for other cafeteria", r.status_code in (403, 404),
          f"got {r.status_code}")

    # ── Test 4: Student denied from reports ──
    print("\nTest 4: Student denied from reports")
    r = httpx.get(f"{BASE_URL}/reports/sales",
                  headers=auth_header(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Student gets 403", r.status_code == 403, f"got {r.status_code}")

    # ── Test 5: Unauthenticated denied ──
    print("\nTest 5: Unauthenticated access denied")
    r = httpx.get(f"{BASE_URL}/reports/sales", timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Unauthenticated gets 401/403/422", r.status_code in (401, 403, 422), f"got {r.status_code}")

    # ── Test 6: Order summary ──
    print("\nTest 6: Order summary endpoint")
    r = httpx.get(f"{BASE_URL}/reports/orders/summary",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Order summary 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has total_orders", "total_orders" in data)
        check("Has status_breakdown", "status_breakdown" in data)
        check("Has type_breakdown", "type_breakdown" in data)
        check("Has payment_breakdown", "payment_breakdown" in data)
        check("Has cancellation_rate", "cancellation_rate" in data)

    # ── Test 7: Sales by cafeteria (admin only) ──
    print("\nTest 7: Sales by cafeteria (admin only)")
    r = httpx.get(f"{BASE_URL}/reports/sales/by-cafeteria",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Admin gets 200 for by-cafeteria", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Response has 'rows' key", "rows" in data)

    # ── Test 8: Staff access own cafeteria ──
    print("\nTest 8: Staff access own cafeteria popular items")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/popular-items",
                  headers=auth_header(stf_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Staff gets 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    # ── Test 9: Empty date range returns zeros ──
    print("\nTest 9: Empty date range returns zeroed data")
    r = httpx.get(f"{BASE_URL}/reports/sales?start_date=2020-01-01&end_date=2020-01-01",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Past date range 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Zero revenue for empty range", data["summary"]["total_revenue"] == 0)

    # ── Test 10: Inventory stock levels ──
    print("\nTest 10: Inventory stock levels")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/inventory/stock-levels",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Stock levels 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Response has 'items' list", isinstance(data.get("items"), list))

    # ── Bonus: Sales daily ──
    print("\nBonus: Sales daily endpoint")
    r = httpx.get(f"{BASE_URL}/reports/sales/daily",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Sales daily 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Response has 'rows' key", "rows" in data)

    # ── Bonus: Order volume ──
    print("\nBonus: Order volume endpoint")
    r = httpx.get(f"{BASE_URL}/reports/orders/volume",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Order volume 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("Has daily and hourly keys", "daily" in data and "hourly" in data)

    # ── Bonus: Cancellation rate ──
    print("\nBonus: Cancellation rate endpoint")
    r = httpx.get(f"{BASE_URL}/reports/orders/cancellation-rate",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Cancellation rate 200", r.status_code == 200, f"got {r.status_code}")

    # ── Bonus: Cafeteria peak hours ──
    print("\nBonus: Cafeteria peak hours")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/peak-hours",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Peak hours 200", r.status_code == 200, f"got {r.status_code}")

    # ── Bonus: Inventory low stock ──
    print("\nBonus: Inventory low stock")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/inventory/low-stock",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Low stock 200", r.status_code == 200, f"got {r.status_code}")

    # ── Bonus: Inventory turnover ──
    print("\nBonus: Inventory turnover")
    r = httpx.get(f"{BASE_URL}/reports/cafeteria/{caf_id}/inventory/turnover",
                  headers=auth_header(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    check("Turnover 200", r.status_code == 200, f"got {r.status_code}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    global passed, failed

    print("=" * 60)
    print("Phase 7 Live Verification — Reporting & Analytics APIs")
    print("=" * 60)

    # Check server is running
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code != 200:
            print(f"❌ API server health check failed: {r.status_code}")
            sys.exit(1)
        print("✅ API server is running and healthy")
    except Exception as e:
        print(f"❌ Cannot reach API server: {e}")
        sys.exit(1)

    # Setup
    admin_token, mgr_token, stf_token, stu_token, caf_id = setup()
    if not caf_id:
        print("❌ Could not create test cafeteria — aborting")
        sys.exit(1)
    print(f"  ✅ Test cafeteria created: {caf_id}")

    # Run tests
    run_tests(admin_token, mgr_token, stf_token, stu_token, caf_id)

    # Summary
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("🎉 ALL LIVE VERIFICATION TESTS PASSED")
    else:
        print(f"⚠️  {failed} test(s) failed")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
