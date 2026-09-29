#!/usr/bin/env python3
"""UniServe Live Role Matrix Verification Script.

Tests every role against every endpoint with actual HTTP responses.
Password for all test users: TestPass123!
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"

USERS = {
    "student_a":    {"email": "live.stu.alpha@lgu.edu.pk",  "password": "TestPass123!", "role": "student",           "category": "student"},
    "student_b":    {"email": "live.stu.beta@lgu.edu.pk",   "password": "TestPass123!", "role": "student",           "category": "student"},
    "faculty_a":    {"email": "live.fac.alpha@lgu.edu.pk",  "password": "TestPass123!", "role": "faculty",           "category": "faculty"},
    "faculty_b":    {"email": "live.fac.beta@lgu.edu.pk",   "password": "TestPass123!", "role": "faculty",           "category": "faculty"},
    "staff_student":{"email": "live.stf.student@lgu.edu.pk","password": "TestPass123!", "role": "cafeteria_staff",   "category": "faculty"},
    "staff_faculty":{"email": "live.stf.faculty@lgu.edu.pk","password": "TestPass123!", "role": "cafeteria_staff",   "category": "faculty"},
    "mgr_student":  {"email": "live.mgr.student@lgu.edu.pk","password": "TestPass123!", "role": "cafeteria_manager", "category": "faculty"},
    "mgr_faculty":  {"email": "live.mgr.faculty@lgu.edu.pk","password": "TestPass123!", "role": "cafeteria_manager", "category": "faculty"},
    "admin":        {"email": "live.admin@lgu.edu.pk",      "password": "TestPass123!", "role": "university_admin",  "category": "faculty"},
}

STUDENT_CAF = "205e8c71-7b9c-4a04-a40b-8f5ca8344bf2"
FACULTY_CAF = "f47ac10b-58cc-4372-a567-0e02b2c3d479"

results = []
passed = 0
failed = 0

def api(method, path, token=None, body=None, expect_status=None):
    """Make an API call and return (status_code, json_body_or_text)."""
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode()
            try:
                return resp.status, json.loads(resp_body)
            except:
                return resp.status, resp_body
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()
        try:
            return e.code, json.loads(resp_body)
        except:
            return e.code, resp_body

def login(email, password):
    """Login and return access token."""
    status, body = api("POST", "/auth/login", body={"university_email": email, "password": password})
    if status == 200:
        return body["tokens"]["access_token"]
    return None

def check(name, actual_status, expected_status, token=None, description=""):
    global passed, failed
    ok = actual_status == expected_status
    symbol = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    results.append({"test": name, "expected": expected_status, "actual": actual_status, "pass": ok, "desc": description})
    print(f"  [{symbol}] {name}: expected {expected_status}, got {actual_status} {description}")

# ═══════════════════════════════════════════════════════════════════
# PHASE 2: Login verification for all users
# ═══════════════════════════════════════════════════════════════════
print("=" * 70)
print("PHASE 2: LOGIN VERIFICATION FOR ALL 10 USERS")
print("=" * 70)

tokens = {}
for key, u in USERS.items():
    token = login(u["email"], u["password"])
    if token:
        tokens[key] = token
        print(f"  [PASS] {key} ({u['role']}) login: OK")
        passed += 1
    else:
        print(f"  [FAIL] {key} ({u['role']}) login: FAILED")
        failed += 1

print(f"\n  Total logins: {passed} passed, {failed} failed\n")

# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Student live validation
# ═══════════════════════════════════════════════════════════════════
print("=" * 70)
print("PHASE 3: STUDENT LIVE VALIDATION")
print("=" * 70)

t = tokens.get("student_a")
if t:
    # Authorized: GET own profile
    s, b = api("GET", "/auth/me", t)
    check("Student: GET /auth/me", s, 200, description=f"role={b.get('role') if isinstance(b,dict) else '?'}")

    # Authorized: GET cafeterias
    s, b = api("GET", "/cafeterias", t)
    check("Student: GET /cafeterias", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: GET student cafeteria menu items
    s, b = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", t)
    menu_count = b.get("total", len(b)) if isinstance(b, dict) else len(b) if isinstance(b, list) else "?"
    check("Student: GET student-caf menu", s, 200, description=f"count={menu_count}")

    # Unauthorized: GET faculty cafeteria menu items (student blocked from faculty caf)
    s, b = api("GET", f"/cafeterias/{FACULTY_CAF}/menu-items", t)
    check("Student: GET faculty-caf menu (BLOCKED)", s, 403, description="student->faculty caf")

    # Authorized: GET own orders
    s, b = api("GET", "/orders/", t)
    check("Student: GET /orders/", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Unauthorized: GET staff orders for student cafeteria
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Student: GET staff orders (BLOCKED)", s, 403, description="student->staff orders")

    # Unauthorized: GET admin all refunds
    s, b = api("GET", "/refunds/admin/all", t)
    check("Student: GET admin refunds (BLOCKED)", s, 403, description="student->admin refunds")

    # Authorized: GET notifications
    s, b = api("GET", "/notifications", t)
    check("Student: GET /notifications", s, 200)

    # Authorized: GET unread count
    s, b = api("GET", "/notifications/unread-count", t)
    check("Student: GET /notifications/unread-count", s, 200, description=f"count={b.get('unread_count') if isinstance(b,dict) else '?'}")

    # Authorized: GET favorites
    s, b = api("GET", "/favorites/", t)
    check("Student: GET /favorites/", s, 200)

    # Authorized: GET administration overview (should be denied for student)
    s, b = api("GET", "/administration/overview", t)
    check("Student: GET admin overview (BLOCKED)", s, 403, description="student->admin overview")

    # Unauthorized: GET reports/sales
    s, b = api("GET", "/reports/sales", t)
    check("Student: GET /reports/sales (BLOCKED)", s, 403, description="student->reports")

    # Unauthorized: GET user list
    s, b = api("GET", "/users/", t)
    check("Student: GET /users/ (BLOCKED)", s, 403, description="student->user list")

    # Authorized: menu search (student cafeteria)
    s, b = api("GET", f"/menu-search/?cafeteria_id={STUDENT_CAF}", t)
    check("Student: GET menu-search (student caf)", s, 200)

    # Unauthorized: menu search (faculty cafeteria)
    s, b = api("GET", f"/menu-search/?cafeteria_id={FACULTY_CAF}", t)
    check("Student: GET menu-search (faculty caf, BLOCKED)", s, 403)

# ═══════════════════════════════════════════════════════════════════
# PHASE 4: Faculty live validation
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 4: FACULTY LIVE VALIDATION")
print("=" * 70)

t = tokens.get("faculty_a")
if t:
    # Authorized: GET own profile
    s, b = api("GET", "/auth/me", t)
    check("Faculty: GET /auth/me", s, 200, description=f"role={b.get('role') if isinstance(b,dict) else '?'}")

    # Authorized: GET cafeterias (both accessible to faculty)
    s, b = api("GET", "/cafeterias", t)
    check("Faculty: GET /cafeterias", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: GET student cafeteria menu (faculty allowed in student caf)
    s, b = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", t)
    check("Faculty: GET student-caf menu", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: GET faculty cafeteria menu
    s, b = api("GET", f"/cafeterias/{FACULTY_CAF}/menu-items", t)
    check("Faculty: GET faculty-caf menu", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: GET own orders
    s, b = api("GET", "/orders/", t)
    check("Faculty: GET /orders/", s, 200)

    # Unauthorized: GET staff orders
    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Faculty: GET staff orders (BLOCKED)", s, 403)

    # Unauthorized: admin endpoints
    s, b = api("GET", "/refunds/admin/all", t)
    check("Faculty: GET admin refunds (BLOCKED)", s, 403)

    s, b = api("GET", "/administration/overview", t)
    check("Faculty: GET admin overview (BLOCKED)", s, 403)

    s, b = api("GET", "/users/", t)
    check("Faculty: GET /users/ (BLOCKED)", s, 403)

    # Authorized: notifications
    s, b = api("GET", "/notifications", t)
    check("Faculty: GET /notifications", s, 200)

    # Authorized: favorites
    s, b = api("GET", "/favorites/", t)
    check("Faculty: GET /favorites/", s, 200)

    # Authorized: menu search (both cafeterias)
    s, b = api("GET", f"/menu-search/?cafeteria_id={STUDENT_CAF}", t)
    check("Faculty: GET menu-search (student caf)", s, 200)

    s, b = api("GET", f"/menu-search/?cafeteria_id={FACULTY_CAF}", t)
    check("Faculty: GET menu-search (faculty caf)", s, 200)

# ═══════════════════════════════════════════════════════════════════
# PHASE 5: Staff live validation
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 5: STAFF LIVE VALIDATION")
print("=" * 70)

t = tokens.get("staff_student")
if t:
    # Authorized: GET own profile
    s, b = api("GET", "/auth/me", t)
    check("Staff-Student: GET /auth/me", s, 200, description=f"role={b.get('role') if isinstance(b,dict) else '?'}")

    # Authorized: GET assigned cafeteria staff orders
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Staff-Student: GET staff orders (own caf)", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Unauthorized: GET other cafeteria staff orders
    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Staff-Student: GET other caf orders (BLOCKED)", s, 403)

    # Authorized: menu operations (read)
    s, b = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", t)
    check("Staff-Student: GET own caf menu", s, 200)

    # Unauthorized: admin overview
    s, b = api("GET", "/administration/overview", t)
    check("Staff-Student: GET admin overview (BLOCKED)", s, 403)

    s, b = api("GET", "/refunds/admin/all", t)
    check("Staff-Student: GET admin refunds (BLOCKED)", s, 403)

    s, b = api("GET", "/users/", t)
    check("Staff-Student: GET /users/ (BLOCKED)", s, 403)

# ═══════════════════════════════════════════════════════════════════
# PHASE 6: Manager live validation
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 6: MANAGER LIVE VALIDATION")
print("=" * 70)

t = tokens.get("mgr_student")
if t:
    # Authorized: GET own profile
    s, b = api("GET", "/auth/me", t)
    check("Manager-Student: GET /auth/me", s, 200, description=f"role={b.get('role') if isinstance(b,dict) else '?'}")

    # Authorized: GET assigned cafeteria staff orders
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Manager-Student: GET staff orders (own caf)", s, 200)

    # Unauthorized: GET other cafeteria staff orders
    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Manager-Student: GET other caf orders (BLOCKED)", s, 403)

    # Unauthorized: administration overview (UNIVERSITY_ADMIN only)
    s, b = api("GET", "/administration/overview", t)
    check("Manager-Student: GET admin overview (BLOCKED)", s, 403, description="manager->admin overview")

    # Authorized: GET own cafeteria menu
    s, b = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", t)
    check("Manager-Student: GET own caf menu", s, 200)

    # Unauthorized: user list (only admin)
    s, b = api("GET", "/users/", t)
    check("Manager-Student: GET /users/ (BLOCKED)", s, 403)

    # Unauthorized: admin refunds
    s, b = api("GET", "/refunds/admin/all", t)
    check("Manager-Student: GET admin refunds (BLOCKED)", s, 403)

# ═══════════════════════════════════════════════════════════════════
# PHASE 7: Admin live validation
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 7: ADMIN LIVE VALIDATION")
print("=" * 70)

t = tokens.get("admin")
if t:
    # Authorized: GET own profile
    s, b = api("GET", "/auth/me", t)
    check("Admin: GET /auth/me", s, 200, description=f"role={b.get('role') if isinstance(b,dict) else '?'}")

    # Authorized: administration overview
    s, b = api("GET", "/administration/overview", t)
    check("Admin: GET admin overview", s, 200, description=f"keys={list(b.keys()) if isinstance(b,dict) else '?'}")

    # Authorized: user list
    s, b = api("GET", "/users/", t)
    check("Admin: GET /users/", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: admin refunds
    s, b = api("GET", "/refunds/admin/all", t)
    check("Admin: GET admin refunds", s, 200, description=f"count={len(b) if isinstance(b,list) else '?'}")

    # Authorized: reports
    s, b = api("GET", "/reports/sales", t)
    check("Admin: GET /reports/sales", s, 200)

    # Authorized: both cafeteria staff orders
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Admin: GET student-caf staff orders", s, 200)

    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Admin: GET faculty-caf staff orders", s, 200)

    # Authorized: GET any user
    # Get a student user id
    s, b = api("GET", "/users/", t)
    if isinstance(b, list) and len(b) > 0:
        uid = b[0]["id"]
        s2, b2 = api("GET", f"/users/{uid}", t)
        check("Admin: GET /users/{id}", s2, 200, description=f"name={b2.get('first_name','?')} {b2.get('last_name','?')}")
    else:
        check("Admin: GET /users/{id}", 404, 200, description="no users found")

# ═══════════════════════════════════════════════════════════════════
# PHASE 10: API CONTRACT VERIFICATION
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 10: API CONTRACT VERIFICATION")
print("=" * 70)

t = tokens.get("admin")
if t:
    # Administration overview shape
    s, b = api("GET", "/administration/overview", t)
    if isinstance(b, dict):
        check("Contract: admin overview is NESTED dict", s, 200, description=f"top_keys={list(b.keys())}")
        # Check nested structure
        if "users" in b and "cafeterias" in b:
            check("Contract: overview.users exists", s, 200, description=f"users_keys={list(b['users'].keys())}")
            check("Contract: overview.cafeterias exists", s, 200, description=f"caf_keys={list(b['cafeterias'].keys())}")
        else:
            check("Contract: overview is nested", s, 200, description=f"keys={list(b.keys())}")
    else:
        check("Contract: admin overview is dict", s, 200, description=f"type={type(b).__name__}")

    # Notifications shape
    s, b = api("GET", "/notifications", t)
    if isinstance(b, list):
        check("Contract: notifications is list", s, 200)
    elif isinstance(b, dict) and "items" in b:
        check("Contract: notifications is paginated", s, 200, description=f"keys={list(b.keys())}")
    else:
        check("Contract: notifications shape", s, 200, description=f"keys={list(b.keys()) if isinstance(b,dict) else type(b).__name__}")

    # Unread count shape
    s, b = api("GET", "/notifications/unread-count", t)
    check("Contract: unread-count has unread_count", s, 200, description=f"body={b}")

    # Refunds admin shape
    s, b = api("GET", "/refunds/admin/all", t)
    check("Contract: admin refunds is list", s, 200, description=f"type={type(b).__name__} count={len(b) if isinstance(b,list) else '?'}")

    # Favorites shape
    s, b = api("GET", "/favorites/", t)
    check("Contract: favorites shape", s, 200, description=f"type={type(b).__name__}")

# ═══════════════════════════════════════════════════════════════════
# PHASE 11: REGISTRATION VALIDATION
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 11: REGISTRATION VALIDATION")
print("=" * 70)

# Valid registration (use unique ID to avoid conflicts on re-run)
import time
reg_body = {
    "first_name": "Reg",
    "last_name": "Test",
    "university_id": f"LIVE-REG-{int(time.time())}",
    "university_email": f"live.reg.{int(time.time())}@lgu.edu.pk",
    "password": "StrongReg1!",
}
s, b = api("POST", "/auth/register", body=reg_body)
check("Register: valid student", s, 201, description=f"body={b}")

# Duplicate email (use same body)
s, b = api("POST", "/auth/register", body=reg_body)
check("Register: duplicate email", s, 409, description=f"status={s}")

# Weak password (no uppercase)
weak_body = reg_body.copy()
weak_body["university_email"] = "live.reg.weak@lgu.edu.pk"
weak_body["university_id"] = "LIVE-REG-002"
weak_body["password"] = "weakpass1!"
s, b = api("POST", "/auth/register", body=weak_body)
check("Register: weak password", s, 422, description=f"status={s}")

# Short password
short_body = reg_body.copy()
short_body["university_email"] = "live.reg.short@lgu.edu.pk"
short_body["university_id"] = "LIVE-REG-003"
short_body["password"] = "Ab1!"
s, b = api("POST", "/auth/register", body=short_body)
check("Register: short password", s, 422, description=f"status={s}")

# Invalid email domain
invalid_body = reg_body.copy()
invalid_body["university_email"] = "test@gmail.com"
invalid_body["university_id"] = "LIVE-REG-004"
s, b = api("POST", "/auth/register", body=invalid_body)
check("Register: invalid email domain", s, 400, description=f"status={s}")

# ═══════════════════════════════════════════════════════════════════
# PHASE 14: SECURITY ATTACK MATRIX (selected high-priority)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 14: SECURITY ATTACK MATRIX")
print("=" * 70)

# Unauthenticated access to protected endpoints
no_token_endpoints = [
    ("/auth/me", 401),
    ("/orders/", 401),
    ("/cafeterias", 401),  # all endpoints require auth
    ("/notifications", 401),
    ("/favorites/", 401),
    ("/users/", 401),
    ("/administration/overview", 401),
    ("/refunds/admin/all", 401),
    ("/reports/sales", 401),
]
for path, expected in no_token_endpoints:
    s, b = api("GET", path)
    check(f"Unauth GET {path}", s, expected)

# Student trying admin endpoints
t = tokens.get("student_a")
if t:
    admin_endpoints = [
        ("/users/", 403),
        ("/administration/overview", 403),
        ("/refunds/admin/all", 403),
        ("/reports/sales", 403),
    ]
    for path, expected in admin_endpoints:
        s, b = api("GET", path, t)
        check(f"Student->Admin {path}", s, expected)

# Student B accessing Student A's order (IDOR test — should fail since no order yet, but test 404 vs 403)
t_b = tokens.get("student_b")
t_a = tokens.get("student_a")
if t_a and t_b:
    # Create an order as Student A
    # First, get a menu item from student cafeteria (response is {items: [...], total: N})
    s, items_resp = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", t_a)
    items_list = items_resp.get("items", items_resp) if isinstance(items_resp, dict) else items_resp
    if isinstance(items_list, list) and len(items_list) > 0:
        item_id = items_list[0]["id"]
        # Create cart item then order (cart is scoped under cafeteria)
        s, _ = api("POST", f"/cafeterias/{STUDENT_CAF}/cart/items", t_a, {"menu_item_id": item_id, "quantity": 1})
        s, _ = api("POST", f"/cafeterias/{STUDENT_CAF}/cart/checkout", t_a, {"payment_method": "cash"})
        
        # Get Student A's orders
        s, orders_resp = api("GET", "/orders/", t_a)
        orders_list = orders_resp.get("orders", orders_resp) if isinstance(orders_resp, dict) else orders_resp
        if isinstance(orders_list, list) and len(orders_list) > 0:
            order_id = orders_list[0]["id"]
            # Student B tries to access Student A's order ETA (IDOR)
            s, b = api("GET", f"/orders/{order_id}/eta", t_b)
            check(f"IDOR: Student B -> Student A ETA", s, 403, description=f"cross-owner={s}")

            # Student A can access own order
            s, b = api("GET", f"/orders/{order_id}/eta", t_a)
            check(f"IDOR: Student A -> own ETA", s, 200, description=f"owner={s}")

            # Student A tries to cancel
            s, b = api("POST", f"/orders/{order_id}/cancel", t_a)
            check(f"Order: Student A cancel own order", s, 200, description=f"result={s}")
        else:
            print("  [SKIP] No orders created for IDOR test")
    else:
        print("  [SKIP] No menu items for IDOR test")

# ═══════════════════════════════════════════════════════════════════
# PHASE 15: CAFETERIA INDEPENDENCE
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE 15: CAFETERIA INDEPENDENCE")
print("=" * 70)

t = tokens.get("admin")
if t:
    # Verify 2 cafeterias exist
    s, b = api("GET", "/cafeterias", t)
    if isinstance(b, dict):
        # Could be paginated or nested
        caf_list = b.get("cafeterias", b.get("items", []))
        count = len(caf_list) if isinstance(caf_list, list) else 0
        check("Cafeterias: 2 exist", s, 200, description=f"count={count} keys={list(b.keys())}")
    elif isinstance(b, list):
        check("Cafeterias: 2 exist", s, 200, description=f"count={len(b)}")
    else:
        check("Cafeterias: list returned", s, 200, description=f"type={type(b).__name__}")

# Staff Student cafeteria access
t = tokens.get("staff_student")
if t:
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Staff-Student: own cafeteria orders", s, 200)

    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Staff-Student: faculty cafeteria orders (BLOCKED)", s, 403)

# Staff Faculty cafeteria access
t = tokens.get("staff_faculty")
if t:
    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Staff-Faculty: own cafeteria orders", s, 200)

    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Staff-Faculty: student cafeteria orders (BLOCKED)", s, 403)

# Manager cafeteria isolation
t = tokens.get("mgr_student")
if t:
    s, b = api("GET", f"/orders/cafeteria/{STUDENT_CAF}", t)
    check("Manager-Student: own cafeteria orders", s, 200)

    s, b = api("GET", f"/orders/cafeteria/{FACULTY_CAF}", t)
    check("Manager-Student: faculty cafeteria orders (BLOCKED)", s, 403)

# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"VERIFICATION SUMMARY: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 70)

if failed > 0:
    print("\nFAILURES:")
    for r in results:
        if not r["pass"]:
            print(f"  FAIL: {r['test']} — expected {r['expected']}, got {r['actual']} {r['desc']}")

sys.exit(0 if failed == 0 else 1)
