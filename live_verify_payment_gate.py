"""Live Verification: Payment-Preparation Gate.

Verifies that an online-paid order cannot enter preparation unless its
payment has successfully completed.

Tests the actual HTTP/API behavior against the running FastAPI application
and real PostgreSQL database.

CRITICAL CONSTRAINTS:
- Do NOT call internal service methods directly
- Do NOT manually set payment/order status via DB to simulate API behavior
- Database operations allowed ONLY for controlled setup, inspection, cleanup
"""

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from datetime import date, timedelta

import httpx

BASE_URL = "http://127.0.0.1:8001/api/v1"
FOLLOW_REDIRECTS = True
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_dev"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

results: list[tuple[str, str, bool, str]] = []
cleanup_user_ids: list[str] = []


def safe_json(r: httpx.Response, default=None):
    try:
        return r.json()
    except Exception:
        return default


def log_result(test_num: str, name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    results.append((test_num, name, passed, detail))
    print(f"  [{status}] {test_num}: {name}")
    if detail and not passed:
        print(f"         Detail: {detail}")


def uid() -> str:
    return uuid.uuid4().hex[:8]


def sql(query: str) -> str:
    cmd = f'docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -t -A -c "{query}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(first_name, last_name, uid_str, email, password, category=None):
    """Register a user, auto-verify, login. Returns (token, user_id)."""
    body = {
        "first_name": first_name,
        "last_name": last_name,
        "university_id": uid_str,
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
        return None, None
    resp = safe_json(r, {})
    user_id = resp.get("user_id")
    sql(f"UPDATE users SET email_verified = true, status = 'active' WHERE id = '{user_id}'")
    cleanup_user_ids.append(user_id)

    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": email, "password": password},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code != 200:
        print(f"    Login failed: {r.status_code} {r.text[:200]}")
        return None, None
    data = safe_json(r, {})
    tokens = data.get("tokens", data)
    token = tokens.get("access_token") or tokens.get("token")
    return token, user_id


def promote_to_admin(user_id):
    sql(f"UPDATE users SET role = 'university_admin' WHERE id = '{user_id}'")


def promote_to_manager(user_id):
    sql(f"UPDATE users SET role = 'cafeteria_manager' WHERE id = '{user_id}'")


def promote_to_staff(user_id):
    sql(f"UPDATE users SET role = 'cafeteria_staff' WHERE id = '{user_id}'")


def re_login(email, password):
    """Re-login to get a fresh JWT with updated role."""
    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": email, "password": password},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code != 200:
        print(f"    Re-login failed: {r.status_code} {r.text[:200]}")
        return None
    data = safe_json(r, {})
    tokens = data.get("tokens", data)
    return tokens.get("access_token") or tokens.get("token")


def send_webhook(provider: str, payload: dict, headers: dict | None = None) -> httpx.Response:
    """Send a webhook to the payment provider endpoint."""
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return httpx.post(
        f"{BASE_URL}/payments/webhook/{provider}",
        json=payload,
        headers=hdrs,
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup():
    """Create controlled test data: cafeteria, menu items, users."""
    print("\n=== SETUP ===")

    # Manager — start as admin for cafeteria creation, then demote to manager
    mgr_uid = f"pg_mgr_{uid()}"
    mgr_email = f"pgmgr_{uid()}@lgu.edu.pk"
    mgr_token, mgr_id = register_and_login(
        "PayGate", "Manager", mgr_uid, mgr_email, "Test1234!"
    )
    promote_to_admin(mgr_id)
    mgr_token = re_login(mgr_email, "Test1234!")

    # Staff
    staff_uid = f"pg_staff_{uid()}"
    staff_email = f"pgstaff_{uid()}@lgu.edu.pk"
    staff_token, staff_id = register_and_login(
        "PayGate", "Staff", staff_uid, staff_email, "Test1234!"
    )
    promote_to_staff(staff_id)
    staff_token = re_login(staff_email, "Test1234!")

    # Create cafeteria
    r = httpx.post(
        f"{BASE_URL}/cafeterias",
        json={
            "name": f"PayGate Cafeteria {uid()}",
            "type": "student",
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    cafeteria_data = safe_json(r, {})
    cafeteria_id = cafeteria_data.get("id")
    if not cafeteria_id:
        print(f"  FATAL: Cafeteria creation failed: HTTP {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print(f"  Cafeteria: {cafeteria_id}")

    # Assign manager and staff to cafeteria
    sql(
        f"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
        f"VALUES ('{uuid.uuid4()}', '{mgr_id}', '{cafeteria_id}', 'cafeteria_manager', NOW()) "
        f"ON CONFLICT DO NOTHING"
    )
    sql(
        f"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
        f"VALUES ('{uuid.uuid4()}', '{staff_id}', '{cafeteria_id}', 'cafeteria_staff', NOW()) "
        f"ON CONFLICT DO NOTHING"
    )

    # Demote admin to manager and re-login for cafeteria operations
    promote_to_manager(mgr_id)
    mgr_token = re_login(mgr_email, "Test1234!")

    # Create menu item
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/menu-items",
        json={
            "name": f"Burger {uid()}",
            "category": "main_course",
            "price": 10000,
            "is_available": True,
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    item_data = safe_json(r, {})
    item_id = item_data.get("id")
    if not item_id:
        print(f"  FATAL: Menu item creation failed: HTTP {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print(f"  Menu item: {item_id}")

    # Create daily menu (DRAFT -> add item -> PUBLISH)
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus",
        json={"menu_date": date.today().isoformat()},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    daily_menu_id = safe_json(r, {}).get("id")

    httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/items",
        json={"menu_item_id": item_id, "is_available_today": True},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )

    httpx.patch(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/daily-menus/{daily_menu_id}/publish",
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )

    # Create inventory (100)
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/inventory",
        json={
            "menu_item_id": item_id,
            "quantity": 100,
            "unit": "pcs",
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"  FATAL: Inventory creation failed: HTTP {r.status_code} {r.text[:200]}")
        sys.exit(1)

    # Student
    stu_token, stu_id = register_and_login(
        "PayGate", "Student", f"pg_stu_{uid()}", f"pgstu_{uid()}@lgu.edu.pk", "Test1234!"
    )

    print(f"  Manager: {mgr_id}, Staff: {staff_id}, Student: {stu_id}")
    return mgr_token, staff_token, stu_token, cafeteria_id, item_id


def add_to_cart_and_checkout(stu_token, cafeteria_id, item_id, payment_method="online"):
    """Add item to cart and checkout. Returns (order_id, payment_id)."""
    # Add to cart
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/items",
        json={"menu_item_id": item_id, "quantity": 1},
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Cart add failed: HTTP {r.status_code} {r.text[:200]}")

    # Checkout
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/checkout",
        json={"payment_method": payment_method, "order_type": "immediate"},
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Checkout failed ({payment_method}): HTTP {r.status_code} {r.text[:200]}")
    order_data = safe_json(r, {})
    order_id = order_data.get("id")
    return order_id


def initiate_payment(stu_token, order_id):
    """Initiate online payment for an order."""
    r = httpx.post(
        f"{BASE_URL}/payments/initiate/{order_id}",
        json={"idempotency_key": f"idem_{order_id[:8]}_{int(time.time())}"},
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return safe_json(r, {})


def send_payment_success_webhook(order_id):
    """Send a payment_success webhook for the given order."""
    # Get the actual payment reference from the payment record
    pay_data = get_payment_from_db(order_id)
    provider_ref = pay_data.get("provider_reference", f"test_pay_{order_id[:8]}")
    event_id = f"evt_pg_{order_id[:8]}_{int(time.time())}"
    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment_success",
        "payment_reference": provider_ref,
        "amount": 10000,
        "currency": "PKR",
        "timestamp": time.time(),
    }
    r = send_webhook("test_provider", webhook_payload, headers={"x-event-id": event_id})
    return safe_json(r, {})


def send_payment_failure_webhook(order_id):
    """Send a payment_failed webhook for the given order."""
    pay_data = get_payment_from_db(order_id)
    provider_ref = pay_data.get("provider_reference", f"test_pay_{order_id[:8]}")
    event_id = f"evt_fail_{order_id[:8]}_{int(time.time())}"
    webhook_payload = {
        "event_id": event_id,
        "event_type": "payment_failed",
        "payment_reference": provider_ref,
        "amount": 10000,
        "currency": "PKR",
        "timestamp": time.time(),
    }
    r = send_webhook("test_provider", webhook_payload, headers={"x-event-id": event_id})
    return safe_json(r, {})


def prepare_order(staff_token, order_id):
    """Attempt to start preparation for an order."""
    r = httpx.post(
        f"{BASE_URL}/orders/{order_id}/prepare",
        json={},
        headers=auth(staff_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return r, safe_json(r, {})


def get_order(stu_token, order_id):
    """Get order details."""
    r = httpx.get(
        f"{BASE_URL}/orders/{order_id}",
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return safe_json(r, {})


def get_payment(stu_token, order_id):
    """Get payment details for an order."""
    r = httpx.get(
        f"{BASE_URL}/payments/order/{order_id}",
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return safe_json(r, {})


def get_payment_from_db(order_id):
    """Get payment details directly from DB for webhook reference."""
    row = sql(
        f"SELECT provider_reference, status FROM payments WHERE order_id = '{order_id}' LIMIT 1"
    )
    if row:
        parts = row.split("|")
        return {"provider_reference": parts[0], "status": parts[1]}
    return {}


def confirm_order(staff_token, order_id):
    """Confirm an order (manager/staff)."""
    r = httpx.post(
        f"{BASE_URL}/orders/{order_id}/confirm",
        json={},
        headers=auth(staff_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return r, safe_json(r, {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_a_successful_online_payment(stu_token, staff_token, cafeteria_id, item_id):
    """Test A: Successful online payment → preparation allowed."""
    print("\n--- Test A: Successful online payment ---")

    # Create order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id)
    if not order_id:
        log_result("A.1", "Order created", False, "No order_id returned")
        return
    order_before = get_order(stu_token, order_id)
    log_result("A.1", "Order created (online)", order_before.get("status") == "pending",
               f"status={order_before.get('status')}")

    # Initiate payment
    pay_resp = initiate_payment(stu_token, order_id)
    log_result("A.2", "Payment initiated", "payment_id" in pay_resp,
               f"payment={pay_resp}")

    # Send payment success webhook
    wh_resp = send_payment_success_webhook(order_id)
    log_result("A.3", "Payment webhook accepted", wh_resp.get("status") == "ok",
               f"webhook={wh_resp}")

    # Check payment status
    pay_data = get_payment(stu_token, order_id)
    log_result("A.4", "Payment succeeded", pay_data.get("status") == "succeeded",
               f"payment_status={pay_data.get('status')}")

    # Confirm order
    r, _ = confirm_order(staff_token, order_id)
    log_result("A.5", "Order confirmed", r.status_code in (200, 201),
               f"HTTP {r.status_code}")

    # Prepare order
    r, prep_data = prepare_order(staff_token, order_id)
    log_result("A.6", "Preparation started (succeeded payment)", r.status_code in (200, 201),
               f"HTTP {r.status_code}, status={prep_data.get('status')}")


def test_b_pending_online_payment(stu_token, staff_token, cafeteria_id, item_id):
    """Test B: Pending online payment → preparation rejected."""
    print("\n--- Test B: Pending online payment ---")

    # Create order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id)
    if not order_id:
        log_result("B.1", "Order created", False, "No order_id returned")
        return

    # Initiate payment (status is now PENDING)
    pay_resp = initiate_payment(stu_token, order_id)
    pay_data = get_payment(stu_token, order_id)
    log_result("B.1", "Payment initiated (pending)", pay_data.get("status") in ("pending", "processing"),
               f"payment_status={pay_data.get('status')}")

    # Confirm order (manager confirms before payment completes — allowed)
    r, _ = confirm_order(staff_token, order_id)
    log_result("B.2", "Order confirmed", r.status_code in (200, 201),
               f"HTTP {r.status_code}")

    # Attempt preparation (should be rejected)
    r, prep_data = prepare_order(staff_token, order_id)
    order_after = get_order(stu_token, order_id)
    log_result("B.3", "Preparation REJECTED (pending payment)",
               r.status_code in (400, 422),
               f"HTTP {r.status_code}, order_status={order_after.get('status')}")


def test_c_failed_online_payment(stu_token, staff_token, cafeteria_id, item_id):
    """Test C: Failed online payment → preparation rejected."""
    print("\n--- Test C: Failed online payment ---")

    # Create order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id)
    if not order_id:
        log_result("C.1", "Order created", False, "No order_id returned")
        return

    # Initiate payment
    initiate_payment(stu_token, order_id)

    # Send payment failure webhook
    wh_resp = send_payment_failure_webhook(order_id)
    log_result("C.1", "Payment failed via webhook", wh_resp.get("status") == "ok",
               f"webhook={wh_resp}")

    # Check payment status
    pay_data = get_payment(stu_token, order_id)
    log_result("C.2", "Payment status is failed", pay_data.get("status") == "failed",
               f"payment_status={pay_data.get('status')}")

    # Confirm order
    r, _ = confirm_order(staff_token, order_id)
    log_result("C.3", "Order confirmed", r.status_code in (200, 201),
               f"HTTP {r.status_code}")

    # Attempt preparation (should be rejected)
    r, prep_data = prepare_order(staff_token, order_id)
    order_after = get_order(stu_token, order_id)
    log_result("C.4", "Preparation REJECTED (failed payment)",
               r.status_code in (400, 422),
               f"HTTP {r.status_code}, order_status={order_after.get('status')}")


def test_d_abandoned_online_payment(stu_token, staff_token, cafeteria_id, item_id):
    """Test D: Abandoned online payment → preparation rejected."""
    print("\n--- Test D: Abandoned online payment ---")

    # Create order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id)
    if not order_id:
        log_result("D.1", "Order created", False, "No order_id returned")
        return

    # Initiate payment
    initiate_payment(stu_token, order_id)
    pay_data = get_payment(stu_token, order_id)
    log_result("D.1", "Payment initiated (abandoned — no webhook sent)",
               pay_data.get("status") in ("pending", "processing"),
               f"payment_status={pay_data.get('status')}")

    # Confirm order
    r, _ = confirm_order(staff_token, order_id)
    log_result("D.2", "Order confirmed", r.status_code in (200, 201),
               f"HTTP {r.status_code}")

    # Attempt preparation (should be rejected)
    r, prep_data = prepare_order(staff_token, order_id)
    order_after = get_order(stu_token, order_id)
    log_result("D.3", "Preparation REJECTED (abandoned payment)",
               r.status_code in (400, 422),
               f"HTTP {r.status_code}, order_status={order_after.get('status')}")


def test_e_cash_order_regression(stu_token, staff_token, cafeteria_id, item_id):
    """Test E: Cash order → existing confirmation/preparation flow works."""
    print("\n--- Test E: Cash order regression ---")

    # Create cash order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id, payment_method="cash")
    if not order_id:
        log_result("E.1", "Cash order created", False, "No order_id returned")
        return
    order_data = get_order(stu_token, order_id)
    log_result("E.1", "Cash order created", order_data.get("payment_method") == "cash",
               f"payment_method={order_data.get('payment_method')}")

    # Confirm order
    r, _ = confirm_order(staff_token, order_id)
    log_result("E.2", "Cash order confirmed", r.status_code in (200, 201),
               f"HTTP {r.status_code}")

    # Prepare order (should succeed for cash)
    r, prep_data = prepare_order(staff_token, order_id)
    order_after = get_order(stu_token, order_id)
    log_result("E.3", "Cash order preparation started", r.status_code in (200, 201),
               f"HTTP {r.status_code}, status={order_after.get('status')}")


def test_f_bypass_attempt(stu_token, staff_token, cafeteria_id, item_id):
    """Test F: Payment status cannot be bypassed via API-visible state."""
    print("\n--- Test F: Payment status bypass attempt ---")

    # Create online order
    order_id = add_to_cart_and_checkout(stu_token, cafeteria_id, item_id)
    if not order_id:
        log_result("F.1", "Order created", False, "No order_id returned")
        return

    # Initiate payment
    initiate_payment(stu_token, order_id)

    # Confirm order (without paying)
    r, _ = confirm_order(staff_token, order_id)
    confirmed = r.status_code in (200, 201)
    log_result("F.1", "Order confirmed without payment", confirmed,
               f"HTTP {r.status_code}")

    # Attempt preparation — should be rejected even though order is confirmed
    r, prep_data = prepare_order(staff_token, order_id)
    order_after = get_order(stu_token, order_id)
    rejected = r.status_code in (400, 422)
    log_result("F.2", "Preparation rejected despite confirmed status",
               rejected,
               f"HTTP {r.status_code}, order_status={order_after.get('status')}")

    # Verify payment is still not succeeded
    pay_data = get_payment(stu_token, order_id)
    log_result("F.3", "Payment still not succeeded",
               pay_data.get("status") != "succeeded",
               f"payment_status={pay_data.get('status')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 60)
    print("UniServe — Live Verification: Payment-Preparation Gate")
    print("=" * 60)

    try:
        mgr_token, staff_token, stu_token, cafeteria_id, item_id = setup()
    except Exception as e:
        print(f"\n  SETUP FAILED: {e}")
        sys.exit(1)

    # Run all tests
    test_a_successful_online_payment(stu_token, staff_token, cafeteria_id, item_id)
    test_b_pending_online_payment(stu_token, staff_token, cafeteria_id, item_id)
    test_c_failed_online_payment(stu_token, staff_token, cafeteria_id, item_id)
    test_d_abandoned_online_payment(stu_token, staff_token, cafeteria_id, item_id)
    test_e_cash_order_regression(stu_token, staff_token, cafeteria_id, item_id)
    test_f_bypass_attempt(stu_token, staff_token, cafeteria_id, item_id)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, _, p, _ in results if p)
    failed = sum(1 for _, _, p, _ in results if not p)
    total = len(results)
    for test_num, name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        line = f"  [{status}] {test_num}: {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)

    print(f"\n  Total: {total} | Passed: {passed} | Failed: {failed}")

    if failed == 0:
        print("\n  ALL TESTS PASSED")
    else:
        print(f"\n  {failed} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
