"""Phase 56 — E2E fixture setup (menu & inventory ergonomics).

Creates ONLY clearly-labeled "Phase 56 ..." test data via the live API:
  1. "Phase 56 E2E Cafeteria" (active, type=student)
  2. Three tagged menu items (dietary_info / allergens JSON strings)
  3. Yesterday's published daily menu (copy source, with junction metadata)
  4. Today's published daily menu (occupied target for the 409 conflict test)
  5. "Phase 56 Inactive Probe" cafeteria (created active, then deactivated —
     existing cafeterias are NEVER deactivated; only this new probe is)

Idempotent: reuses any fixture that already exists. Never touches
pre-existing rows. Prints all IDs + verification state.
"""
import datetime
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8001/api/v1"


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {method} {path}: {e.read().decode()[:500]}")
        raise


def main():
    login = req("POST", "/auth/login", body={
        "university_email": "admin@lgu.edu.pk", "password": "Admin123!",
    })
    tok = login["tokens"]["access_token"]
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    today_s, yesterday_s = today.isoformat(), yesterday.isoformat()
    print(f"today={today_s} yesterday={yesterday_s}")

    # ── Cafeterias ────────────────────────────────────────────────
    cafes = req("GET", "/cafeterias/", tok)["cafeterias"]
    by_name = {c["name"]: c for c in cafes}

    e2e = by_name.get("Phase 56 E2E Cafeteria")
    if not e2e:
        e2e = req("POST", "/cafeterias/", tok, {
            "name": "Phase 56 E2E Cafeteria",
            "type": "student",
            "description": "Phase 56 menu & inventory ergonomics test cafeteria",
        })
    cid = e2e["id"]
    print(f"e2e_cafeteria={cid} active={e2e.get('is_active')}")

    inactive = by_name.get("Phase 56 Inactive Probe")
    if not inactive:
        inactive = req("POST", "/cafeterias/", tok, {
            "name": "Phase 56 Inactive Probe",
            "type": "student",
            "description": "Phase 56 inactive-cafeteria filter probe (no orders)",
        })
    if inactive.get("is_active", True):
        inactive = req("PUT", f"/cafeterias/{inactive['id']}", tok, {"is_active": False})
    print(f"inactive_probe={inactive['id']} active={inactive.get('is_active')}")

    # ── Menu items (tagged) ───────────────────────────────────────
    existing = {i["name"]: i for i in req("GET", f"/cafeterias/{cid}/menu-items", tok)["items"]}

    def get_or_create_item(name, payload):
        if name in existing:
            return existing[name]
        item = req("POST", f"/cafeterias/{cid}/menu-items/", tok, payload)
        print(f"created_item={item['id']} {name}")
        return item

    i1 = get_or_create_item("Phase 56 Grilled Sandwich", {
        "name": "Phase 56 Grilled Sandwich", "category": "main_course",
        "price": 25000, "dietary_info": '["vegetarian"]',
        "allergens": '["wheat","milk"]', "preparation_time_minutes": 10,
        "description": "E2E item A (copy source)",
    })
    i2 = get_or_create_item("Phase 56 Mango Lassi", {
        "name": "Phase 56 Mango Lassi", "category": "beverage",
        "price": 18000, "dietary_info": '["vegetarian","gluten_free"]',
        "allergens": '["milk"]', "preparation_time_minutes": 5,
        "description": "E2E item B (copy source)",
    })
    i3 = get_or_create_item("Phase 56 Delete Probe", {
        "name": "Phase 56 Delete Probe", "category": "snack",
        "price": 12000, "dietary_info": '["vegan"]',
        "preparation_time_minutes": 5,
        "description": "Soft-delete probe (Phase 56 C)",
    })
    print(f"item1={i1['id']} item2={i2['id']} item3={i3['id']}")

    # ── Daily menus ───────────────────────────────────────────────
    menus = req("GET", f"/cafeterias/{cid}/daily-menus", tok)["menus"]

    def ensure_menu(date_s, label, want_published):
        for m in menus:
            if m["menu_date"] == date_s and m["status"] != "archived":
                print(f"{label}_menu_exists={m['id']} status={m['status']}")
                return m
        m = req("POST", f"/cafeterias/{cid}/daily-menus/", tok, {"menu_date": date_s})
        mid = m["id"]
        req("POST", f"/cafeterias/{cid}/daily-menus/{mid}/items", tok,
            {"menu_item_id": i1["id"], "special_price": 23000, "display_order": 1, "is_available_today": True})
        req("POST", f"/cafeterias/{cid}/daily-menus/{mid}/items", tok,
            {"menu_item_id": i2["id"], "display_order": 2, "is_available_today": True})
        req("POST", f"/cafeterias/{cid}/daily-menus/{mid}/items", tok,
            {"menu_item_id": i3["id"], "display_order": 3, "is_available_today": False})
        if want_published:
            req("PATCH", f"/cafeterias/{cid}/daily-menus/{mid}/publish", tok)
        print(f"created_{label}_menu={mid} date={date_s} published={want_published}")
        return req("GET", f"/cafeterias/{cid}/daily-menus/{mid}", tok)

    src = ensure_menu(yesterday_s, "source", True)
    tgt = ensure_menu(today_s, "today", True)
    src_items = src.get("items", [])
    print(f"source_menu={src['id']} status={src['status']} items={len(src_items)} "
          f"metadata={[ (x['menu_item_id'][:8], x.get('special_price'), x['display_order'], x['is_available_today']) for x in src_items ]}")
    print(f"today_menu={tgt['id']} status={tgt['status']}")

    # ── Verification probes ───────────────────────────────────────
    act = [c["name"] for c in req("GET", "/cafeterias/?is_active=true", tok)["cafeterias"]]
    allc = [c["name"] for c in req("GET", "/cafeterias/", tok)["cafeterias"]]
    print(f"active_filter_excludes_probe={'Phase 56 Inactive Probe' not in act}")
    print(f"all_list_includes_probe={'Phase 56 Inactive Probe' in allc}")
    print("SETUP_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"SETUP_FAILED: {exc}")
        sys.exit(1)
