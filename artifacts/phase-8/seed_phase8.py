#!/usr/bin/env python3
"""Phase 8 — Isolated E2E seed (targets uniserve_test_phase7 via :8001 ONLY).

Reuses the Phase 19 seed's data + helpers but:
  * Points all API calls at the isolated API (127.0.0.1:8001).
  * Points all DB verify/role/assignment SQL at uniserve_test_phase7.
  * Stores host-independent image paths (/api/v1/static/food/<file>) so both
    web and mobile resolvers attach their own configured API origin.

Never touches uniserve_prod. Run from repo root with the isolated API up on :8001.
"""
import sys
import subprocess
from datetime import date

import httpx

sys.path.insert(0, "scripts")
import seed_realistic_data as base  # reuse data tables + helpers

REPO = "C:/Users/Lenovo/Documents/Code_PlayGround/UniServe"
BASE_URL = "http://127.0.0.1:8001/api/v1"
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_test_phase7"  # isolated
TIMEOUT = 30

# Re-point the imported module's globals so its helpers hit the isolated env.
base.BASE_URL = BASE_URL
base.PG_DB = PG_DB


def log(msg):
    print(f"  {msg}")


def psql(sql, read=False):
    cmd = f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} " + ("-t -c " if read else "-c ") + f"\"{sql}\""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)


def ensure_verified_active(email):
    psql(f"UPDATE users SET email_verified=true, status='active' WHERE university_email='{email}';")


