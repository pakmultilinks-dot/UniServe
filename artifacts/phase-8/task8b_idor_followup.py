"""Phase 8 — Task 8b: IDOR/info-disclosure follow-up on cancel + confirmation of
the two mis-stated expectations from task8_authz_tests.py.

Isolated API only (127.0.0.1:8001 / uniserve_test_phase7). Never prod.

Findings under test:
  1. `cancel_order` validates ORDER STATUS before OWNERSHIP (orders/service.py:380
     -> status checks at ~399-405, ownership check only at ~420 inside the
     non-manager branch). GET /orders/{id} returns 403 "Order not found" to a
     non-owner, but POST /orders/{id}/cancel may reveal status via the error
     message = order-status oracle for any authenticated user.
  2. Ownership IS still enforced for a PENDING order (no write-IDOR) — proven
     below by creating a real pending order and having a stranger try to cancel.
  3. Re-stated expectations: manager POST /users/ is ALLOWED by role
     (RequireRole(UNIVERSITY_ADMIN, CAFETERIA_MANAGER)) so 422 = body schema
     error, not a role failure; student GET Faculty-Cafeteria cart -> 403 is
     CORRECT audience enforcement.
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
CAF_FACULTY = "c84affd5-16bf-47bc-b50c-c54f4442f408"
ORDER_COMPLETED = "1012b956-1d49-4ffb-95bc-564cd57b6e21"   # faculty-owned, completed
ORDER_CANCELLED = "a05d5eed-a7e0-405d-9df1-9301c28de8b1"   # faculty-owned, cancelled
ITEM_FACULTY = "5d33b252-ec7d-4cf1-bc28-db366e7cdec8"      # PHASE8, Faculty Cafeteria


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
    detail = body.get("detail") if isinstance(body, dict) else (str(body)[:140] if body else "")
    if isinstance(expected, (list, tuple, set)):
        ok = str(s) in {str(x) for x in expected}
        exp_txt = "/".join(str(x) for x in expected)
    else:
        ok = str(s) == str(expected)
        exp_txt = str(expected)
    results.append({"test": label, "expected": exp_txt, "got": s, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exp {exp_txt} got {s} | {detail}")
    return body if isinstance(body, dict) else {}


admin = login("admin@lgu.edu.pk", "Admin123!")
mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")
print("tokens:", {k: bool(v) for k, v in dict(admin=admin, mgr=mgr, fac=fac, stu=stu).items()})

# --------------------------------------------------------------- 1. Status oracle
print("\n=== 1. Cancel endpoint as a non-owner (status oracle probe) ===")
_, p_completed = call("POST", f"/orders/{ORDER_COMPLETED}/cancel", stu, {"reason": "other"})
print("   completed ->", json.dumps(p_completed)[:200])
_, p_cancelled = call("POST", f"/orders/{ORDER_CANCELLED}/cancel", stu, {"reason": "other"})
print("   cancelled ->", json.dumps(p_cancelled)[:200])
_, p_missing = call("POST", f"/orders/00000000-0000-0000-0000-000000000000/cancel", stu,
                    {"reason": "other"})
print("   missing   ->", json.dumps(p_missing)[:200])

# Contrast: the read endpoint hides existence from the same user
s, b = call("GET", f"/orders/{ORDER_COMPLETED}", stu)
check("GET foreign order -> 403 'Order not found'", "403", s, b)
hidden = isinstance(b, dict) and b.get("detail") == "Order not found"
print("   GET hides existence:", hidden)

# The oracle is confirmed if the cancel error differs per status for a non-owner.
completed_msg = p_completed.get("detail") if isinstance(p_completed, dict) else None
cancelled_msg = p_cancelled.get("detail") if isinstance(p_cancelled, dict) else None
missing_msg = p_missing.get("detail") if isinstance(p_missing, dict) else None
oracle = len({completed_msg, cancelled_msg, missing_msg}) > 1
results.append({"test": "cancel-status oracle (non-owner learns order status)",
                "expected": "no status-dependent detail", "got": str(len({completed_msg, cancelled_msg, missing_msg})),
                "ok": not oracle, "detail": f"completed={completed_msg!r} cancelled={cancelled_msg!r} missing={missing_msg!r}"})
print(f"[{'PASS' if not oracle else 'FAIL'}] cancel-status oracle: distinct_details="
      f"{len({completed_msg, cancelled_msg, missing_msg})}")

# ------------------------------------------------------- 2. Ownership on PENDING
print("\n=== 2. Ownership enforced for a PENDING order (no write-IDOR) ===")
# Build a fresh pending order as the faculty user.
s, cart = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/items", fac,
               {"menu_item_id": ITEM_FACULTY, "quantity": 1})
print("   cart add:", s)
s, checkout = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/checkout", fac,
                   {"idempotency_key": "phase8-authz-pending-001"})
order_id = checkout.get("order_id") if isinstance(checkout, dict) else None
if order_id is None and isinstance(checkout, dict):
    order_id = (checkout.get("order") or {}).get("id")
check("faculty checkout -> 201 (pending order created)", "201", s, checkout)
print("   pending order:", order_id)
if order_id:
    s, b = call("GET", f"/orders/{order_id}", stu)
    check("stranger GET pending order -> 403", "403", s, b)
    s, b = call("POST", f"/orders/{order_id}/cancel", stu, {"reason": "other"})
    check("stranger cancel pending order -> 400 (ownership)", (400, 403), s, b)
    print("   stranger cancel detail:", json.dumps(b)[:200])
    # confirm the order was NOT cancelled
    s, b = call("GET", f"/orders/{order_id}", fac)
    still_pending = isinstance(b, dict) and b.get("status") == "pending"
    results.append({"test": "pending order NOT cancelled by stranger",
                    "expected": "status=pending", "got": (b.get("status") if isinstance(b, dict) else s),
                    "ok": still_pending, "detail": f"status={(b.get('status') if isinstance(b, dict) else s)}"})
    print(f"[{'PASS' if still_pending else 'FAIL'}] pending order NOT cancelled by stranger")
    # owner still can cancel it (control) — restores tidy state
    s, b = call("POST", f"/orders/{order_id}/cancel", fac, {"reason": "other"})
    check("owner cancel own pending order -> 200", "200", s, b)

# --------------------------------------- 3. Re-stated expectations from task 8
print("\n=== 3. Re-stated expectations ===")
# (a) manager IS allowed to create users by role; only the body schema is wrong
s, b = call("POST", "/users/", mgr,
            {"university_email": "phase8.intruder@lgu.edu.pk", "full_name": "Intruder",
             "role": "student", "password": "TestPass123!"})
check("mgr POST /users/ -> 422 body-schema (role ALLOWED)", "422", s, b)
s, b = call("GET", "/users/", mgr)
check("mgr GET /users/ -> 403 (read is admin-only)", "403", s, b)
# (b) student hitting the Faculty Cafeteria audience gate is correct behaviour
s, b = call("GET", f"/cafeterias/{CAF_FACULTY}/cart", stu)
check("stu GET Faculty cart -> 403 audience gate", "403", s, b)
aud = isinstance(b, dict) and "restricted to faculty" in str(b.get("detail", ""))
print("   audience detail:", json.dumps(b)[:200], "| gate ok:", aud)
# (c) the same student reaches their own cafeteria fine
s, b = call("GET", "/cafeterias/9ebdb4ce-d563-4e39-b968-c66beebdf351/cart", stu)
check("stu GET Student cart -> 200", "200", s, b)

print("\n=== SUMMARY ===")
passed = sum(1 for r in results if r["ok"])
print(f"{passed}/{len(results)} checks matched expectation")
for r in results:
    if not r["ok"]:
        print(f"  FAIL: {r['test']} exp={r['expected']} got={r['got']} detail={r['detail']}")
