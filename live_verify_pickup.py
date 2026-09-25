"""Phase 12 Live Verification — automatic pickup expiry and no-show processing.

Runs against the live API server at http://127.0.0.1:8001 with real PostgreSQL.
Tests 9 scenarios proving the automatic mechanism works end-to-end.

CRITICAL CONSTRAINTS:
- Do NOT call mark_uncollected() directly
- Do NOT manually update the order to Uncollected in PostgreSQL
- Do NOT manually create the NoShow record
- The purpose of this script is to prove the AUTOMATIC mechanism

Prerequisites:
- Docker: uniserve_postgres container running on port 5433
- Server: uvicorn running on http://127.0.0.1:8001
"""

import httpx
import subprocess
import sys
import time
import uuid

BASE_URL = "http://127.0.0.1:8001/api/v1"
FOLLOW_REDIRECTS = True
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_dev"
PICKUP_WINDOW_SECONDS = 1810  # slightly more than 30 minutes for testing


# ── Helpers ──────────────────────────────────────────────────────────

def unique_id():
    return uuid.uuid4().hex[:8]


def sql(query):
    """Execute a SQL query against the PostgreSQL container."""
    cmd = f'docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -A -c "{query}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def verify_user_via_db(user_id):
    """Mark a user as email-verified in the dev database (dev environment only)."""
    cmd = (
        f'docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c '
        f'"UPDATE users SET email_verified = true, status = \'active\' '
        f'WHERE id = \'{user_id}\' AND email_verified = false;"'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


def register_and_verify(first_name, last_name, uni_id, email, password, category=None):
    """Register a user and auto-verify email via DB."""
    body = {
        "first_name": first_name,
        "last_name": last_name,
        "university_id": uni_id,
        "university_email": email,
        "password": password,
    }
    if category:
        body["selected_category"] = category
    r = httpx.post(
        f"{BASE_URL}/auth/register", json=body, timeout=30, follow_redirects=FOLLOW_REDIRECTS
    )
    if r.status_code != 201:
        print(f"    Registration failed: {r.status_code} {r.text[:200]}")
        return None

    resp = r.json()
    user_id = resp.get("user_id")
    if not user_id:
        print(f"    No user_id in response: {resp}")
        return None

    # Auto-verify via DB
    verify_user_via_db(user_id)
    return user_id


def login(email, password):
    """Login and return access token."""
    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": email, "password": password},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code != 200:
        print(f"    Login failed: {r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    # Handle nested token structure: {"tokens": {"access_token": "..."}} or flat
    tokens = data.get("tokens", data)
    return tokens.get("access_token") or tokens.get("token") or data.get("access_token") or data.get("token")


def register_admin():
    """Register admin user and return (token, user_id).

    Sets up the user as university_admin first (for cafeteria creation),
    then upgrades to cafeteria_manager after cafeteria is created.
    Returns token with university_admin role; caller must call
    setup_admin_for_cafeteria() after creating a cafeteria.
    """
    uid = unique_id()
    body = {
        "first_name": "Admin",
        "last_name": "User",
        "university_id": f"ADMIN-{uid}",
        "university_email": f"admin-{uid}@lgu.edu.pk",
        "password": "AdminPass123!",
    }
    r = httpx.post(
        f"{BASE_URL}/auth/register", json=body, timeout=30, follow_redirects=FOLLOW_REDIRECTS
    )
    if r.status_code != 201:
        print(f"    Admin registration failed: {r.status_code}")
        return None, None

    resp = r.json()
    user_id = resp.get("user_id")
    email = body["university_email"]
    verify_user_via_db(user_id)

    # Promote to university_admin via DB
    sql(f"UPDATE users SET role = 'university_admin' WHERE id = '{user_id}'")

    token = login(email, body["password"])
    return token, user_id


def setup_admin_for_cafeteria(user_id, cafeteria_id):
    """After cafeteria creation, upgrade admin to cafeteria_manager + assign."""
    # Create CafeteriaAssignment
    assignment_id = str(uuid.uuid4())
    sql(
        f"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
        f"VALUES ('{assignment_id}', '{user_id}', '{cafeteria_id}', 'cafeteria_manager', "
        f"NOW())"
    )
    # Update role to cafeteria_manager for order ops
    sql(f"UPDATE users SET role = 'cafeteria_manager' WHERE id = '{user_id}'")


def register_student(name_suffix=""):
    """Register a student user and return (token, user_id, email)."""
    uid = unique_id()
    body = {
        "first_name": f"Student{name_suffix}",
        "last_name": "Test",
        "university_id": f"STU-{uid}",
        "university_email": f"fa23-{uid}@lgu.edu.pk",
        "password": "StudentPass123!",
        "selected_category": "student",
    }
    r = httpx.post(
        f"{BASE_URL}/auth/register", json=body, timeout=30, follow_redirects=FOLLOW_REDIRECTS
    )
    if r.status_code != 201:
        print(f"    Student registration failed: {r.status_code}")
        return None, None, None

    resp = r.json()
    user_id = resp.get("user_id")
    email = body["university_email"]
    verify_user_via_db(user_id)

    token = login(email, body["password"])
    return token, user_id, email


def create_cafeteria(token, name="Test Cafeteria"):
    """Create a cafeteria and return its ID."""
    r = httpx.post(
        f"{BASE_URL}/cafeterias",
        json={
            "name": name,
            "type": "student",
            "location": "Building A",
            "timezone": "Asia/Karachi",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create cafeteria failed: {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("id")


def create_menu_item(token, cafeteria_id):
    """Create a menu item and return its ID."""
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/menu-items",
        json={
            "name": f"Item-{unique_id()}",
            "description": "Test item",
            "price": 15000,
            "currency": "PKR",
            "category": "main_course",
            "is_available": True,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create menu item failed: {r.status_code} {r.text[:200]}")
        return None
    menu_item_id = r.json().get("id")

    # Create inventory record for the menu item (required for checkout)
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/inventory",
        json={
            "menu_item_id": menu_item_id,
            "quantity": 100,
            "unit": "portions",
            "low_threshold": 5,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create inventory record failed: {r.status_code} {r.text[:200]}")
        return None

    return menu_item_id


def create_and_publish_daily_menu(token, cafeteria_id, menu_item_id):
    """Create a daily menu for today, add the item, and publish it.

    Checkout requires a published daily menu for the current date.
    Returns daily_menu_id or None on failure.
    """
    from datetime import date as date_type

    today = date_type.today().isoformat()

    # 1. Create daily menu draft
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus",
        json={"menu_date": today},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create daily menu failed: {r.status_code} {r.text[:200]}")
        return None
    daily_menu_id = r.json().get("id")

    # 2. Add menu item to the daily menu
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/items",
        json={"menu_item_id": menu_item_id, "is_available_today": True},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Add item to daily menu failed: {r.status_code} {r.text[:200]}")
        return None

    # 3. Publish the daily menu
    r = httpx.patch(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Publish daily menu failed: {r.status_code} {r.text[:200]}")
        return None

    return daily_menu_id


def create_order(student_token, admin_token, cafeteria_id, item_id):
    """Add item to cart, checkout, confirm, and mark ready. Returns order_id."""
    # Add item to cart
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/items",
        json={"menu_item_id": item_id, "quantity": 1},
        headers={"Authorization": f"Bearer {student_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    assert r.status_code in (200, 201), f"Add cart item failed: {r.status_code} {r.text[:200]}"

    # Checkout
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/checkout",
        json={"payment_method": "cash"},
        headers={"Authorization": f"Bearer {student_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    assert r.status_code in (200, 201), f"Checkout failed: {r.status_code} {r.text[:200]}"
    order_id = r.json().get("id")
    assert order_id, f"No order ID: {list(r.json().keys())}"

    # Confirm
    r = httpx.post(
        f"{BASE_URL}/orders/{order_id}/confirm",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    assert r.status_code in (200, 201), f"Confirm failed: {r.status_code} {r.text[:200]}"

    # Prepare (PENDING → PREPARING, must happen before ready)
    r = httpx.post(
        f"{BASE_URL}/orders/{order_id}/prepare",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Prepare failed: {r.status_code} {r.text[:200]}")
    assert r.status_code in (200, 201), f"Prepare failed: {r.status_code} {r.text[:200]}"

    # Ready (PREPARING → READY)
    r = httpx.put(
        f"{BASE_URL}/orders/{order_id}/ready",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    assert r.status_code in (200, 201), f"Ready failed: {r.status_code} {r.text[:200]}"
    return order_id


def set_pickup_deadline(order_id, minutes_ago):
    """Set an order's pickup_deadline to N minutes ago (for testing only)."""
    from datetime import datetime, timedelta, timezone

    deadline = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sql(
        f"UPDATE orders SET pickup_deadline = '{deadline}' "
        f"WHERE id = '{order_id}'"
    )


def get_order(token, order_id):
    """Get order details."""
    r = httpx.get(
        f"{BASE_URL}/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return r.json() if r.status_code == 200 else None


def get_noshow_count(user_id):
    """Get a user's no-show count from DB."""
    result = sql(f"SELECT no_show_count FROM users WHERE id = '{user_id}'")
    return int(result) if result else 0


def get_noshow_records(user_id):
    """Get no-show records for a user from DB."""
    result = sql(
        f"SELECT id FROM no_shows WHERE user_id = '{user_id}'"
    )
    return result.split("\n") if result else []


def is_user_suspended(user_id):
    """Check if a user is ordering_suspended."""
    result = sql(
        f"SELECT ordering_suspended FROM users WHERE id = '{user_id}'"
    )
    return result.lower() in ("t", "true") if result else False


# ── Test Functions ───────────────────────────────────────────────────

passed = 0
failed = 0
total = 9


def run_test(name, test_fn):
    global passed, failed
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        test_fn()
        passed += 1
        print(f"  ✅ PASS")
    except AssertionError as e:
        failed += 1
        print(f"  ❌ FAIL: {e}")
    except Exception as e:
        failed += 1
        print(f"  ❌ ERROR: {e}")


def setup_admin_cafeteria(test_name):
    """Common setup: create admin, cafeteria, assign admin to cafeteria.
    Returns (admin_token, cafeteria_id, item_id, admin_user_id, admin_email).
    The admin_token has cafeteria_manager role and is assigned to the cafeteria.
    """
    admin_token, admin_user_id = register_admin()
    assert admin_token, f"{test_name}: Admin registration failed"

    cafeteria_id = create_cafeteria(admin_token, f"Auto {test_name}")
    assert cafeteria_id, f"{test_name}: Cafeteria creation failed"

    # Assign admin to cafeteria and upgrade role for order ops
    setup_admin_for_cafeteria(admin_user_id, cafeteria_id)

    # Re-login to get fresh token with updated role
    admin_email = f"admin-{admin_user_id[:8]}@lgu.edu.pk"
    # We need the actual email; get it from the register response.
    # Actually we need the password to re-login. Let's get admin_email from DB.
    admin_email_result = sql(
        f"SELECT university_email FROM users WHERE id = '{admin_user_id}'"
    )
    admin_email = admin_email_result if admin_email_result else f"admin-{admin_user_id[:8]}@lgu.edu.pk"
    admin_token = login(admin_email, "AdminPass123!")
    assert admin_token, f"{test_name}: Admin re-login failed"

    item_id = create_menu_item(admin_token, cafeteria_id)
    assert item_id, f"{test_name}: Menu item creation failed"

    # Create and publish daily menu (required for checkout)
    daily_menu_id = create_and_publish_daily_menu(admin_token, cafeteria_id, item_id)
    assert daily_menu_id, f"{test_name}: Daily menu creation/publish failed"

    return admin_token, cafeteria_id, item_id, admin_user_id, admin_email


def test_01_single_order_auto_expires():
    """A READY order past its pickup_deadline is automatically marked uncollected."""
    token, user_id, email = register_student("-01")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C1")

    # Create a full order through the real API (cart → checkout → confirm → ready)
    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    # Verify status is READY
    order_data = get_order(token, order_id)
    assert order_data, "Could not fetch order"
    status = order_data.get("status")
    assert status == "ready", f"Expected READY, got {status}"

    # Set deadline to 5 minutes ago via DB
    set_pickup_deadline(order_id, minutes_ago=5)
    print(f"  Set pickup_deadline to 5 minutes ago")

    # Wait for background worker (interval is 60s, wait up to 70s)
    print(f"  Waiting for background worker (up to 70s)...")
    time.sleep(70)

    # Verify order is now marked uncollected via DB
    # (OrderResponse schema does not expose uncollected_at, so we check DB directly)
    uncollected_result = sql(
        f"SELECT uncollected_at FROM orders WHERE id = '{order_id}' AND uncollected_at IS NOT NULL"
    )
    assert uncollected_result, f"Order not auto-expired. Status: {order_data.get('status')}"
    print(f"  Order automatically marked uncollected at: {uncollected_result}")

    # Verify NoShow record was created
    noshow_count = get_noshow_count(user_id)
    assert noshow_count >= 1, f"No-show count should be >= 1, got {noshow_count}"
    print(f"  No-show count: {noshow_count}")


def test_02_no_show_record_created():
    """An automatically expired order creates a NoShow record."""
    token, user_id, email = register_student("-02")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C2")

    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    set_pickup_deadline(order_id, minutes_ago=10)
    print(f"  Set pickup_deadline to 10 minutes ago")

    print(f"  Waiting for background worker (up to 70s)...")
    time.sleep(70)

    noshow_records = get_noshow_records(user_id)
    assert len(noshow_records) >= 1, f"Expected NoShow records, got {noshow_records}"
    print(f"  NoShow records found: {len(noshow_records)}")


def test_03_multiple_orders_expired():
    """Multiple expired orders are all processed in one worker cycle."""
    token, user_id, email = register_student("-03")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C3")

    order_ids = []
    for i in range(3):
        oid = create_order(token, admin_token, cafeteria_id, item_id)
        order_ids.append(oid)

    for oid in order_ids:
        set_pickup_deadline(oid, minutes_ago=5 + order_ids.index(oid))

    print(f"  Created {len(order_ids)} orders, set deadlines in the past")
    print(f"  Waiting for background worker (up to 70s)...")
    time.sleep(70)

    noshow_count = get_noshow_count(user_id)
    assert noshow_count >= 3, f"Expected >= 3 no-shows, got {noshow_count}"
    print(f"  No-show count: {noshow_count}")


def test_04_future_deadline_not_expired():
    """An order whose deadline is in the future is NOT processed."""
    token, user_id, email = register_student("-04")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C4")

    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    print(f"  Order ready, deadline is ~30 min in future")
    print(f"  Waiting for background worker (up to 70s)...")
    time.sleep(70)

    noshow_count = get_noshow_count(user_id)
    assert noshow_count == 0, f"Expected 0 no-shows, got {noshow_count}"
    print(f"  No-show count: {noshow_count} (correct: order not expired)")


def test_05_collection_prevents_expiry():
    """Collecting an order before deadline prevents expiry processing."""
    token, user_id, email = register_student("-05")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C5")

    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    # Get order number for collection
    order_data = get_order(token, order_id)
    order_number = order_data.get("order_number")
    r = httpx.post(
        f"{BASE_URL}/orders/collect",
        json={"order_number": order_number},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    assert r.status_code in (200, 201), f"Collect failed: {r.status_code} {r.text[:200]}"
    print(f"  Order collected successfully")

    set_pickup_deadline(order_id, minutes_ago=10)
    print(f"  Set pickup_deadline to 10 minutes ago (but order already collected)")
    print(f"  Waiting for background worker (up to 70s)...")
    time.sleep(70)

    noshow_count = get_noshow_count(user_id)
    assert noshow_count == 0, f"Expected 0 no-shows, got {noshow_count}"
    print(f"  No-show count: {noshow_count} (correct: order was collected)")


def test_06_idempotent_processing():
    """Processing the same expired order twice does not create duplicate no-shows."""
    token, user_id, email = register_student("-06")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C6")

    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    set_pickup_deadline(order_id, minutes_ago=10)
    print(f"  Set deadline in past, waiting for first worker cycle...")
    time.sleep(70)

    noshow_after_first = get_noshow_count(user_id)
    print(f"  No-shows after first cycle: {noshow_after_first}")

    print(f"  Waiting for second worker cycle...")
    time.sleep(65)

    noshow_after_second = get_noshow_count(user_id)
    assert noshow_after_second == noshow_after_first, (
        f"Duplicate no-show: {noshow_after_first} → {noshow_after_second}"
    )
    print(f"  No-shows after second cycle: {noshow_after_second} (idempotent ✓)")


def test_07_order_event_recorded():
    """The UNCOLLECTED event type is recorded for auto-expired orders."""
    token, user_id, email = register_student("-07")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C7")

    order_id = create_order(token, admin_token, cafeteria_id, item_id)

    set_pickup_deadline(order_id, minutes_ago=10)
    print(f"  Set deadline in past, waiting for worker...")
    time.sleep(70)

    result = sql(
        f"SELECT event_type FROM order_events WHERE order_id = '{order_id}' AND event_type = 'uncollected'"
    )
    assert result, "UNCOLLECTED event not found in order_events"
    print(f"  UNCOLLECTED event found: {result}")


def test_08_suspension_after_threshold():
    """After N no-shows within the window, the user gets ordering_suspended."""
    token, user_id, email = register_student("-08")
    assert token, "Registration failed"

    admin_token, cafeteria_id, item_id, _, _ = setup_admin_cafeteria("C8")

    for i in range(3):
        oid = create_order(token, admin_token, cafeteria_id, item_id)
        set_pickup_deadline(oid, minutes_ago=5 + i)

    print(f"  Created and expired 3 orders, waiting for worker...")
    time.sleep(70)

    suspended = is_user_suspended(user_id)
    assert suspended, "User should be suspended after 3 no-shows"
    print(f"  User is suspended: {suspended}")

    noshow_count = get_noshow_count(user_id)
    print(f"  No-show count: {noshow_count}")


def test_09_worker_health():
    """The background worker is running and the API is responsive."""
    r = httpx.get(f"{BASE_URL}/health", timeout=10, follow_redirects=FOLLOW_REDIRECTS)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    data = r.json()
    print(f"  Health response: {data}")
    assert data.get("status") == "healthy", f"Unhealthy: {data}"


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 12: LIVE VERIFICATION — Automatic Pickup Expiry")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print(f"Total tests: {total}")

    tests = [
        ("Worker health check", test_09_worker_health),
        ("Single order auto-expires", test_01_single_order_auto_expires),
        ("No-show record created", test_02_no_show_record_created),
        ("Multiple orders expired", test_03_multiple_orders_expired),
        ("Future deadline not expired", test_04_future_deadline_not_expired),
        ("Collection prevents expiry", test_05_collection_prevents_expiry),
        ("Idempotent processing", test_06_idempotent_processing),
        ("Order event recorded", test_07_order_event_recorded),
        ("Suspension after threshold", test_08_suspension_after_threshold),
    ]

    for name, fn in tests:
        run_test(name, fn)

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
