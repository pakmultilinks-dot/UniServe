#!/usr/bin/env python3
"""Phase 19 — Realistic UniServe Seed Data Generator.

Seeds the local dev environment with realistic cafeteria data:
- Test users (students, faculty, staff, managers, admin)
- Two cafeterias (Student + Faculty)
- 27 menu items with real food images and PKR prices
- Published daily menus for today
- Inventory records for all items
- Staff/manager cafeteria assignments

Run from repo root:
    python scripts/seed_realistic_data.py

All data is created via API endpoints (tests actual business logic).
Email verification bypassed via direct DB update (dev environment only).
"""

import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta

import httpx

BASE_URL = "http://localhost:8000/api/v1"
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_dev"
TIMEOUT = 30

# ── Test Account Definitions ─────────────────────────────────────────

PASSWORD = "TestPass123!"

USERS = [
    # (first_name, last_name, uni_id, email, role_hint)
    ("Ayesha", "Khan", "FA22-001", "ayesha.khan@student.lgu.edu.pk", "student"),
    ("Bilal", "Hussain", "FA22-002", "bilal.hussain@student.lgu.edu.pk", "student"),
    ("Fatima", "Raza", "FA23-003", "fatima.raza@student.lgu.edu.pk", "student"),
    ("Dr. Sana", "Malik", "FAC-101", "dr.sana.malik@lgu.edu.pk", "faculty"),
    ("Dr. Imran", "Chaudhry", "FAC-102", "dr.imran.chaudhry@lgu.edu.pk", "faculty"),
    ("Ahmed", "Raza", "STF-201", "ahmed.raza@lgu.edu.pk", "staff"),
    ("Sana", "Malik", "MGR-301", "sana.malik@lgu.edu.pk", "manager"),
]

ADMIN_EMAIL = "admin@lgu.edu.pk"
ADMIN_PASSWORD = "Admin123!"

# ── Cafeteria Definitions ────────────────────────────────────────────

CAFETERIAS = [
    {
        "name": "Student Cafeteria",
        "type": "student",
        "description": "Main cafeteria for students — burgers, wraps, snacks, and beverages",
        "phone": "+92-42-111-222-333",
        "email": "student.cafeteria@lgu.edu.pk",
        "location": "Block B, Ground Floor",
        "operating_hours": "08:00-22:00",
    },
    {
        "name": "Faculty Cafeteria",
        "type": "faculty",
        "description": "Premium cafeteria for faculty — biryani, karahi, traditional meals",
        "phone": "+92-42-111-444-555",
        "email": "faculty.cafeteria@lgu.edu.pk",
        "location": "Administration Block, 1st Floor",
        "operating_hours": "09:00-21:00",
    },
]

# ── Menu Item Definitions ────────────────────────────────────────────
# (cafeteria_index, name, description, category, price_pkr, image_filename, prep_minutes, stock_qty)

