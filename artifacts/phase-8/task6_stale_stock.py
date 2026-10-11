"""Phase 8 — Task 6: stale-stock / cart validation (focused re-run).

Inventory list is manager-scoped; the cart add is attempted as faculty.
Isolated API only (127.0.0.1:8001 / uniserve_test_phase7).
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
CAF = "c84affd5-16bf-47bc-b50c-c54f4442f408"
ITEM = "5d33b252-ec7d-4cf1-bc28-db366e7cdec8"


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
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except Exception:
            return e.code, raw[:200]


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    return ((t.get("tokens") or {}).get("access_token")) if s == 200 else None


mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")

results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {detail}")


# 1. Inventory read as manager (write scope) — faculty should be 403
s, inv = call("GET", f"/cafeterias/{CAF}/inventory", mgr)
print("manager inventory list:", s)
avail = None
if s == 200:
    rows = inv.get("items") if isinstance(inv, dict) else inv
    for row in rows or []:
        if row.get("menu_item_id") == ITEM:
            avail = row.get("quantity")
check("manager can read inventory", s == 200, f"status={s} available={avail}")

s2, _ = call("GET", f"/cafeterias/{CAF}/inventory", fac)
check("faculty FORBIDDEN from inventory list", s2 == 403, f"status={s2}")
s3, _ = call("GET", f"/cafeterias/{CAF}/inventory", stu)
check("student FORBIDDEN from inventory list", s3 == 403, f"status={s3}")

if avail is not None:
    # 2. Stale stock — add more than available as faculty (cart add path)
    s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                {"menu_item_id": ITEM, "quantity": avail + 5})
    detail = r.get("detail") if isinstance(r, dict) else str(r)[:120]
    check("cart add qty>stock rejected 400", s == 400, f"status={s} detail={detail}")

    # 3. Exactly available should succeed, then we remove it
    s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                {"menu_item_id": ITEM, "quantity": 1})
    check("cart add qty=1 accepted", s == 201, f"status={s}")
    if s == 201:
        cid = r.get("id")
        s, rr = call("DELETE", f"/cafeterias/{CAF}/cart/items/{cid}", fac)
        check("cleanup cart line removed", s == 204, f"status={s}")

    # 4. Zero / negative quantity validation
    s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                {"menu_item_id": ITEM, "quantity": 0})
    check("cart add qty=0 rejected", s in (400, 422), f"status={s}")
    s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                {"menu_item_id": ITEM, "quantity": -3})
    check("cart add qty<0 rejected", s in (400, 422), f"status={s}")

    # 5. Unknown menu item
    s, r = call("POST", f"/cafeterias/{CAF}/cart/items", fac,
                {"menu_item_id": "00000000-0000-0000-0000-000000000000", "quantity": 1})
    check("cart add unknown item rejected", s in (400, 404, 422), f"status={s}")

print(f"\n{sum(1 for _, ok, _ in results if ok)}/{len(results)} passed")
