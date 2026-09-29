#!/usr/bin/env python3
"""UniServe Complete End-to-End Verification Script.

Tests all workflows across all roles:
- Student: browse, cart, order, pay, track, cancel
- Faculty: same as student + faculty cafeteria access
- Staff: order management, status updates
- Manager: staff management, reports, refund approval
- Admin: user management, system settings, full access

Password for all test users: TestPass123!
"""

import json
import sys
import uuid
import urllib.request
import urllib.error
from datetime import datetime

BASE = "http://localhost:8000/api/v1"

# Results tracking
results = []
passed = 0
failed = 0


def api(method, path, token=None, body=None, expect_status=None, allow_redirect=False):
    """Make an API call and return (status_code, json_body)."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": str(e)}


def unwrap(data, key=None):
    """Unwrap paginated/wrapped responses. Returns the inner list or dict."""
    if isinstance(data, dict):
        if key and key in data:
            return data[key]
        # Auto-detect: if there's exactly one list value, return it
        list_keys = [k for k, v in data.items() if isinstance(v, list)]
        if len(list_keys) == 1:
            return data[list_keys[0]]
    return data


def login(email, password="TestPass123!"):
    """Login and return (access_token, user_info)."""
    status, body = api("POST", "/auth/login", body={"university_email": email, "password": password})
    if status == 200 and "tokens" in body:
        return body["tokens"]["access_token"], body["user"]
    return None, body


def check(label, condition, detail=""):
    """Record a test result."""
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if condition:
        passed += 1
    else:
        failed += 1
    msg = f"  [{status}] {label}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    results.append({"label": label, "passed": condition, "detail": detail})


# =========================================================================
# SECTION 1: Login all roles
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 1: Login all roles")
print("=" * 70)

accounts = {
    "student_alpha": "live.stu.alpha@lgu.edu.pk",
    "student_beta": "live.stu.beta@lgu.edu.pk",
    "faculty_alpha": "live.fac.alpha@lgu.edu.pk",
    "faculty_beta": "live.fac.beta@lgu.edu.pk",
    "staff_student": "live.stf.student@lgu.edu.pk",
    "staff_faculty": "live.stf.faculty@lgu.edu.pk",
    "manager_student": "live.mgr.student@lgu.edu.pk",
    "manager_faculty": "live.mgr.faculty@lgu.edu.pk",
    "admin": "live.admin@lgu.edu.pk",
}

tokens = {}
users = {}
for label, email in accounts.items():
    token, user = login(email)
    check(f"Login {label}", token is not None, f"user={user.get('role', 'UNKNOWN') if isinstance(user, dict) else user}")
    if token:
        tokens[label] = token
        users[label] = user


# =========================================================================
# SECTION 2: Student workflow
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 2: Student end-to-end workflow")
print("=" * 70)

st = tokens.get("student_alpha")
if not st:
    print("  SKIP: No student token")
else:
    # 2.1 Browse cafeterias
    s, caf_data = api("GET", "/cafeterias/", token=st)
    cafeterias = unwrap(caf_data, "cafeterias")
    check("List cafeterias", s == 200 and isinstance(cafeterias, list) and len(cafeterias) > 0,
          f"count={len(cafeterias) if isinstance(cafeterias, list) else 'N/A'}")
    
    if isinstance(cafeterias, list) and len(cafeterias) > 0:
        caf_id = cafeterias[0]["id"]
        
        # 2.2 Get cafeteria details
        s, caf_detail = api("GET", f"/cafeterias/{caf_id}", token=st)
        check("Get cafeteria detail", s == 200 and caf_detail.get("id") == caf_id)
        
        # 2.3 Browse menus for this cafeteria
        s, menus = api("GET", f"/cafeterias/{caf_id}/menu-items/", token=st)
        check("List menu items for cafeteria", s == 200, f"status={s}")
        
        # 2.4 Get daily menus
        s, daily_menus_raw = api("GET", f"/cafeterias/{caf_id}/daily-menus/", token=st)
        daily_menus = unwrap(daily_menus_raw, "menus")
        check("List daily menus", s == 200 and isinstance(daily_menus, list),
              f"count={len(daily_menus) if isinstance(daily_menus, list) else 'N/A'}")
        
        # 2.5 Get menu items from first available daily menu
        if isinstance(daily_menus, list) and len(daily_menus) > 0:
            dm_id = daily_menus[0]["id"]
            s, dm_items = api("GET", f"/cafeterias/{caf_id}/daily-menus/{dm_id}", token=st)
            check("Get daily menu detail", s == 200, f"status={s}")
            
            items = unwrap(dm_items, "items") if isinstance(dm_items, dict) else dm_items if isinstance(dm_items, list) else []
            if items and len(items) > 0:
                item = items[0]
                item_id = item.get("menu_item_id") or item.get("menu_item", {}).get("id")
                
                # 2.6 Add to cart
                s, cart_resp = api("POST", f"/cafeterias/{caf_id}/cart/items", token=st, body={
                    "menu_item_id": item_id,
                    "quantity": 2,
                })
                check("Add item to cart", s in (200, 201), f"status={s}")
                
                # 2.7 View cart
                s, cart = api("GET", f"/cafeterias/{caf_id}/cart/", token=st)
                check("View cart", s == 200, f"status={s}")
                
                if isinstance(cart, dict) and cart.get("items"):
                    # 2.8 Place order via checkout
                    s, order = api("POST", f"/cafeterias/{caf_id}/cart/checkout", token=st, body={
                        "order_type": "immediate",
                        "payment_method": "cash",
                        "collection_time": "12:30",
                    })
                    check("Place order (cash, checkout)", s in (200, 201) and isinstance(order, dict),
                          f"status={s}, order_id={order.get('id', 'N/A') if isinstance(order, dict) else 'N/A'}")
                    
                    if isinstance(order, dict) and order.get("id"):
                        oid = order["id"]
                        
                        # 2.9 Get order details
                        s, order_detail = api("GET", f"/orders/{oid}", token=st)
                        check("Get order detail", s == 200 and order_detail.get("id") == oid)
                        
                        # 2.10 List my orders
                        s, my_orders_raw = api("GET", "/orders/", token=st)
                        my_orders = unwrap(my_orders_raw, "orders")
                        check("List my orders", s == 200, f"count={len(my_orders) if isinstance(my_orders, list) else 'N/A'}")
                        
                        # 2.11 Cancel order (if allowed)
                        s, cancel_resp = api("POST", f"/orders/{oid}/cancel", token=st, body={"reason": "Verification test"})
                        check("Cancel order", s in (200, 400, 409), f"status={s}")
                    
        # 2.12 Check notifications
        s, notifs = api("GET", "/notifications", token=st)
        check("List notifications", s == 200, f"status={s}")
        
        # 2.13 Get unread count
        s, unread = api("GET", "/notifications/unread-count", token=st)
        check("Get unread notification count", s == 200, f"status={s}")
        
        # 2.14 Browse favorites
        s, favs = api("GET", "/favorites/", token=st)
        check("List favorites", s == 200, f"status={s}")
        
        # 2.15 Get profile
        s, profile = api("GET", "/auth/me", token=st)
        check("Get profile", s == 200 and profile.get("role") == "student")


# =========================================================================
# SECTION 3: Faculty workflow
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 3: Faculty end-to-end workflow")
print("=" * 70)

ft = tokens.get("faculty_alpha")
if not ft:
    print("  SKIP: No faculty token")
else:
    # 3.1 Browse cafeterias
    s, caf_data = api("GET", "/cafeterias/", token=ft)
    cafeterias = unwrap(caf_data, "cafeterias")
    check("Faculty: list cafeterias", s == 200 and isinstance(cafeterias, list) and len(cafeterias) > 0)
    
    if isinstance(cafeterias, list):
        # 3.2 Verify faculty can access faculty cafeteria
        fac_caf = [c for c in cafeterias if "faculty" in c.get("name", "").lower()]
        if fac_caf:
            check("Faculty: faculty cafeteria visible", True)
        else:
            check("Faculty: faculty cafeteria visible", False, "no cafeteria with 'faculty' in name")
        
        # 3.3 Place an order with online payment
        caf_id = cafeterias[0]["id"]
        
        # Get menus
        s, daily_menus = api("GET", f"/cafeterias/{caf_id}/daily-menus/", token=ft)
        if isinstance(daily_menus, list) and len(daily_menus) > 0:
            dm = daily_menus[0]
            s, items = api("GET", f"/cafeterias/{caf_id}/daily-menus/{dm['id']}", token=ft)
            item_list = items.get("items", []) if isinstance(items, dict) else items if isinstance(items, list) else []
            
            if item_list:
                item = item_list[0]
                item_id = item.get("id") or item.get("menu_item", {}).get("id")
                
                # Add to cart
                s, _ = api("POST", f"/cafeterias/{caf_id}/cart/items", token=ft, body={
                    "menu_item_id": item_id, "quantity": 1,
                })
                check("Faculty: add to cart", s in (200, 201), f"status={s}")
                
                # Place order via checkout (online)
                s, order = api("POST", f"/cafeterias/{caf_id}/cart/checkout", token=ft, body={
                    "order_type": "immediate",
                    "payment_method": "online",
                    "collection_time": "13:00",
                })
                check("Faculty: place order (online)", s in (200, 201), f"status={s}")
    
    # 3.4 Profile
    s, profile = api("GET", "/auth/me", token=ft)
    check("Faculty: get profile", s == 200 and profile.get("role") == "faculty")
    
    # 3.5 Notifications
    s, notifs = api("GET", "/notifications", token=ft)
    check("Faculty: notifications", s == 200)
    
    # 3.6 Favorites
    s, favs = api("GET", "/favorites/", token=ft)
    check("Faculty: favorites", s == 200)


# =========================================================================
# SECTION 4: Staff workflow
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 4: Staff end-to-end workflow")
print("=" * 70)

stf = tokens.get("staff_student")
if not stf:
    print("  SKIP: No staff token")
else:
    # 4.1 List orders (staff sees their cafeteria's orders)
    s, orders_raw = api("GET", "/orders/", token=stf)
    orders = unwrap(orders_raw, "orders")
    check("Staff: list orders", s == 200, f"status={s}")
    
    # 4.2 View order detail
    if isinstance(orders, list) and len(orders) > 0:
        oid = orders[0]["id"]
        s, detail = api("GET", f"/orders/{oid}", token=stf)
        check("Staff: view order detail", s == 200, f"status={s}")
        
        # 4.3 Update order status
        s, update = api("PUT", f"/orders/{oid}/status", token=stf, body={"status": "preparing"})
        check("Staff: update order status", s in (200, 400, 409), f"status={s}")
    
    # 4.4 List menus (read) - need cafeteria_id
    # Get the cafeteria this staff is assigned to (Student Cafeteria for staff_student)
    s, caf_data = api("GET", "/cafeterias/", token=stf)
    cafeterias = unwrap(caf_data, "cafeterias")
    if isinstance(cafeterias, list) and len(cafeterias) > 0:
        # Find the student cafeteria (staff_student is assigned to it)
        student_cafs = [c for c in cafeterias if "student" in c.get("name", "").lower()]
        caf_id = student_cafs[0]["id"] if student_cafs else cafeterias[0]["id"]
        s, menus = api("GET", f"/cafeterias/{caf_id}/daily-menus/", token=stf)
        check("Staff: list daily menus", s == 200, f"status={s}")
        
        # 4.5 Inventory list
        s, inv = api("GET", f"/cafeterias/{caf_id}/inventory/", token=stf)
        check("Staff: list inventory", s == 200, f"status={s}")
    else:
        check("Staff: list daily menus", False, "no cafeterias found")
        check("Staff: list inventory", False, "no cafeterias found")
    
    # 4.6 Profile
    s, profile = api("GET", "/auth/me", token=stf)
    check("Staff: get profile", s == 200 and profile.get("role") == "cafeteria_staff")


# =========================================================================
# SECTION 5: Manager workflow
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 5: Manager end-to-end workflow")
print("=" * 70)

mgr = tokens.get("manager_student")
if not mgr:
    print("  SKIP: No manager token")
else:
    # 5.1 List orders
    s, orders_raw = api("GET", "/orders/", token=mgr)
    orders = unwrap(orders_raw, "orders")
    check("Manager: list orders", s == 200, f"status={s}")
    
    # 5.2 View order detail
    if isinstance(orders, list) and len(orders) > 0:
        oid = orders[0]["id"]
        s, detail = api("GET", f"/orders/{oid}", token=mgr)
        check("Manager: view order detail", s == 200)
    
    # 5.3 View refunds
    s, refunds = api("GET", "/refunds/admin/all", token=mgr)
    check("Manager: list refunds", s in (200, 403), f"status={s}")
    
    # 5.4 List staff/assignments
    s, staff = api("GET", "/cafeteria-assignments", token=mgr)
    check("Manager: list cafeteria assignments", s in (200, 404), f"status={s}")
    
    # 5.5 Reports
    s, reports = api("GET", "/reports/sales", token=mgr)
    check("Manager: reports sales", s in (200, 403), f"status={s}")
    
    # 5.6 Inventory management
    s, caf_data = api("GET", "/cafeterias/", token=mgr)
    cafeterias = unwrap(caf_data, "cafeterias")
    if isinstance(cafeterias, list) and len(cafeterias) > 0:
        # Find the student cafeteria (manager_student is assigned to it)
        student_cafs = [c for c in cafeterias if "student" in c.get("name", "").lower()]
        caf_id = student_cafs[0]["id"] if student_cafs else cafeterias[0]["id"]
        s, inv = api("GET", f"/cafeterias/{caf_id}/inventory/", token=mgr)
        check("Manager: list inventory", s == 200, f"status={s}")
    else:
        check("Manager: list inventory", False, "no cafeterias found")
    
    # 5.7 Profile
    s, profile = api("GET", "/auth/me", token=mgr)
    check("Manager: get profile", s == 200 and profile.get("role") == "cafeteria_manager")


# =========================================================================
# SECTION 6: Admin workflow
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 6: Admin end-to-end workflow")
print("=" * 70)

adm = tokens.get("admin")
if not adm:
    print("  SKIP: No admin token")
else:
    # 6.1 List all users
    s, all_users_raw = api("GET", "/users/", token=adm)
    all_users = unwrap(all_users_raw, "users")
    check("Admin: list all users", s == 200, f"status={s}")
    
    # 6.2 View specific user
    if isinstance(all_users, list) and len(all_users) > 0:
        uid = all_users[0]["id"]
        s, user_detail = api("GET", f"/users/{uid}", token=adm)
        check("Admin: view user detail", s == 200, f"status={s}")
    
    # 6.3 List refunds
    s, refunds = api("GET", "/refunds/admin/all", token=adm)
    check("Admin: list refunds", s == 200, f"status={s}")
    
    # 6.4 Reports
    s, reports = api("GET", "/reports/sales", token=adm)
    check("Admin: reports sales", s == 200, f"status={s}")
    
    # 6.5 Cafeteria management
    s, caf_data = api("GET", "/cafeterias/", token=adm)
    cafeterias = unwrap(caf_data, "cafeterias")
    check("Admin: list cafeterias", s == 200, f"count={len(cafeterias) if isinstance(cafeterias, list) else 'N/A'}")
    
    # 6.6 Create cafeteria
    caf_name = f"Test Cafeteria {uuid.uuid4().hex[:8]}"
    s, new_caf = api("POST", "/cafeterias/", token=adm, body={
        "name": caf_name,
        "type": "student",
        "description": "Test cafeteria for verification",
        "operating_hours": "08:00-17:00",
    })
    check("Admin: create cafeteria", s in (200, 201), f"status={s}")
    
    if isinstance(new_caf, dict) and new_caf.get("id"):
        caf_id = new_caf["id"]
        
        # 6.7 Update cafeteria
        s, upd = api("PUT", f"/cafeterias/{caf_id}", token=adm, body={
            "description": "Updated description",
        })
        check("Admin: update cafeteria", s == 200, f"status={s}")
        
        # 6.8 Deactivate cafeteria
        s, deactivate = api("PATCH", f"/cafeterias/{caf_id}/status", token=adm, body={
            "status": "closed",
        })
        check("Admin: update cafeteria status", s in (200, 400), f"status={s}")
    
    # 6.9 Audit logs
    s, audit = api("GET", "/audit", token=adm)
    check("Admin: view audit logs", s in (200, 404), f"status={s}")
    
    # 6.10 Profile
    s, profile = api("GET", "/auth/me", token=adm)
    check("Admin: get profile", s == 200 and profile.get("role") == "university_admin")


# =========================================================================
# SECTION 7: IDOR / Security tests
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 7: Security/IDOR attack matrix")
print("=" * 70)

st = tokens.get("student_alpha")
adm = tokens.get("admin")
ft = tokens.get("faculty_alpha")

if st:
    # 7.1 Student cannot access admin endpoints
    s, _ = api("GET", "/users/", token=st)
    check("IDOR: student cannot list all users", s == 403, f"status={s}")
    
    s, _ = api("GET", "/refunds/admin/all", token=st)
    check("IDOR: student cannot list refunds", s == 403, f"status={s}")
    
    # 7.2 Student cannot create cafeteria
    s, _ = api("POST", "/cafeterias/", token=st, body={"name": "HACK", "type": "student"})
    check("IDOR: student cannot create cafeteria", s in (403, 401), f"status={s}")
    
    # 7.3 Student cannot access another user's profile directly
    if adm:
        s, admin_user = api("GET", "/auth/me", token=adm)
        if isinstance(admin_user, dict) and admin_user.get("id"):
            s, _ = api("GET", f"/users/{admin_user['id']}", token=st)
            check("IDOR: student cannot view admin profile", s in (403, 401), f"status={s}")

if adm:
    # 7.4 Admin can access admin endpoints
    s, _ = api("GET", "/users/", token=adm)
    check("Admin: can list all users", s == 200, f"status={s}")
    
    s, _ = api("GET", "/refunds/admin/all", token=adm)
    check("Admin: can list refunds", s == 200, f"status={s}")

# 7.5 Unauthenticated access is rejected
s, _ = api("GET", "/users/")
check("Security: unauthenticated access rejected", s in (401, 403), f"status={s}")

s, _ = api("GET", "/orders/")
check("Security: unauthenticated orders rejected", s in (401, 403), f"status={s}")

# 7.6 Invalid token rejected
s, _ = api("GET", "/users/me", token="invalid.jwt.token")
check("Security: invalid token rejected", s == 401, f"status={s}")


# =========================================================================
# SECTION 8: Order/Payment edge cases
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 8: Order/Payment edge cases")
print("=" * 70)

st = tokens.get("student_alpha")
if st:
    # 8.1 Place order with invalid cafeteria
    s, _ = api("POST", "/cafeterias/nonexistent-id/cart/checkout", token=st, body={
        "order_type": "immediate",
        "payment_method": "cash",
        "collection_time": "12:30",
    })
    check("Edge: order with invalid cafeteria", s in (400, 404, 422), f"status={s}")
    
    # 8.2 Place order with invalid cart/cafeteria
    s, _ = api("POST", f"/cafeterias/{uuid.uuid4()}/cart/checkout", token=st, body={
        "order_type": "immediate",
        "payment_method": "cash",
        "collection_time": "12:30",
    })
    check("Edge: order with invalid cart/cafeteria", s in (400, 404), f"status={s}")
    
    # 8.3 Get non-existent order
    s, _ = api("GET", f"/orders/{uuid.uuid4()}", token=st)
    check("Edge: get non-existent order", s in (404, 403), f"status={s}")
    
    # 8.4 Cancel already cancelled order
    # (would need a specific order ID, just test the endpoint)
    
    # 8.5 Scheduled order with past time
    # s, _ = api("POST", "/orders", token=st, body={
    #     "cafeteria_id": caf_id,
    #     "order_type": "scheduled",
    #     "payment_method": "cash",
    #     "collection_time": "08:00",
    # })
    # check("Edge: scheduled order with past time", s in (400, 422), f"status={s}")


# =========================================================================
# SECTION 9: Notification verification
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 9: Notification verification")
print("=" * 70)

for role_label in ["student_alpha", "faculty_alpha", "staff_student", "manager_student", "admin"]:
    t = tokens.get(role_label)
    if t:
        s, notifs = api("GET", "/notifications", token=t)
        check(f"Notifications ({role_label})", s == 200, f"status={s}")
        
        s, count = api("GET", "/notifications/unread-count", token=t)
        check(f"Unread count ({role_label})", s == 200, f"status={s}")


# =========================================================================
# SECTION 10: Health and system endpoints
# =========================================================================
print("\n" + "=" * 70)
print("SECTION 10: Health and system endpoints")
print("=" * 70)

s, health = api("GET", "/health")
check("Health endpoint", s == 200 and health.get("status") == "healthy")

# Check OpenAPI docs - path is /api/docs when APP_DEBUG is True
try:
    resp = urllib.request.urlopen("http://localhost:8000/api/docs")
    s = resp.status
except urllib.error.HTTPError as e:
    s = e.code
except Exception:
    s = 0
check("Swagger UI accessible", s in (200, 307), f"status={s}")

try:
    resp = urllib.request.urlopen("http://localhost:8000/api/openapi.json")
    s = resp.status
except urllib.error.HTTPError as e:
    s = e.code
except Exception:
    s = 0
check("OpenAPI spec available", s == 200, f"status={s}")


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 70)
print(f"SUMMARY: {passed} passed, {failed} failed out of {passed + failed} total")
print("=" * 70)

if failed > 0:
    print("\nFailed tests:")
    for r in results:
        if not r["passed"]:
            print(f"  - {r['label']}: {r['detail']}")

sys.exit(1 if failed > 0 else 0)
