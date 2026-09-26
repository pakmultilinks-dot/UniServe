"""Phase 7 Live Verification — University Administration APIs.

Runs against the live API server at http://127.0.0.1:8001 with real PostgreSQL.
Tests 14 representative cases covering authorization, structure, and data correctness.

NOTE: Newly registered users require email OTP verification before login.
      This script auto-verifies users via direct DB update (dev environment only).
"""

import httpx
import subprocess
import sys
import uuid
import time

BASE_URL = "http://127.0.0.1:8001/api/v1"
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
    r = httpx.post(f"{BASE_URL}/auth/register", json=body, timeout=30)
    if r.status_code == 201:
        resp = r.json()
        user_id = resp.get("user_id")
        if user_id:
            verify_user_via_db(user_id)
        if role and role not in ("student", "faculty"):
            set_user_role_db(user_id, role)
        return user_id
    elif r.status_code == 409:
        # Already exists — find user_id from DB
        cmd = (
            f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -A -c "
            f"\"SELECT id FROM users WHERE university_email = '{email}' LIMIT 1;\""
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        user_id = result.stdout.strip()
        if user_id:
            verify_user_via_db(user_id)
            if role and role not in ("student", "faculty"):
                set_user_role_db(user_id, role)
        return user_id
    else:
        print(f"    Registration failed: {r.status_code} {r.text[:100]}")
        return None


def login(email, password):
    r = httpx.post(f"{BASE_URL}/auth/login", json={
        "university_email": email,
        "password": password,
    }, timeout=30)
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
        print(f"  \u2705 {name}")
    else:
        failed += 1
        msg = f"  \u274c {name}"
        if detail:
            msg += f"  \u2014 {detail}"
        print(msg)


# ── Main Tests ───────────────────────────────────────────────────────

def run_tests():
    global passed, failed

    print("=" * 70)
    print("LIVE VERIFICATION: Phase 7 University Administration APIs")
    print("=" * 70)

    # ── Setup ────────────────────────────────────────────────────────
    print("\n--- Setup ---")
    print("  Setting up users...")

    # Admin
    admin_email = f"admin_{unique_id()}@lgu.edu.pk"
    admin_id = register_and_verify(
        "Admin", "User", f"ADM-{unique_id()}", admin_email, "AdminPass1!",
        category="faculty", role="university_admin",
    )
    admin_token = login(admin_email, "AdminPass1!")
    check("Admin login", admin_token is not None)
    if not admin_token:
        print("FATAL: Cannot get admin token. Aborting.")
        return

    ah = auth_header(admin_token)

    # Manager (non-admin — should be denied)
    mgr_email = f"mgr_{unique_id()}@lgu.edu.pk"
    register_and_verify(
        "Manager", "User", f"MGR-{unique_id()}", mgr_email, "ManagerPass1!",
        category="faculty", role="cafeteria_manager",
    )
    mgr_token = login(mgr_email, "ManagerPass1!")

    # Student (should be denied)
    stu_email = f"stu_{unique_id()}@lgu.edu.pk"
    register_and_verify(
        "Student", "User", f"STU-{unique_id()}", stu_email, "StudentPass1!",
        category="student",
    )
    stu_token = login(stu_email, "StudentPass1!")

    # Faculty (should be denied)
    fac_email = f"fac_{unique_id()}@lgu.edu.pk"
    register_and_verify(
        "Faculty", "User", f"FAC-{unique_id()}", fac_email, "FacultyPass1!",
        category="faculty",
    )
    fac_token = login(fac_email, "FacultyPass1!")

    # ── 1. Admin access to overview ──────────────────────────────────
    print("\n--- Test 1: Admin access to overview ---")
    r = httpx.get(f"{BASE_URL}/administration/overview", headers=ah, timeout=10)
    check("Admin gets 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    data = r.json() if r.status_code == 200 else {}

    if "detail" in data:
        print(f"  API error: {data['detail']}")
        print("  Aborting remaining data tests.")
        return

    # ── 2. Response structure (all 5 sections) ───────────────────────
    print("\n--- Test 2: Response structure ---")
    check("Has 'users' key", "users" in data)
    check("Has 'cafeterias' key", "cafeterias" in data)
    check("Has 'orders' key", "orders" in data)
    check("Has 'financial' key", "financial" in data)
    check("Has 'exceptions' key", "exceptions" in data)

    # ── 3. Date filtering ────────────────────────────────────────────
    print("\n--- Test 3: Date filtering ---")
    from datetime import date, timedelta
    today = date.today()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()
    r = httpx.get(
        f"{BASE_URL}/administration/overview?start_date={start}&end_date={end}",
        headers=ah, timeout=10,
    )
    check("Date-filtered request 200", r.status_code == 200, f"got {r.status_code}")

    # ── 4. Both cafeterias (seeded via DB init) ──────────────────────
    print("\n--- Test 4: Cafeteria summary ---")
    cafeterias = data.get("cafeterias", {})
    check("Cafeterias has 'total'", "total" in cafeterias)
    check("Cafeterias has 'cafeterias' list", isinstance(cafeterias.get("cafeterias"), list))
    check("Cafeteria count >= 2", cafeterias.get("total", 0) >= 2, f"got {cafeterias.get('total')}")

    if cafeterias.get("cafeterias"):
        caf = cafeterias["cafeterias"][0]
        check("Cafeteria has 'cafeteria_id'", "cafeteria_id" in caf)
        check("Cafeteria has 'name'", "name" in caf)
        check("Cafeteria has 'operational_status'", "operational_status" in caf)
        check("Cafeteria has 'preparation_capacity'", "preparation_capacity" in caf)

    # ── 5. User counts ───────────────────────────────────────────────
    print("\n--- Test 5: User counts ---")
    users = data.get("users", {})
    check("Users has 'total'", "total" in users)
    check("Users has 'students'", "students" in users)
    check("Users has 'faculty'", "faculty" in users)
    check("Users has 'university_admins'", "university_admins" in users)
    check("Users has 'cafeteria_managers'", "cafeteria_managers" in users)
    check("Users has 'cafeteria_staff'", "cafeteria_staff" in users)
    check("Users has 'active'", "active" in users)
    check("Users has 'suspended'", "suspended" in users)
    check("Users has 'ordering_suspended'", "ordering_suspended" in users)
    check("Total users > 0", users.get("total", 0) > 0, f"got {users.get('total')}")

    # ── 6. Order counts ──────────────────────────────────────────────
    print("\n--- Test 6: Order counts ---")
    orders = data.get("orders", {})
    check("Orders has 'total_orders'", "total_orders" in orders)
    check("Orders has 'pending'", "pending" in orders)
    check("Orders has 'completed'", "completed" in orders)
    check("Orders has 'cancelled'", "cancelled" in orders)
    check("Orders has 'uncollected'", "uncollected" in orders)
    check("Orders has 'cancellation_rate'", "cancellation_rate" in orders)
    check("cancellation_rate is float or 0", isinstance(orders.get("cancellation_rate"), (int, float)))
    check("total_orders >= 0", orders.get("total_orders", -1) >= 0)

    # ── 7. Financial totals ──────────────────────────────────────────
    print("\n--- Test 7: Financial totals ---")
    fin = data.get("financial", {})
    check("Financial has 'total_revenue'", "total_revenue" in fin)
    check("Financial has 'total_refunded'", "total_refunded" in fin)
    check("Financial has 'net_revenue'", "net_revenue" in fin)
    check("Financial has 'online_payment_volume'", "online_payment_volume" in fin)
    check("Financial has 'cash_payment_volume'", "cash_payment_volume" in fin)
    check("Financial has 'currency'", "currency" in fin)
    check("Currency is PKR", fin.get("currency") == "PKR", f"got {fin.get('currency')}")
    check("total_revenue >= 0", fin.get("total_revenue", -1) >= 0)
    check("net_revenue = revenue - refunded",
          fin.get("net_revenue") == fin.get("total_revenue", 0) - fin.get("total_refunded", 0))

    # ── 8. Refund totals (part of financial) ─────────────────────────
    print("\n--- Test 8: Refund totals ---")
    check("total_refunded >= 0", fin.get("total_refunded", -1) >= 0)
    check("net_revenue <= total_revenue",
          fin.get("net_revenue", 0) <= fin.get("total_revenue", 0))

    # ── 9. Exception counts ──────────────────────────────────────────
    print("\n--- Test 9: Exception counts ---")
    exc = data.get("exceptions", {})
    check("Exceptions has 'overdue_refunds'", "overdue_refunds" in exc)
    check("Exceptions has 'ordering_suspended_users'", "ordering_suspended_users" in exc)
    check("Exceptions has 'uncollected_orders'", "uncollected_orders" in exc)
    check("Exceptions has 'cafeteria_closure_cancellations'", "cafeteria_closure_cancellations" in exc)
    check("overdue_refunds >= 0", exc.get("overdue_refunds", -1) >= 0)
    check("ordering_suspended_users >= 0", exc.get("ordering_suspended_users", -1) >= 0)

    # ── 10. Manager denied ───────────────────────────────────────────
    print("\n--- Test 10: Manager denied ---")
    if mgr_token:
        r = httpx.get(f"{BASE_URL}/administration/overview", headers=auth_header(mgr_token), timeout=10)
        check("Manager gets 403", r.status_code == 403, f"got {r.status_code}")
    else:
        check("Manager denied (login failed)", False, "no token")

    # ── 11. Staff denied ─────────────────────────────────────────────
    print("\n--- Test 11: Staff denied ---")
    # Create staff user
    staff_email = f"staff_{unique_id()}@lgu.edu.pk"
    register_and_verify(
        "Staff", "User", f"STAFF-{unique_id()}", staff_email, "StaffPass1!",
        category="faculty", role="cafeteria_staff",
    )
    staff_token = login(staff_email, "StaffPass1!")
    if staff_token:
        r = httpx.get(f"{BASE_URL}/administration/overview", headers=auth_header(staff_token), timeout=10)
        check("Staff gets 403", r.status_code == 403, f"got {r.status_code}")
    else:
        check("Staff denied (login failed)", False, "no token")

    # ── 12. Student denied ───────────────────────────────────────────
    print("\n--- Test 12: Student denied ---")
    if stu_token:
        r = httpx.get(f"{BASE_URL}/administration/overview", headers=auth_header(stu_token), timeout=10)
        check("Student gets 403", r.status_code == 403, f"got {r.status_code}")
    else:
        check("Student denied (login failed)", False, "no token")

    # ── 13. Faculty denied ───────────────────────────────────────────
    print("\n--- Test 13: Faculty denied ---")
    if fac_token:
        r = httpx.get(f"{BASE_URL}/administration/overview", headers=auth_header(fac_token), timeout=10)
        check("Faculty gets 403", r.status_code == 403, f"got {r.status_code}")
    else:
        check("Faculty denied (login failed)", False, "no token")

    # ── 14. No sensitive fields in response ──────────────────────────
    print("\n--- Test 14: No sensitive fields ---")
    raw = __import__("json").dumps(data)
    for term in ["password", "password_hash", "pin_hash", "refresh_token", "otp", "biometric"]:
        check(f"No '{term}' in response", term.lower() not in raw.lower())

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"LIVE VERIFICATION RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)


if __name__ == "__main__":
    time.sleep(2)
    run_tests()
    sys.exit(1 if failed else 0)