MENU_ITEMS = [
    # Student Cafeteria
    (0, "Chicken Burger",
     "Grilled chicken patty with lettuce, tomato, mayo, and pickles on a toasted bun",
     "main_course", 250, "chicken-burger.jpg", 12, 30),
    (0, "Zinger Burger",
     "Crispy fried chicken fillet with spicy zinger sauce, lettuce, and cheese",
     "main_course", 320, "zinger-burger.jpg", 15, 25),
    (0, "Chicken Shawarma",
     "Middle Eastern wrap with marinated chicken, garlic sauce, pickles, and fries",
     "snack", 200, "chicken-shawarma.jpg", 8, 40),
    (0, "Chicken Roll",
     "Flaky paratha rolled with spiced chicken, chutney, and onion rings",
     "snack", 150, "chicken-roll.jpg", 10, 35),
    (0, "French Fries",
     "Golden crispy potato fries with ketchup and salt",
     "side_dish", 120, "fries.jpg", 6, 50),
    (0, "Club Sandwich",
     "Triple-decker sandwich with chicken, egg, lettuce, tomato, and mayo",
     "main_course", 280, "club-sandwich.jpg", 10, 20),
    (0, "Chai",
     "Freshly brewed Pakistani milk tea with cardamom",
     "beverage", 50, "chai.jpg", 5, 100),
    (0, "Cold Drink",
     "Chilled soft drink — Coca-Cola, Pepsi, or Sprite (350ml)",
     "beverage", 80, "cold-drink.jpg", 2, 60),
    (0, "Water Bottle",
     "Mineral water bottle (500ml)",
     "beverage", 40, "water.jpg", 1, 80),
    (0, "Samosa (2 pcs)",
     "Crispy pastry triangles filled with spiced potato and peas",
     "snack", 60, "samosa.jpg", 8, 45),
    (0, "Paratha",
     "Flaky layered flatbread cooked on tawa with butter",
     "breakfast", 40, "paratha.jpg", 7, 70),
    (0, "Omelette",
     "Fluffy egg omelette with onions, green chilies, and herbs",
     "breakfast", 80, "omelette.jpg", 6, 30),
    (0, "Chicken Pizza Slice",
     "Oven-baked pizza slice with chicken tikka, mozzarella, and vegetables",
     "main_course", 220, "pizza-slice.jpg", 12, 25),
    (0, "Chicken Pakora",
     "Deep-fried chickpea-battered chicken pieces with mint chutney",
     "snack", 150, "chicken-pakora.jpg", 15, 35),
    (0, "Gulab Jamun (2 pcs)",
     "Soft milk dumplings soaked in rose-cardamom syrup",
     "dessert", 100, "gulab-jamun.jpg", 5, 40),

    # Faculty Cafeteria
    (1, "Chicken Biryani (Full)",
     "Fragrant basmati rice layered with spiced chicken, fried onions, and raita",
     "main_course", 450, "chicken-biryani.jpg", 20, 20),
    (1, "Chicken Pulao",
     "Aromatic rice cooked with chicken broth, whole spices, and herbs",
     "main_course", 350, "chicken-pulao.jpg", 18, 25),
    (1, "Chicken Karahi (Half)",
     "Slow-cooked chicken in tomato-based gravy with fresh ginger and green chilies",
     "main_course", 600, "chicken-karahi.jpg", 25, 15),
    (1, "Chicken Korma",
     "Creamy yogurt-based curry with tender chicken, cashews, and aromatic spices",
     "main_course", 400, "chicken-korma.jpg", 22, 20),
    (1, "Naan",
     "Soft tandoori bread baked in clay oven",
     "side_dish", 30, "naan.jpg", 8, 80),
    (1, "Raita",
     "Yogurt dip with cucumber, mint, and roasted cumin",
     "side_dish", 60, "raita.jpg", 3, 50),
    (1, "Fresh Juice",
     "Freshly squeezed seasonal juice — orange, mango, or pomegranate",
     "beverage", 150, "fresh-juice.jpg", 5, 40),
    (1, "Chocolate Cake Slice",
     "Rich chocolate layer cake with dark chocolate ganache",
     "dessert", 250, "chocolate-cake.jpg", 3, 20),
    (1, "Green Tea",
     "Organic green tea with honey and lemon",
     "beverage", 40, "green-tea.jpg", 4, 90),
    (1, "Chicken Shami Kebab (2 pcs)",
     "Slow-cooked lentil and chicken patties with mint chutney",
     "snack", 180, "chicken-shami-kebab.jpg", 12, 30),
    (1, "Daal",
     "Yellow lentil curry with cumin tadka and butter",
     "main_course", 200, "dal.jpg", 15, 35),
    (1, "Mixed Vegetable",
     "Seasonal vegetables cooked in aromatic spices with fresh herbs",
     "main_course", 220, "mixed-veg.jpg", 18, 30),
]

# ── Helpers ──────────────────────────────────────────────────────────

def log(msg):
    print(f"  {msg}")


def db_verify_user(user_id):
    """Mark user as email-verified via direct DB (dev only)."""
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET email_verified = true, status = 'active' "
        f"WHERE id = '{user_id}' AND email_verified = false;\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


def register_user(first_name, last_name, uni_id, email, password):
    """Register a user and auto-verify via DB."""
    body = {
        "first_name": first_name,
        "last_name": last_name,
        "university_id": uni_id,
        "university_email": email,
        "password": password,
    }
    r = httpx.post(f"{BASE_URL}/auth/register", json=body, timeout=TIMEOUT)
    if r.status_code == 201:
        user_id = r.json().get("user_id")
        if user_id and db_verify_user(user_id):
            return user_id
    elif r.status_code == 409:
        # Already exists — find user_id by logging in later
        return "exists"
    return None


def login(email, password):
    """Login and return access token."""
    r = httpx.post(f"{BASE_URL}/auth/login", json={
        "university_email": email,
        "password": password,
    }, timeout=TIMEOUT)
    if r.status_code == 200:
        return r.json()["tokens"]["access_token"]
    return None


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_admin_user():
    """Create admin user — register via API, promote role via SQL."""
    # Register via API (or skip if exists)
    user_id = register_user("System", "Administrator", "ADM-001", ADMIN_EMAIL, ADMIN_PASSWORD)
    if not user_id:
        print("  ERROR: Could not create admin user")
        return None

    # Get user_id from DB
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -c "
        f"\"SELECT id FROM users WHERE university_email = '{ADMIN_EMAIL}';\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    user_id = result.stdout.strip()

    # Promote to university_admin + ensure verified/active
    subprocess.run(
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET role = 'university_admin', email_verified = true, status = 'active' "
        f"WHERE id = '{user_id}';\"",
        shell=True, capture_output=True, text=True, timeout=10
    )
    log(f"Admin role assigned: {user_id}")
    return user_id


