"""Phase 8 — Task 6 negative-path + cancellation + RBAC checks.

Runs ONLY against the isolated API (127.0.0.1:8001 / uniserve_test_phase7).
Never touches uniserve_prod. Records actual status codes + bodies.
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
CAF = "c84affd5-16bf-47bc-b50c-c54f4442f408"   # Faculty Cafeteria
ITEM = "5d33b252-ec7d-4cf1-bc28-db366e7cdec8"  # PHASE8 item
COMPLETED_ORDER = "1012b956-1d49-4ffb-95bc-564cd57b6e21"

results = []


def call(method, path, token=None, body=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except Exception:
            return e.code, raw[:300]


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    return ((t.get("tokens") or {}).get("access_token")) if s == 200 else None


def record(label, expected, s, body):
    detail = body.get("detail") if isinstance(body, dict) else str(body)[:120]
    code = body.get("code") if isinstance(body, dict) else ""
    ok = str(s) == expected
    results.append(
        {"test": label, "expected": expected, "got": s, "ok": ok, "detail": detail, "code": code}
    )
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: expected {expected}, got {s} | {detail} {code}")


mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")
staff_other = login("ahmed.raza@lgu.edu.pk", "TestPass123!")
print("tokens:", {k: bool(v) for k, v in
                  {"mgr": mgr, "fac": fac, "stu": stu, "staff_other": staff_other}.items()})

print("\n=== A. Invalid transitions on a COMPLETED order (manager) ===")
record("confirm completed order -> 400", "400",
       *call("POST", f"/orders/{COMPLETED_ORDER}/confirm", mgr, {}))
record("prepare completed order -> 400", "400",
       *call("POST", f"/orders/{COMPLETED_ORDER}/prepare", mgr, {"notes": "n"}))
record("ready on completed order -> 400", "400",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/ready", mgr, {"notes": "n"}))
record("status completed->preparing -> 400", "400",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", mgr, {"status": "preparing"}))
record("status completed->ready -> 400", "400",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", mgr, {"status": "ready"}))
record("status pattern reject 'bogus' -> 422", "422",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", mgr, {"status": "bogus"}))

print("\n=== B. RBAC: staff/manager scope + auth gates ===")
record("student PUT status -> 403", "403",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", stu, {"status": "preparing"}))
record("faculty PUT status -> 403", "403",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", fac, {"status": "preparing"}))
record("staff of OTHER cafeteria -> 403", "403",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", staff_other, {"status": "preparing"}))
record("unauthenticated PUT status -> 401", "401",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", None, {"status": "preparing"}))
record("garbage token -> 401", "401",
       *call("PUT", f"/orders/{COMPLETED_ORDER}/status", "not-a-real-token", {"status": "preparing"}))
record("student manager-cancel -> 403", "403",
       *call("POST", f"/orders/{COMPLETED_ORDER}/manager-cancel", stu, {"reason": "x"}))
record("student reject order -> 403", "403",
       *call("POST", f"/orders/{COMPLETED_ORDER}/reject", stu, {"reason": "out_of_stock"}))

print("\n=== C. Stale stock: add more than available to cart (faculty) ===")
s, inv = call("GET", f"/cafeterias/{CAF}/inventory", fac)
avail = None
if s == 200:
    for row in inv.get("items", []) if isinstance(inv, dict) else inv:
        if row.get("menu_item_id") == ITEM:
            avail = row.get("quantity")
print("available:", avail)
if avail is not None:
    record(f"cart add qty {avail + 5} (> stock) -> 400", "400",
           *call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                 {"menu_item_id": ITEM, "quantity": avail + 5}))
    record("cart add qty 0 -> 4xx", "422",
           *call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                 {"menu_item_id": ITEM, "quantity": 0}))
    record("cart add negative qty -> 4xx", "422",
           *call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                 {"menu_item_id": ITEM, "quantity": -3}))

print("\n=== D. Place a fresh order for cancellation testing (faculty) ===")
s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac, {"menu_item_id": ITEM, "quantity": 1})
print("add:", s)
s, order = call("POST", f"/cafeterias/{CAF}/cart/checkout", fac,
                {"payment_method": "cash", "order_type": "immediate",
                 "idempotency_key": "phase8-cancel-001"})
print("checkout:", s, order.get("id") if isinstance(order, dict) else order)
new_id = order.get("id") if isinstance(order, dict) else None

if new_id:
    print("\n=== E. Duplicate checkout with SAME idempotency key ===")
    s2, r2 = call("POST", f"/cafeterias/{CAF}/cart/checkout", fac,
                  {"payment_method": "cash", "order_type": "immediate",
                   "idempotency_key": "phase8-cancel-001"})
    same = isinstance(r2, dict) and r2.get("id") == new_id
    results.append({"test": "duplicate checkout idempotency", "expected": "same-order/4xx",
                    "got": s2, "ok": (s2 in (200, 201, 409)) and (same or s2 == 409),
                    "detail": f"id={r2.get('id') if isinstance(r2, dict) else r2}", "code": ""})
    print(f"[{'PASS' if results[-1]['ok'] else 'WARN'}] duplicate checkout: {s2} same_order={same}")

    print("\n=== F. Invalid transition on a PENDING order (skip confirm) ===")
    record("prepare unconfirmed pending -> 400", "400",
           *call("POST", f"/orders/{new_id}/prepare", mgr, {"notes": "skip-confirm"}))
    record("pending -> ready (skip preparing) -> 400", "400",
           *call("PUT", f"/orders/{new_id}/status", mgr, {"status": "ready"}))

    print("\n=== G. User cancellation of a PENDING order (faculty) ===")
    s, r = call("POST", f"/orders/{new_id}/cancel", fac, {"reason": "Changed my mind"})
    record("user cancel pending -> 200", "200", s, r)
    if isinstance(r, dict):
        results.append({"test": "cancel sets status", "expected": "cancelled", "got": r.get("status"),
                        "ok": r.get("status") == "cancelled", "detail": r.get("status"), "code": ""})
        print(f"[{'PASS' if r.get('status')=='cancelled' else 'FAIL'}] status after cancel = {r.get('status')}")

    print("\n=== H. Double-cancel already cancelled -> 4xx ===")
    record("second cancel -> 400", "400", *call("POST", f"/orders/{new_id}/cancel", fac, {"reason": "again"}))

    print("\n=== I. Cancel a COMPLETED order -> 4xx (policy) ===")
    record("cancel completed -> 400", "400",
           *call("POST", f"/orders/{COMPLETED_ORDER}/cancel", fac, {"reason": "late"}))

print("\n=== SUMMARY ===")
passed = sum(1 for r in results if r["ok"])
print(f"{passed}/{len(results)} checks matched expectation")
for r in results:
    if not r["ok"]:
        print("  MISMATCH:", r)