def main():
    print("=" * 64)
    print("UniServe — Phase 8 ISOLATED E2E Seed (uniserve_test_phase7 @ :8001)")
    print("=" * 64)

    # Guard: refuse to run if BASE_URL somehow isn't the isolated port.
    assert ":8001" in BASE_URL, "Refusing to seed a non-isolated API."
    assert PG_DB == "uniserve_test_phase7", "Refusing to seed a non-isolated DB."

    # ── 1. Admin user ──
    print("\n[1/7] Creating admin user (university_admin)...")
    admin_id = base.create_admin_user()
    if not admin_id:
        print("FATAL: admin user")
        sys.exit(1)
    ensure_verified_active(base.ADMIN_EMAIL)
    admin_token = base.login(base.ADMIN_EMAIL, base.ADMIN_PASSWORD)
    if not admin_token:
        print("FATAL: admin login")
        sys.exit(1)
    log("Admin login OK")

    # ── 2. Test users ──
    print("\n[2/7] Registering test users...")
    user_tokens = {}
    for fname, lname, uid, email, role in base.USERS:
        res = base.register_user(fname, lname, uid, email, base.PASSWORD)
        ensure_verified_active(email)
        if role == "staff":
            psql(f"UPDATE users SET role='cafeteria_staff' WHERE university_email='{email}';")
        elif role == "manager":
            psql(f"UPDATE users SET role='cafeteria_manager' WHERE university_email='{email}';")
        tok = base.login(email, base.PASSWORD)
        if tok:
            user_tokens[email] = tok
            log(f"OK {email} ({role})")
        else:
            log(f"LOGIN FAILED {email}")
    log(f"Logged-in users: {len(user_tokens)}")

    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    # ── 3. Cafeterias ──
    print("\n[3/7] Creating cafeterias...")
    r = httpx.get(f"{BASE_URL}/cafeterias/", headers=auth(admin_token), timeout=TIMEOUT)
    existing = {c["name"]: c["id"] for c in (r.json().get("cafeterias", []) if r.status_code == 200 else [])}
    cafeteria_ids = []
    for caf in base.CAFETERIAS:
        if caf["name"] in existing:
            cid = existing[caf["name"]]
            log(f"Exists {caf['name']} ({cid})")
        else:
            rr = httpx.post(f"{BASE_URL}/cafeterias/", json=caf, headers=auth(admin_token), timeout=TIMEOUT)
            if rr.status_code in (200, 201):
                cid = rr.json()["id"]
                log(f"Created {caf['name']} ({cid})")
            else:
                log(f"FAILED {caf['name']}: {rr.status_code} {rr.text[:150]}")
                continue
        cafeteria_ids.append(cid)
    if len(cafeteria_ids) < 2:
        print("FATAL: need both cafeterias")
        sys.exit(1)

    # ── 4. Menu items (host-independent image paths) ──
    print("\n[4/7] Creating menu items...")
    menu_item_map = {}
    for caf_idx, name, desc, category, price, image_file, prep_min, stock_qty in base.MENU_ITEMS:
        cid = cafeteria_ids[caf_idx]
        payload = {
            "name": name,
            "description": desc,
            "category": category,
            "price": price * 100,  # PKR -> paisa
            "currency": "PKR",
            "image_url": f"/api/v1/static/food/{image_file}",  # host-independent
            "preparation_time_minutes": prep_min,
        }
        rr = httpx.post(f"{BASE_URL}/cafeterias/{cid}/menu-items/", json=payload,
                        headers=auth(admin_token), timeout=TIMEOUT)
        if rr.status_code in (200, 201):
            menu_item_map[(caf_idx, name)] = rr.json()["id"]
        else:
            log(f"FAILED {name}: {rr.status_code} {rr.text[:120]}")
    log(f"Menu items: {len(menu_item_map)}")

    # ── 5. Daily menus published ──
    print("\n[5/7] Creating + publishing daily menus...")
    today = date.today().isoformat()
    for caf_idx, cid in enumerate(cafeteria_ids):
        rr = httpx.post(f"{BASE_URL}/cafeterias/{cid}/daily-menus/", json={"menu_date": today},
                        headers=auth(admin_token), timeout=TIMEOUT)
        if rr.status_code in (200, 201):
            dm_id = rr.json()["id"]
        elif rr.status_code == 409:
            r2 = httpx.get(f"{BASE_URL}/cafeterias/{cid}/daily-menus/today",
                           headers=auth(admin_token), timeout=TIMEOUT)
            dm_id = r2.json()["id"]
        else:
            log(f"daily-menu failed caf{caf_idx}: {rr.status_code} {rr.text[:120]}")
            continue
        order = 0
        for (mi_caf, mi_name), mi_id in menu_item_map.items():
            if mi_caf != caf_idx:
                continue
            r3 = httpx.post(f"{BASE_URL}/cafeterias/{cid}/daily-menus/{dm_id}/items",
                            json={"menu_item_id": mi_id, "is_available_today": True, "display_order": order},
                            headers=auth(admin_token), timeout=TIMEOUT)
            if r3.status_code in (200, 201):
                order += 1
        r4 = httpx.patch(f"{BASE_URL}/cafeterias/{cid}/daily-menus/{dm_id}/publish",
                         headers=auth(admin_token), timeout=TIMEOUT)
        log(f"caf{caf_idx} daily-menu {dm_id} published={r4.status_code == 200} items={order}")

    # ── 6. Inventory ──
    print("\n[6/7] Adding inventory...")
    inv = 0
    for (caf_idx, name), mi_id in menu_item_map.items():
        stock = next((it[7] for it in base.MENU_ITEMS if it[0] == caf_idx and it[1] == name), 30)
        cid = cafeteria_ids[caf_idx]
        rr = httpx.post(f"{BASE_URL}/cafeterias/{cid}/inventory/",
                        json={"menu_item_id": mi_id, "quantity": stock, "unit": "portions",
                              "low_threshold": max(5, stock // 5)},
                        headers=auth(admin_token), timeout=TIMEOUT)
        if rr.status_code in (200, 201):
            inv += 1
    log(f"Inventory: {inv}")

    # ── 7. Staff/manager assignments ──
    print("\n[7/7] Assigning staff/managers...")
    staff_map = {
        "ahmed.raza@lgu.edu.pk": (0, "cafeteria_staff"),
        "sana.malik@lgu.edu.pk": (1, "cafeteria_manager"),
    }
    for email, (caf_idx, arole) in staff_map.items():
        rr = psql(f"SELECT id FROM users WHERE university_email='{email}';", read=True)
        uid = rr.stdout.strip()
        cid = cafeteria_ids[caf_idx]
        if uid:
            psql(f"INSERT INTO cafeteria_assignments (id,user_id,cafeteria_id,role,created_at) "
                 f"VALUES (gen_random_uuid(),'{uid}','{cid}','{arole}',now()) ON CONFLICT DO NOTHING;")
            log(f"Assigned {email} -> caf{caf_idx} ({arole})")

    print("\n" + "=" * 64)
    print("PHASE 8 ISOLATED SEED COMPLETE")
    print("=" * 64)
    print(f"  Cafeterias: {len(cafeteria_ids)}")
    print(f"  Menu items: {len(menu_item_map)}")
    print(f"  Inventory:  {inv}")
    print(f"  Users:      {len(user_tokens)} + admin")
    print(f"  Admin:      {base.ADMIN_EMAIL}")
    print(f"  Users pw:   {base.PASSWORD}")
    print(f"  Cafeteria ids: {cafeteria_ids}")
    print("=" * 64)


if __name__ == "__main__":
    main()
