import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:8001/api/v1"

def call(method, path, token=None, body=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")

s, t = call("POST", "/auth/login", body={"university_email": "admin@lgu.edu.pk", "password": "Admin123!"})
tok = (t.get("tokens") or {}).get("access_token") or t.get("access_token")
print("login", s, "token?", bool(tok))

s, r = call(
    "POST",
    "/cafeterias/c84affd5-16bf-47bc-b50c-c54f4442f408/inventory/adjust",
    token=tok,
    body={
        "inventory_item_id": "9031b184-2a15-43fd-9bde-c6b708185b19",
        "adjustment_quantity": 50,
        "reason": "Phase 8 E2E restock",
    },
)
print("adjust", s, json.dumps(r)[:500])

s, r = call("GET", "/cafeterias/c84affd5-16bf-47bc-b50c-c54f4442f408/inventory", token=tok)
items = [i for i in r.get("items", []) if i.get("menu_item_id") == "9031b184-2a15-43fd-9bde-c6b708185b19"] if isinstance(r, dict) else r
print("verify_inventory", s, json.dumps(items)[:400])
