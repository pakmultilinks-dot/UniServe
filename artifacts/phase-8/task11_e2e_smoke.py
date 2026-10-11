"""Phase 8 Task 11 - post-remediation E2E smoke (isolated DB only).

Full flow against the LIVE isolated API with the D7/D8 fixes loaded:
login -> add to cart -> checkout (cash) -> staff lifecycle to completed
-> cash refund settles manually -> cancel-oracle parity re-asserted.
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
CAF_FACULTY = "c84affd5-16bf-47bc-b50c-c54f4442f408"
ITEM = "5d33b252-ec7d-4cf1-bc28-db366e7cdec8"  # PHASE8-E2E-7F3A9C Test Burger


def call(method, path, token=None, body=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    assert s == 200, (email, s, str(t)[:200])
    return t["tokens"]["access_token"]


fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")

results = []


def check(name, expected, got, detail=""):
    ok = str(got) == str(expected)
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected {expected}, got {got} {str(detail)[:130]}")


print("=== 1. Cart + checkout (cash) ===")
s, b = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/items", fac,
            {"menu_item_id": ITEM, "quantity": 1})
check("add to cart", 201, s, b)
s, checkout = call("POST", f"/cafeterias/{CAF_FACULTY}/cart/checkout", fac,
                   {"payment_method": "cash", "order_type": "immediate"})
check("checkout -> 201", 201, s, checkout if s != 201 else "")
order_id = checkout.get("id") if isinstance(checkout, dict) else None
check("order id created", True, bool(order_id), order_id)

print("\n=== 2. Staff lifecycle: confirm -> prepare -> ready -> collect ===")
s, b = call("POST", f"/orders/{order_id}/confirm", mgr, {})
check("confirm -> 200", 200, s, b)
s, b = call("POST", f"/orders/{order_id}/prepare", mgr, {})
check("prepare -> 200", 200, s, b)
s, b = call("PUT", f"/orders/{order_id}/ready", mgr, {})
check("ready -> 200", 200, s, b)
s, b = call("POST", "/orders/collect", mgr,
            {"order_number": checkout["order_number"]})
check("collect -> 200", 200, s, b)
s, o = call("GET", f"/orders/{order_id}", fac)
check("order completed", "completed", (o or {}).get("status"), o if s != 200 else "")

print("\n=== 3. D7 live: cash refund settles manually ===")
s, refund = call("POST", f"/refunds?order_id={order_id}", fac,
                 {"amount": 34900, "reason": "item_unavailable",
                  "idempotency_key": "p8-task11-e2e-refund"})
check("refund request -> 201/200", True, s in (200, 201), refund)
rid = (refund or {}).get("id")
s, body = call("POST", f"/refunds/{rid}/process", login("admin@lgu.edu.pk", "Admin123!"), {})
check("process -> succeeded", "succeeded", (body or {}).get("status"), body)
check("manual_cash reference", True,
      str((body or {}).get("provider_reference", "")).startswith("manual_cash_"),
      (body or {}).get("provider_reference"))

print("\n=== 4. D8 live: stranger cannot learn order status via cancel ===")
s1, b1 = call("POST", f"/orders/{order_id}/cancel", stu, {"reason": "probe"})
s2, b2 = call("GET", f"/orders/{order_id}", stu)
check("stranger cancel == stranger GET (parity)", f"{s1}:{(b1 or {}).get('detail')}",
      f"{s2}:{(b2 or {}).get('detail')}", (s1, b1, s2, b2))
check("stranger denied with 403", 403, s1)

print("\n=== 5. Notifications created for the lifecycle ===")
s, notifs = call("GET", "/notifications", fac)
items = (notifs or {}).get("notifications", [])
check("faculty notifications returned", 200, s, len(items))

print()
passed = sum(1 for r in results if r)
print(f"TASK 11 E2E SMOKE: {passed}/{len(results)} passed")
