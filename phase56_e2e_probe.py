"""Phase 56 E2E — inventory upsert probe + role/scope API checks (fixture data only)."""
import json
import urllib.request

BASE = "http://localhost:8001/api/v1"
CAF = "50d67d4b-841b-43c4-b60d-eeb1cf68152a"
LASSI = "6bbfea95-d2ef-42cf-8925-1143ec19ef79"
SANDWICH = "c343f85d-99bb-47da-aaad-393ada85edd8"
PROBE = "75fd0527-f2eb-4d5f-9293-4bf7b86687ef"


def call(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def login(email, password):
    status, data = call("POST", "/auth/login", body={"university_email": email, "password": password})
    assert status == 200, f"login {email} -> {status} {data}"
    return data["tokens"]["access_token"]


admin = login("admin@lgu.edu.pk", "Admin123!")
staff = login("ahmed.raza@lgu.edu.pk", "TestPass123!")
student = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")

# --- Upsert (the exact endpoint the UI Add Item modal calls) on own fixture row
status, data = call("POST", f"/cafeterias/{CAF}/inventory/", admin,
                    {"menu_item_id": LASSI, "quantity": 20, "unit": "portions", "low_threshold": 5})
print(f"admin_upsert_lassi: status={status} qty={data.get('quantity') if isinstance(data, dict) else data} unit={data.get('unit') if isinstance(data, dict) else ''} thr={data.get('low_threshold') if isinstance(data, dict) else ''}")

status, inv = call("GET", f"/cafeterias/{CAF}/inventory/", admin)
rows = {r["menu_item_id"]: r for r in inv.get("inventory", inv if isinstance(inv, list) else [])} if isinstance(inv, (dict, list)) else {}
lassi = rows.get(LASSI)
print(f"inventory_after_upsert: rows={len(rows)} lassi_qty={lassi.get('quantity') if lassi else 'MISSING'} lassi_thr={lassi.get('low_threshold') if lassi else ''}")

# --- Re-upsert same values = idempotent (still one row for lassi)
status, data = call("POST", f"/cafeterias/{CAF}/inventory/", admin,
                    {"menu_item_id": LASSI, "quantity": 20, "unit": "portions", "low_threshold": 5})
print(f"idempotent_reupsert: status={status}")
status, inv = call("GET", f"/cafeterias/{CAF}/inventory/", admin)
rows2 = [r for r in (inv.get("inventory") or []) if r.get("menu_item_id") == LASSI] if isinstance(inv, dict) else []
print(f"lassi_row_count_after_reupsert: {len(rows2)}")

# --- Invalid unit rejected (validation surface used by the modal's dropdown values)
status, data = call("POST", f"/cafeterias/{CAF}/inventory/", admin,
                    {"menu_item_id": SANDWICH, "quantity": 1, "unit": "barrels", "low_threshold": 0})
print(f"invalid_unit: status={status} detail={str(data.get('detail', ''))[:90]}")

# --- RBAC probes (write scope = admin+manager; staff/student must be rejected)
status, data = call("POST", f"/cafeterias/{CAF}/inventory/", staff,
                    {"menu_item_id": SANDWICH, "quantity": 5, "unit": "portions", "low_threshold": 1})
print(f"staff_upsert: status={status} detail={str(data.get('detail', ''))[:80]}")
status, data = call("POST", f"/cafeterias/{CAF}/inventory/", student,
                    {"menu_item_id": SANDWICH, "quantity": 5, "unit": "portions", "low_threshold": 1})
print(f"student_upsert: status={status} detail={str(data.get('detail', ''))[:80]}")
status, data = call("POST", f"/cafeterias/{CAF}/daily-menus/copy", staff,
                    {"source_date": "2026-10-06", "target_date": "2026-10-09"})
print(f"staff_copy: status={status} detail={str(data.get('detail', ''))[:80]}")
status, data = call("POST", f"/cafeterias/{CAF}/daily-menus/copy", student,
                    {"source_date": "2026-10-06", "target_date": "2026-10-09"})
print(f"student_copy: status={status} detail={str(data.get('detail', ''))[:80]}")
status, data = call("DELETE", f"/cafeterias/{CAF}/menu-items/{PROBE}", staff)
print(f"staff_delete_item: status={status} detail={str(data.get('detail', ''))[:80]}")
status, data = call("DELETE", f"/cafeterias/{CAF}/menu-items/{PROBE}", student)
print(f"student_delete_item: status={status} detail={str(data.get('detail', ''))[:80]}")

# --- Cafeteria visibility filters (probe = inactive fixture)
status, data = call("GET", "/cafeterias/?is_active=false", admin)
names = [c.get("name") for c in (data.get("cafeterias") or [])] if isinstance(data, dict) else []
print(f"inactive_filter: status={status} count={len(names)} probe_present={'Phase 56 Inactive Probe' in names} names={names}")
status, data = call("GET", "/cafeterias/?is_active=true", admin)
names = [c.get("name") for c in (data.get("cafeterias") or [])] if isinstance(data, dict) else []
print(f"active_filter: status={status} count={len(names)} probe_present={'Phase 56 Inactive Probe' in names} e2e_present={'Phase 56 E2E Cafeteria' in names}")

print("PROBE_DONE")