# ── Main Seed Logic ──────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("UniServe — Phase 19 Realistic Data Seed")
    print("=" * 60)

    # ── Step 1: Create admin user ──
    print("\n[1/7] Creating admin user...")
    admin_id = create_admin_user()
    if not admin_id:
        print("FATAL: Could not create admin user")
        sys.exit(1)
    log(f"Admin user_id: {admin_id}")

    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        print("FATAL: Could not login as admin")
        sys.exit(1)
    log("Admin login: OK")

    # ── Step 2: Register test users ──
    print("\n[2/7] Registering test users...")
    user_tokens = {}
    for fname, lname, uid, email, role in USERS:
        result = register_user(fname, lname, uid, email, PASSWORD)
        if result and result != "exists":
            log(f"Registered: {email} ({role})")
        elif result == "exists":
            log(f"Already exists: {email}")
        else:
            log(f"FAILED: {email}")

        # Fix category/role for staff and manager accounts via SQL
        # (email patterns auto-classify them as faculty)
        if role == "staff":
            subprocess.run(
                f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
                f"\"UPDATE users SET role = 'cafeteria_staff' WHERE university_email = '{email}';\"",
                shell=True, capture_output=True, text=True, timeout=10
            )
        elif role == "manager":
            subprocess.run(
                f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
                f"\"UPDATE users SET role = 'cafeteria_manager' WHERE university_email = '{email}';\"",
                shell=True, capture_output=True, text=True, timeout=10
            )

        token = login(email, PASSWORD)
        if token:
            user_tokens[email] = token
        else:
            log(f"  Login failed for {email}")

    log(f"Total logged-in users: {len(user_tokens)}")

    # ── Step 3: Create cafeterias ──
    print("\n[3/7] Creating cafeterias...")
    cafeteria_ids = []

    # Check existing cafeterias first
    r = httpx.get(f"{BASE_URL}/cafeterias/", headers=auth(admin_token), timeout=TIMEOUT)
    existing = {}
    if r.status_code == 200:
        for c in r.json().get("cafeterias", []):
            existing[c["name"]] = c["id"]

    for caf in CAFETERIAS:
        if caf["name"] in existing:
            cid = existing[caf["name"]]
            log(f"Already exists: {caf['name']} (id={cid})")
        else:
            r = httpx.post(f"{BASE_URL}/cafeterias/", json=caf, headers=auth(admin_token), timeout=TIMEOUT)
            if r.status_code in (200, 201):
                cid = r.json()["id"]
                log(f"Created: {caf['name']} (id={cid})")
            else:
                log(f"FAILED to create {caf['name']}: {r.status_code} {r.text[:200]}")
                continue
        cafeteria_ids.append(cid)

    if len(cafeteria_ids) < 2:
        print("FATAL: Need both cafeterias")
        sys.exit(1)

    # ── Step 4: Create menu items ──
    print("\n[4/7] Creating menu items with food images...")
    menu_item_map = {}  # (cafeteria_idx, item_name) -> menu_item_id

    for caf_idx, name, desc, category, price, image_file, prep_min, stock_qty in MENU_ITEMS:
        cid = cafeteria_ids[caf_idx]

        # Build image URL pointing to our local static files
        image_url = f"http://localhost:8000/api/v1/static/food/{image_file}"

        payload = {
            "name": name,
            "description": desc,
            "category": category,
            "price": price * 100,  # Convert PKR to paisa
            "currency": "PKR",
            "image_url": image_url,
            "preparation_time_minutes": prep_min,
        }

        r = httpx.post(
            f"{BASE_URL}/cafeterias/{cid}/menu-items/",
            json=payload,
            headers=auth(admin_token),
            timeout=TIMEOUT,
        )
        if r.status_code in (200, 201):
            item_id = r.json()["id"]
            menu_item_map[(caf_idx, name)] = item_id
            log(f"Created: {name} (Rs {price}) -> {image_file}")
        else:
            log(f"FAILED: {name}: {r.status_code} {r.text[:150]}")

    log(f"Total menu items created: {len(menu_item_map)}")

    # ── Step 5: Create & publish daily menus ──
    print("\n[5/7] Creating and publishing daily menus for today...")
    today = date.today().isoformat()

    for caf_idx, cid in enumerate(cafeteria_ids):
        # Create daily menu
        r = httpx.post(
            f"{BASE_URL}/cafeterias/{cid}/daily-menus/",
            json={"menu_date": today},
            headers=auth(admin_token),
            timeout=TIMEOUT,
        )
        if r.status_code in (200, 201):
            dm_id = r.json()["id"]
            log(f"Daily menu created for cafeteria {caf_idx}: {dm_id}")
        elif r.status_code == 409:
            # Already exists — find it
            r2 = httpx.get(
                f"{BASE_URL}/cafeterias/{cid}/daily-menus/today",
                headers=auth(admin_token),
                timeout=TIMEOUT,
            )
            if r2.status_code == 200:
                dm_id = r2.json()["id"]
                log(f"Daily menu already exists: {dm_id}")
            else:
                log(f"Could not find daily menu for cafeteria {caf_idx}")
                continue
        else:
            log(f"FAILED to create daily menu: {r.status_code} {r.text[:150]}")
            continue

        # Add all items for this cafeteria to the daily menu
        display_order = 0
        for (mi_caf, mi_name), mi_id in menu_item_map.items():
            if mi_caf != caf_idx:
                continue
            r = httpx.post(
                f"{BASE_URL}/cafeterias/{cid}/daily-menus/{dm_id}/items",
                json={
                    "menu_item_id": mi_id,
                    "is_available_today": True,
                    "display_order": display_order,
                },
                headers=auth(admin_token),
                timeout=TIMEOUT,
            )
            if r.status_code in (200, 201):
                display_order += 1
            else:
                log(f"  Failed to add {mi_name} to daily menu: {r.status_code}")

        # Publish the daily menu
        r = httpx.patch(
            f"{BASE_URL}/cafeterias/{cid}/daily-menus/{dm_id}/publish",
            headers=auth(admin_token),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            log(f"Published daily menu for cafeteria {caf_idx} ({display_order} items)")
        else:
            log(f"FAILED to publish daily menu: {r.status_code} {r.text[:150]}")

    # ── Step 6: Add inventory ──
    print("\n[6/7] Adding inventory records...")
    inv_count = 0
    for (caf_idx, name), mi_id in menu_item_map.items():
        # Find stock_qty from MENU_ITEMS
        stock_qty = 30  # default
        for item in MENU_ITEMS:
            if item[0] == caf_idx and item[1] == name:
                stock_qty = item[7]
                break

        cid = cafeteria_ids[caf_idx]
        r = httpx.post(
            f"{BASE_URL}/cafeterias/{cid}/inventory/",
            json={
                "menu_item_id": mi_id,
                "quantity": stock_qty,
                "unit": "portions",
                "low_threshold": max(5, stock_qty // 5),
            },
            headers=auth(admin_token),
            timeout=TIMEOUT,
        )
        if r.status_code in (200, 201):
            inv_count += 1
        else:
            log(f"  Inv failed for {name}: {r.status_code}")

    log(f"Inventory records created: {inv_count}")

    # ── Step 7: Assign staff/managers via SQL (no API endpoint exists) ──
    print("\n[7/7] Assigning staff and managers to cafeterias...")

    # Get user IDs for staff/manager
    staff_map = {
        "ahmed.raza@lgu.edu.pk": (0, "cafeteria_staff"),   # Student Cafeteria
        "sana.malik@lgu.edu.pk": (1, "cafeteria_manager"),  # Faculty Cafeteria
    }
    for email, (caf_idx, assign_role) in staff_map.items():
        # Get user_id from DB
        cmd = (
            f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -c "
            f"\"SELECT id FROM users WHERE university_email = '{email}';\""
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        user_id = result.stdout.strip()
        if not user_id:
            log(f"No user_id for {email}")
            continue

        cid = cafeteria_ids[caf_idx]
        caf_name = CAFETERIAS[caf_idx]["name"]

        # Insert assignment via SQL
        assign_sql = (
            f"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
            f"VALUES (gen_random_uuid(), '{user_id}', '{cid}', '{assign_role}', now()) "
            f"ON CONFLICT DO NOTHING;"
        )
        r = subprocess.run(
            f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c \"{assign_sql}\"",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            log(f"Assigned {email} -> {caf_name} ({assign_role})")
        else:
            log(f"Assignment failed for {email}: {r.stderr.strip()[:100]}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SEED COMPLETE")
    print("=" * 60)
    print(f"  Users registered:     {len(USERS)}")
    print(f"  Cafeterias:           {len(cafeteria_ids)}")
    print(f"  Menu items:           {len(menu_item_map)}")
    print(f"  Inventory records:    {inv_count}")
    print(f"  Daily menus published: {len(cafeteria_ids)}")
    print()
    print("Test accounts (password: TestPass123!):")
    for fname, lname, uid, email, role in USERS:
        print(f"  {role:8s}  {email}")
    print(f"  admin    {ADMIN_EMAIL} (password: {ADMIN_PASSWORD})")
    print()
    print(f"Food images: http://localhost:8000/api/v1/static/food/")
    print("=" * 60)


if __name__ == "__main__":
    main()
