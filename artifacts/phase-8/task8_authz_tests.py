"""Phase 8 — Task 8: authorization, role separation and cafeteria isolation.

Isolated API only (127.0.0.1:8001 / uniserve_test_phase7). Never prod.
Read-only against production is not performed here. No writes outside the
isolated database; the only mutating calls are ones we expect to be DENIED
plus one negative cart test that is cleaned up.

Covers:
  A. Authentication (401) — missing / malformed / expired-style tokens
  B. University-admin-only endpoints (403 for faculty, student, manager, staff)
  C. Manager/staff-only endpoints (403 for faculty, student)
  D. Cafeteria-scope isolation (staff/manager of cafeteria X vs cafeteria Y)
  E. Cross-user IDOR (order/payment/refund/user detail of another user)
  F. Cart cafeteria scoping (menu item from a different cafeteria)
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"

CAF_FACULTY = "c84affd5-16bf-47bc-b50c-c54f4442f408"
CAF_STUDENT = "9ebdb4ce-d563-4e39-b968-c66beebdf351"

ORDER_FACULTY = "1012b956-1d49-4ffb-95bc-564cd57b6e21"   # order #1, owned by faculty
PAYMENT_FACULTY = "2d4c8d4e-b1e0-4146-9b4a-eeb8683e8b1c"

USER_FACULTY = "dc3b3f18-1923-459a-9646-4f924e37e4ff"
USER_STUDENT = "21bef1ca-4bd8-41d5-8b95-68498dc10e75"   # ayesha.khan

ITEM_FACULTY_MENU = "5d33b252-ec7d-4cf1-bc28-db366e7cdec8"   # PHASE8, Faculty Cafeteria
ITEM_STUDENT_MENU = "78fb9407-b53c-4515-8961-0df4b40f22da"   # Chicken Burger, Student Cafeteria


def call(method, path, token=None, body=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + token} if token else {})},
    )
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw or "null")
            except Exception:
                return r.status, raw[:250]
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except Exception:
            return e.code, raw[:250]
    except Exception as e:
        return -1, str(e)[:200]


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    return ((t.get("tokens") or {}).get("access_token")) if s == 200 else None


results = []


def check(label, expected, s, body=None):
    detail = body.get("detail") if isinstance(body, dict) else (str(body)[:130] if body else "")
    code = body.get("code") if isinstance(body, dict) else ""
    if isinstance(expected, (list, tuple, set)):
        ok = str(s) in {str(x) for x in expected}
        exp_txt = "/".join(str(x) for x in expected)
    else:
        ok = str(s) == str(expected)
        exp_txt = str(expected)
    results.append({"test": label, "expected": exp_txt, "got": s, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exp {exp_txt} got {s} | {detail} {code}")
    return body if isinstance(body, dict) else {}


tokens = {
    "admin": login("admin@lgu.edu.pk", "Admin123!"),
    "mgr": login("sana.malik@lgu.edu.pk", "TestPass123!"),        # Faculty Cafeteria
    "staff": login("ahmed.raza@lgu.edu.pk", "TestPass123!"),      # Student Cafeteria
    "fac": login("dr.sana.malik@lgu.edu.pk", "TestPass123!"),
    "stu": login("ayesha.khan@student.lgu.edu.pk", "TestPass123!"),
}
print("tokens:", {k: bool(v) for k, v in tokens.items()})
admin, mgr, staff, fac, stu = (tokens[k] for k in ("admin", "mgr", "staff", "fac", "stu"))

# ---------------------------------------------------------------- A. Auth
print("\n=== A. Authentication (401) ===")
for label, path, tok in [
    ("orders list, no token", "/orders", None),
    ("orders list, garbage token", "/orders", "not.a.valid.token"),
    ("cart, no token", f"/cafeterias/{CAF_FACULTY}/cart", None),
    ("users list, no token", "/users/", None),
    ("reports sales, no token", "/reports/sales", None),
    ("refunds admin/all, empty bearer", "/refunds/admin/all", ""),
    ("notification list, garbage token", "/notifications", "xxxxx"),
    ("order detail, no token", f"/orders/{ORDER_FACULTY}", None),
]:
    s, b = call("GET", path, tok)
    check(label, "401", s, b)

# ------------------------------------------- B. Admin-only endpoints (403)
print("\n=== B. University-admin-only endpoints ===")
admin_only = [
    ("GET /users/", "GET", "/users/", None),
    ("POST /users/ (create)", "POST", "/users/",
     {"university_email": "phase8.intruder@lgu.edu.pk", "full_name": "Intruder",
      "role": "student", "password": "TestPass123!"}),
    ("GET /users/{id}", "GET", f"/users/{USER_FACULTY}", None),
    ("PUT /users/{id}/role", "PUT", f"/users/{USER_STUDENT}/role", {"role": "student"}),
    ("GET /administration/overview", "GET", "/administration/overview", None),
    ("GET /administration/audit-events", "GET", "/administration/audit-events", None),
    ("POST /notifications/broadcast", "POST", "/notifications/broadcast",
     {"title": "intruder", "message": "should be denied", "audience": "all"}),
    ("PUT /cafeterias/{id}", "PUT", f"/cafeterias/{CAF_FACULTY}", {"name": "renamed"}),
    ("POST /cafeterias/", "POST", "/cafeterias/",
     {"name": "Intruder Cafeteria", "location": "nowhere"}),
    ("GET /reports/sales/by-cafeteria", "GET", "/reports/sales/by-cafeteria", None),
]
for who in ("fac", "stu", "mgr", "staff"):
    for label, method, path, body in admin_only:
        s, b = call(method, path, tokens[who], body)
        check(f"{who}: {label}", "403", s, b)

# ------------------------------- C. Manager/staff-only endpoints (403)
print("\n=== C. Manager/staff-only endpoints ===")
staff_only = [
    ("PUT /orders/{id}/status", "PUT", f"/orders/{ORDER_FACULTY}/status", {"status": "preparing"}),
    ("POST /orders/{id}/confirm", "POST", f"/orders/{ORDER_FACULTY}/confirm", {}),
    ("POST /orders/{id}/prepare", "POST", f"/orders/{ORDER_FACULTY}/prepare", {}),
    ("PUT /orders/{id}/ready", "PUT", f"/orders/{ORDER_FACULTY}/ready", {}),
    ("POST /orders/{id}/manager-cancel", "POST", f"/orders/{ORDER_FACULTY}/manager-cancel",
     {"reason": "other", "reason_note": "should be denied for non staff"}),
    ("POST /orders/{id}/reject", "POST", f"/orders/{ORDER_FACULTY}/reject",
     {"reason": "other", "reason_note": "should be denied for non staff"}),
    ("GET /cafeterias/{id}/inventory/", "GET", f"/cafeterias/{CAF_FACULTY}/inventory/", None),
    ("POST /cafeterias/{id}/inventory/adjust", "POST",
     f"/cafeterias/{CAF_FACULTY}/inventory/adjust",
     {"inventory_item_id": "9031b184-2a15-43fd-9bde-c6b708185b19",
      "adjustment_quantity": 1, "reason": "should be denied"}),
    ("GET /reports/sales", "GET", "/reports/sales", None),
    ("POST /cafeterias/{id}/menu-items/", "POST",
     f"/cafeterias/{CAF_FACULTY}/menu-items/",
     {"name": "intruder item", "price": 100, "category": "Burgers"}),
]
for who in ("fac", "stu"):
    for label, method, path, body in staff_only:
        s, b = call(method, path, tokens[who], body)
        check(f"{who}: {label}", "403", s, b)

# manager-only endpoints must still deny cafeteria_staff and customers
print("\n--- manager-only endpoints (staff/faculty/student denied) ---")
mgr_only = [
    ("POST /orders/{id}/manager-cancel", "POST", f"/orders/{ORDER_FACULTY}/manager-cancel",
     {"reason": "other", "reason_note": "should be denied"}),
    ("POST /orders/{id}/reject", "POST", f"/orders/{ORDER_FACULTY}/reject",
     {"reason": "other", "reason_note": "should be denied"}),
    ("POST /users/{id}/suspend", "POST", f"/users/{USER_STUDENT}/suspend", {}),
]
for who in ("staff", "fac", "stu"):
    for label, method, path, body in mgr_only:
        s, b = call(method, path, tokens[who], body)
        check(f"{who}: {label}", "403", s, b)

# ---------------------------------- D. Cafeteria-scope isolation
print("\n=== D. Cafeteria scope isolation ===")
# staff (Student Cafeteria) vs Faculty Cafeteria order
s, b = call("GET", f"/orders/{ORDER_FACULTY}", staff)
check("staff(STUDENT caf): GET faculty-caf order -> 403", "403", s, b)
for label, method, path, body in [
    ("confirm faculty-caf order", "POST", f"/orders/{ORDER_FACULTY}/confirm", {}),
    ("prepare faculty-caf order", "POST", f"/orders/{ORDER_FACULTY}/prepare", {}),
    ("set status faculty-caf order", "PUT", f"/orders/{ORDER_FACULTY}/status",
     {"status": "preparing"}),
]:
    s, b = call(method, path, staff, body)
    check(f"staff(STUDENT caf): {label} -> 403", "403", s, b)

s, b = call("GET", f"/orders/cafeteria/{CAF_FACULTY}", staff)
check("staff(STUDENT caf): list faculty-caf orders -> 403", "403", s, b)
s, b = call("GET", f"/cafeterias/{CAF_FACULTY}/inventory/", staff)
check("staff(STUDENT caf): faculty-caf inventory -> 403", "403", s, b)

# manager (Faculty Cafeteria) vs Student Cafeteria
s, b = call("GET", f"/cafeterias/{CAF_STUDENT}/inventory/", mgr)
check("mgr(FACULTY caf): student-caf inventory -> 403", "403", s, b)
s, b = call("POST", f"/cafeterias/{CAF_STUDENT}/inventory/adjust", mgr,
            {"inventory_item_id": "78fb9407-b53c-4515-8961-0df4b40f22da",
             "adjustment_quantity": 1, "reason": "cross cafeteria should deny"})
check("mgr(FACULTY caf): adjust student-caf inventory -> 403", "403", s, b)
s, b = call("GET", f"/orders/cafeteria/{CAF_STUDENT}", mgr)
check("mgr(FACULTY caf): list student-caf orders -> 403", "403", s, b)

# staff (Student Cafeteria) CAN reach own cafeteria (positive control)
s, b = call("GET", f"/cafeterias/{CAF_STUDENT}/inventory/", staff)
check("staff(STUDENT caf): own inventory -> 200", "200", s, b)
s, b = call("GET", f"/orders/cafeteria/{CAF_STUDENT}", staff)
check("staff(STUDENT caf): own orders -> 200", "200", s, b)

# ------------------------------------------ E. Cross-user IDOR
print("\n=== E. Cross-user IDOR ===")
s, b = call("GET", f"/orders/{ORDER_FACULTY}", stu)
check("student: GET faculty's order -> 403", "403", s, b)
s, b = call("GET", f"/orders/cafeteria/{CAF_FACULTY}", stu)
check("student: GET faculty-caf order list -> 403", "403", s, b)
s, b = call("GET", f"/refunds/refundable/{ORDER_FACULTY}", stu)
check("student: GET refundable for faculty's order -> 403", "403", s, b)
s, b = call("GET", f"/refunds/order/{ORDER_FACULTY}", stu)
check("student: GET refunds for faculty's order -> 403", "403", s, b)
s, b = call("GET", f"/payments/order/{ORDER_FACULTY}", stu)
check("student: GET payment for faculty's order -> 403", "403", s, b)
s, b = call("GET", f"/payments/{PAYMENT_FACULTY}", stu)
check("student: GET faculty's payment by id -> 403", "403", s, b)
s, b = call("POST", f"/orders/{ORDER_FACULTY}/cancel", stu, {})
check("student: cancel faculty's order -> 403", "403", s, b)

# faculty trying to read another faculty's order
s, b = call("GET", f"/orders/{ORDER_FACULTY}", fac)
other_fac = "03087f64-c12e-4425-aaba-4386e779fec5"  # dr.imran — used only as a user id probe
s, b = call("GET", f"/users/{USER_STUDENT}", fac)
check("faculty: GET user detail (admin-only) -> 403", "403", s, b)

# ------------------------------ F. Cart cafeteria scoping
print("\n=== F. Cart cafeteria scoping ===")
# Try to add a Student-Cafeteria menu item into the Faculty-Cafeteria cart.
s, b = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/items", fac,
            {"menu_item_id": ITEM_STUDENT_MENU, "quantity": 1})
check("faculty: add STUDENT-caf item to FACULTY cart -> 4xx", (400, 403, 404, 422), s, b)
print("   detail:", json.dumps(b)[:300])
if isinstance(b, dict) and b.get("cart_item_id") or s in (200, 201):
    # unexpected success — clean it up so we leave state tidy
    print("   !! cross-cafeteria add succeeded; removing")
    call("DELETE", f"/cafeterias/{CAF_FACULTY}/cart/items/{b.get('cart_item_id')}", fac)

# positive control: own-cafeteria item still addable
s, b = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/items", fac,
            {"menu_item_id": ITEM_FACULTY_MENU, "quantity": 1})
check("faculty: add FACULTY-caf item to FACULTY cart -> 201", "201", s, b)
cid = b.get("cart_item_id") if isinstance(b, dict) else None
if cid:
    call("DELETE", f"/cafeterias/{CAF_FACULTY}/cart/items/{cid}", fac)

# student cannot read another user's cart (cart is session-scoped)
s, b = call("GET", f"/cafeterias/{CAF_FACULTY}/cart", stu)
check("student: GET faculty's cart path -> 200 (own empty cart)", "200", s, b)

print("\n=== SUMMARY ===")
passed = sum(1 for r in results if r["ok"])
print(f"{passed}/{len(results)} checks matched expectation")
for r in results:
    if not r["ok"]:
        print(f"  FAIL: {r['test']} exp={r['expected']} got={r['got']} detail={r['detail']}")
