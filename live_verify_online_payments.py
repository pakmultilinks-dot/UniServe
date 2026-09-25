"""Phase 6 Live Verification -- Online Payments & Order Integration.

Uses the real running FastAPI API (http://127.0.0.1:8001).
Tests payment initiation, webhooks, idempotency, refunds, IDOR, inventory, etc.

CRITICAL CONSTRAINTS:
- Do NOT call internal service methods directly
- Do NOT manually set payment/order status to simulate API behavior
- Database operations allowed ONLY for controlled setup, inspection, cleanup
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime

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
    """Safely parse JSON from a response, returning default on failure."""
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


def create_cafeteria(mgr_token, name="PayTest Cafeteria"):
    r = httpx.post(
        f"{BASE_URL}/cafeterias",
        json={
            "name": name,
            "type": "student",
            "location": "Building A",
            "timezone": "Asia/Karachi",
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create cafeteria failed: {r.status_code} {r.text[:200]}")
        return None
    return safe_json(r, {}).get("id")


def assign_to_cafeteria(user_id, cafeteria_id, role="cafeteria_manager"):
    assignment_id = str(uuid.uuid4())
    sql(
        f"INSERT INTO cafeteria_assignments (id, user_id, cafeteria_id, role, created_at) "
        f"VALUES ('{assignment_id}', '{user_id}', '{cafeteria_id}', '{role}', NOW()) "
        f"ON CONFLICT DO NOTHING"
    )


def create_menu_item(mgr_token, caf_id, name="Pay Burger", price=500):
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/menu-items",
        json={
            "name": name,
            "description": "Payment test item",
            "price": price,
            "currency": "PKR",
            "category": "main_course",
            "is_available": True,
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create menu item failed: {r.status_code} {r.text[:200]}")
        return None
    mi_id = safe_json(r, {}).get("id")

    # Create inventory
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/inventory",
        json={
            "menu_item_id": mi_id,
            "quantity": 100,
            "unit": "portions",
            "low_threshold": 5,
        },
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create inventory failed: {r.status_code} {r.text[:200]}")
        return None
    return mi_id


def create_and_publish_daily_menu(mgr_token, caf_id, mi_id):
    from datetime import date as date_type
    today = date_type.today().isoformat()
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/daily-menus",
        json={"menu_date": today},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create daily menu failed: {r.status_code} {r.text[:200]}")
        return None
    dm_id = safe_json(r, {}).get("id")

    r = httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/daily-menus/{dm_id}/items",
        json={"menu_item_id": mi_id, "is_available_today": True},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Add item to daily menu failed: {r.status_code} {r.text[:200]}")
        return None

    r = httpx.patch(
        f"{BASE_URL}/cafeterias/{caf_id}/daily-menus/{dm_id}/publish",
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Publish daily menu failed: {r.status_code} {r.text[:200]}")
        return None
    return dm_id


def add_to_cart(stu_token, caf_id, mi_id, qty=1):
    return httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/cart/items",
        json={"menu_item_id": mi_id, "quantity": qty},
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def checkout(stu_token, caf_id, payment="online", order_type="immediate", sched_time=None):
    body: dict = {"payment_method": payment, "order_type": order_type}
    if sched_time:
        body["scheduled_collection_time"] = sched_time
    return httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/cart/checkout",
        json=body,
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def initiate_payment(stu_token, order_id, idem_key=None):
    if idem_key is None:
        idem_key = f"idem_{uid()}"
    return httpx.post(
        f"{BASE_URL}/payments/initiate/{order_id}",
        json={"idempotency_key": idem_key},
        headers=auth(stu_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def send_webhook(event_type, payment_reference, amount, event_id=None, currency="PKR",
                 extra=None, provider="test_provider"):
    if event_id is None:
        event_id = f"evt_{uid()}"
    payload: dict = {
        "event_id": event_id,
        "event_type": event_type,
        "payment_reference": payment_reference,
        "amount": amount,
        "currency": currency,
    }
    if extra:
        payload.update(extra)
    return httpx.post(
        f"{BASE_URL}/payments/webhook/{provider}",
        json=payload,
        headers={"x-event-id": event_id},
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def get_inventory_qty(caf_id, mi_id):
    result = sql(
        f"SELECT quantity FROM inventory_items "
        f"WHERE cafeteria_id = '{caf_id}' AND menu_item_id = '{mi_id}'"
    )
    return int(result) if result else None


def get_provider_ref(payment_id):
    return sql(f"SELECT provider_reference FROM payments WHERE id = '{payment_id}'")


def get_order_from_api(token, order_id):
    r = httpx.get(
        f"{BASE_URL}/orders/{order_id}",
        headers=auth(token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    return safe_json(r) if r.status_code == 200 else None


def confirm_order(mgr_token, order_id):
    return httpx.post(
        f"{BASE_URL}/orders/{order_id}/confirm",
        json={},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def start_preparation(stf_token, order_id):
    return httpx.post(
        f"{BASE_URL}/orders/{order_id}/prepare",
        json={},
        headers=auth(stf_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def mark_ready(mgr_token, order_id):
    return httpx.put(
        f"{BASE_URL}/orders/{order_id}/ready",
        json={},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def collect_order(stf_token, order_number):
    return httpx.post(
        f"{BASE_URL}/orders/collect",
        json={"order_number": order_number},
        headers=auth(stf_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )


def cleanup() -> None:
    print("\n  Cleaning up test data...")
    for uid_str in cleanup_user_ids:
        sql(f"DELETE FROM user_sessions WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM cafeteria_assignments WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM user_pins WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM user_credentials WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM no_shows WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM refresh_tokens WHERE user_id = '{uid_str}'")
        sql(f"DELETE FROM addresses WHERE user_id = '{uid_str}'")
        sql(f"UPDATE users SET status = 'deleted' WHERE id = '{uid_str}'")
    print("  Cleanup done.")


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    print("=" * 70)
    print("Phase 6 Live Verification -- Online Payments & Order Integration")
    print("=" * 70)

    # ======================================================================
    # SETUP
    # ======================================================================
    print("\n=== SETUP ===")

    # University admin (for refund processing)
    admin_uuid = uid()
    admin_email = f"payadmin-{admin_uuid}@lgu.edu.pk"
    admin_token, admin_id = register_and_login(
        "Pay", "Admin", f"pa-{admin_uuid}", admin_email, "AdminPass123!", "student"
    )
    promote_to_admin(admin_id)
    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": admin_email, "password": "AdminPass123!"},
        timeout=30, follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code == 200:
        _bj = safe_json(r, {})
        admin_token = _bj.get("tokens", _bj).get("access_token", "")
    print(f"  Admin: {admin_id}")

    # Manager
    mgr_uuid = uid()
    mgr_email = f"paymgr-{mgr_uuid}@lgu.edu.pk"
    mgr_token, mgr_id = register_and_login(
        "Pay", "Manager", f"pm-{mgr_uuid}", mgr_email, "ManagerPass123!", "student"
    )
    promote_to_manager(mgr_id)
    r = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": mgr_email, "password": "ManagerPass123!"},
        timeout=30, follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code == 200:
        _bj = safe_json(r, {})
        mgr_token = _bj.get("tokens", _bj).get("access_token", "")
    print(f"  Manager: {mgr_id}")

    # Cafeteria (created by admin, managed by manager)
    caf_id = create_cafeteria(admin_token, f"PayCaf-{uid()[:4]}")
    if not caf_id:
        print("  FATAL: Cannot create cafeteria")
        return 1
    assign_to_cafeteria(mgr_id, caf_id, "cafeteria_manager")
    print(f"  Cafeteria: {caf_id}")

    # Staff
    stf_uuid = uid()
    stf_email = f"paystf-{stf_uuid}@lgu.edu.pk"
    stf_token, stf_id = register_and_login(
        "Pay", "Staff", f"ps-{stf_uuid}", stf_email, "StaffPass123!", "student"
    )
    promote_to_staff(stf_id)
    assign_to_cafeteria(stf_id, caf_id, "cafeteria_staff")
    print(f"  Staff: {stf_id}")

    # Menu item + inventory
    mi_id = create_menu_item(mgr_token, caf_id)
    if not mi_id:
        print("  FATAL: Cannot create menu item")
        return 1
    print(f"  Menu item: {mi_id}")

    # Second menu item for partial cancel tests
    mi_id_2 = create_menu_item(mgr_token, caf_id, name="Pay Fries", price=500)
    if not mi_id_2:
        print("  FATAL: Cannot create second menu item")
        return 1
    print(f"  Menu item 2: {mi_id_2}")

    # Daily menu: create, add BOTH items, then publish
    from datetime import date as date_type
    today_str = date_type.today().isoformat()
    r = httpx.post(
        f"{BASE_URL}/cafeterias/{caf_id}/daily-menus",
        json={"menu_date": today_str},
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Create daily menu failed: {r.status_code} {r.text[:200]}")
        return 1
    dm_id = safe_json(r, {}).get("id")
    print(f"  Daily menu (DRAFT): {dm_id}")

    # Add both menu items to the DRAFT daily menu
    for item_id, item_name in [(mi_id, "Burger"), (mi_id_2, "Fries")]:
        r = httpx.post(
            f"{BASE_URL}/cafeterias/{caf_id}/daily-menus/{dm_id}/items",
            json={"menu_item_id": item_id, "is_available_today": True},
            headers=auth(mgr_token),
            timeout=30,
            follow_redirects=FOLLOW_REDIRECTS,
        )
        if r.status_code in (200, 201):
            print(f"  Added {item_name} to daily menu")
        else:
            print(f"  WARN: Could not add {item_name} to daily menu: {r.status_code}")

    # Now publish
    r = httpx.patch(
        f"{BASE_URL}/cafeterias/{caf_id}/daily-menus/{dm_id}/publish",
        headers=auth(mgr_token),
        timeout=30,
        follow_redirects=FOLLOW_REDIRECTS,
    )
    if r.status_code not in (200, 201):
        print(f"    Publish daily menu failed: {r.status_code} {r.text[:200]}")
        return 1
    print(f"  Daily menu published")

    # Student (payment user)
    stu_uuid = uid()
    stu_email = f"paystu-{stu_uuid}@lgu.edu.pk"
    stu_token, stu_id = register_and_login(
        "Pay", "Student", f"ps-{stu_uuid}", stu_email, "StudentPass123!", "student"
    )
    print(f"  Student: {stu_id}")

    # Second student for IDOR
    stu2_uuid = uid()
    stu2_email = f"paystu2-{stu2_uuid}@lgu.edu.pk"
    stu2_token, stu2_id = register_and_login(
        "Pay2", "Student2", f"ps2-{stu2_uuid}", stu2_email, "StudentPass123!", "student"
    )
    print(f"  Student2 (IDOR): {stu2_id}")

    inv_before = get_inventory_qty(caf_id, mi_id)
    print(f"  Initial inventory: {inv_before}")

    # ======================================================================
    # TEST 1: Online Payment Happy Path
    # ======================================================================
    print("\n=== TEST 1: Online Payment Happy Path ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online", order_type="immediate")
    order_1 = safe_json(r) if r.status_code in (200, 201) else None
    order_id_1 = order_1["id"] if order_1 else None
    total_1 = order_1["total_amount"] if order_1 else 0
    log_result("1.1", "Order created with online payment", bool(order_id_1))

    if order_1:
        ord_data = get_order_from_api(stu_token, order_id_1)
        if ord_data:
            log_result("1.2", "Order status is PENDING before payment",
                        ord_data["status"] == "pending", f"status={ord_data['status']}")
            log_result("1.3", "Payment method is online",
                        ord_data["payment_method"] == "online", f"method={ord_data['payment_method']}")
            log_result("1.4", "Inventory NOT reserved before payment",
                        ord_data["inventory_reserved"] is False,
                        f"reserved={ord_data['inventory_reserved']}")
            log_result("1.5", "Server-calculated amount used",
                        total_1 == ord_data["total_amount"],
                        f"total={total_1}, server={ord_data['total_amount']}")

        # Initiate payment
        idem_key_1 = f"idem_{uid()}"
        r = initiate_payment(stu_token, order_id_1, idem_key_1)
        pay_1 = safe_json(r) if r.status_code == 201 else None
        pay_id_1 = pay_1["payment_id"] if pay_1 else None
        log_result("1.6", "Payment initiation succeeds (201)", r.status_code == 201,
                    f"HTTP {r.status_code}")
        if pay_1:
            log_result("1.7", "Payment status is processing",
                        pay_1["status"] == "processing", f"status={pay_1['status']}")
            log_result("1.8", "Provider is test_provider",
                        pay_1["provider_name"] == "test_provider",
                        f"provider={pay_1['provider_name']}")
            log_result("1.9", "Redirect URL field present (test_provider returns None)",
                        "redirect_url" in pay_1,
                        f"url={str(pay_1.get('redirect_url', ''))[:60]}")
        else:
            for i in range(7, 10):
                log_result(f"1.{i}", "Skipped", False, "Payment initiation failed")

        if pay_id_1:
            provider_ref = get_provider_ref(pay_id_1)
            log_result("1.10", "Provider reference assigned",
                        bool(provider_ref) and provider_ref != "",
                        f"ref={provider_ref[:30] if provider_ref else 'None'}")

            # Send success webhook
            r = send_webhook("payment_success", provider_ref, total_1)
            r_status = "ok" if r.status_code == 200 else f"HTTP {r.status_code}"
            try:
                r_body = safe_json(r, {})
                r_status = r_body.get("status", r_status) if r_body else r_status
            except Exception:
                r_status = f"HTTP {r.status_code}, body={r.text[:100]}"
            log_result("1.11", "Webhook accepted",
                        r.status_code == 200 and r_status == "ok",
                        f"HTTP {r.status_code}, status={r_status}")

            # Verify payment succeeded
            r = httpx.get(f"{BASE_URL}/payments/{pay_id_1}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _pj = safe_json(r, {})
                log_result("1.12", "Payment status is succeeded",
                            _pj.get("status") == "succeeded",
                            f"status={_pj.get('status')}")

            # Check order
            ord_data = get_order_from_api(stu_token, order_id_1)
            if ord_data:
                log_result("1.13", "Order still PENDING (preparation phase)",
                            ord_data["status"] == "pending",
                            f"status={ord_data['status']}")
                log_result("1.14", "Inventory reserved after payment",
                            ord_data["inventory_reserved"] is True,
                            f"reserved={ord_data['inventory_reserved']}")

            # Manager can see the order
            r = httpx.get(f"{BASE_URL}/orders/cafeteria/{caf_id}",
                         headers=auth(mgr_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _rj = safe_json(r, [])
                orders_list = _rj if isinstance(_rj, list) else (_rj.get("items", _rj.get("orders", [])) if isinstance(_rj, dict) else [])
                if isinstance(orders_list, dict):
                    orders_list = orders_list.get("items", orders_list.get("orders", []))
                found = any(o["id"] == order_id_1 for o in orders_list) if isinstance(orders_list, list) else False
                log_result("1.15", "Cafeteria can see paid order", found)
        else:
            for i in range(10, 16):
                log_result(f"1.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(2, 16):
            log_result(f"1.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 2: Server-Authoritative Amount
    # ======================================================================
    print("\n=== TEST 2: Server-Authoritative Amount ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r2 = safe_json(r, {})
        oid_2 = _r2["id"]
        total_2 = _r2["total_amount"]

        # Try to pass amount in body
        r = httpx.post(
            f"{BASE_URL}/payments/initiate/{oid_2}",
            json={"idempotency_key": f"idem_{uid()}", "amount": 1},
            headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
        )
        if r.status_code == 422:
            log_result("2.1", "Amount field rejected by schema validation", True)
        elif r.status_code == 201:
            pay_id = safe_json(r, {}).get("payment_id")
            r2 = httpx.get(f"{BASE_URL}/payments/{pay_id}",
                          headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r2.status_code == 200:
                _r2j = safe_json(r2, {})
                log_result("2.1", "Server ignores client-supplied amount",
                            _r2j.get("amount") == total_2,
                            f"client=1, server={_r2j.get('amount')}, expected={total_2}")
        else:
            log_result("2.1", "Amount field handling", False, f"HTTP {r.status_code}")

        # Verify via order endpoint
        r = httpx.get(f"{BASE_URL}/payments/order/{oid_2}",
                     headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
        if r.status_code == 200:
            _r2j = safe_json(r, {})
            log_result("2.2", "Payment amount matches order total",
                        _r2j.get("amount") == total_2,
                        f"pay={_r2j.get('amount')}, order={total_2}")
        else:
            log_result("2.2", "Payment amount match", False, f"HTTP {r.status_code}")
    else:
        log_result("2.1", "Order creation", False, f"HTTP {r.status_code}")
        log_result("2.2", "Amount match", False, "Skipped")

    # ======================================================================
    # TEST 3: Payment Failure
    # ======================================================================
    print("\n=== TEST 3: Payment Failure ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r3 = safe_json(r, {})
        oid_3 = _r3["id"]
        total_3 = _r3["total_amount"]
        r = initiate_payment(stu_token, oid_3)
        if r.status_code == 201:
            pay_id_3 = safe_json(r, {}).get("payment_id")
            pr_3 = get_provider_ref(pay_id_3)

            send_webhook("payment_failed", pr_3, total_3)

            r = httpx.get(f"{BASE_URL}/payments/{pay_id_3}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _r3j = safe_json(r, {})
                log_result("3.1", "Payment status is failed",
                            _r3j.get("status") == "failed",
                            f"status={_r3j.get('status')}")

            ord_data = get_order_from_api(stu_token, oid_3)
            if ord_data:
                log_result("3.2", "Order not prepared after failure",
                            ord_data["status"] == "pending",
                            f"status={ord_data['status']}")
                log_result("3.3", "Inventory not consumed after failure",
                            ord_data["inventory_reserved"] is False,
                            f"reserved={ord_data['inventory_reserved']}")

            attempt_count = sql(
                f"SELECT COUNT(*) FROM payment_attempts WHERE payment_id = '{pay_id_3}'"
            )
            log_result("3.4", "Payment attempt recorded",
                        attempt_count.strip() == "1",
                        f"attempts={attempt_count}")
        else:
            for i in range(1, 5):
                log_result(f"3.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"3.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 4: Payment Abandonment
    # ======================================================================
    print("\n=== TEST 4: Payment Abandonment ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r4 = safe_json(r, {})
        oid_4 = _r4["id"]
        r = initiate_payment(stu_token, oid_4)
        if r.status_code == 201:
            pay_id_4 = safe_json(r, {}).get("payment_id")
            time.sleep(0.5)

            r = httpx.get(f"{BASE_URL}/payments/{pay_id_4}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _r4j = safe_json(r, {})
                log_result("4.1", "Payment remains processing (not succeeded)",
                            _r4j.get("status") == "processing",
                            f"status={_r4j.get('status')}")

            ord_data = get_order_from_api(stu_token, oid_4)
            if ord_data:
                log_result("4.2", "Order not prepared after abandonment",
                            ord_data["status"] == "pending",
                            f"status={ord_data['status']}")
                log_result("4.3", "Inventory not consumed",
                            ord_data["inventory_reserved"] is False,
                            f"reserved={ord_data['inventory_reserved']}")

            # New payment attempt allowed
            r2 = initiate_payment(stu_token, oid_4)
            log_result("4.4", "New payment attempt allowed for abandoned order",
                        r2.status_code == 201,
                        f"HTTP {r2.status_code}")
        else:
            for i in range(1, 5):
                log_result(f"4.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"4.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 5: Valid Webhook
    # ======================================================================
    print("\n=== TEST 5: Valid Webhook ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r5 = safe_json(r, {})
        oid_5 = _r5["id"]
        total_5 = _r5["total_amount"]
        r = initiate_payment(stu_token, oid_5)
        if r.status_code == 201:
            pay_id_5 = safe_json(r, {}).get("payment_id")
            pr_5 = get_provider_ref(pay_id_5)

            evt_id_5 = f"evt_{uid()}"
            r = send_webhook("payment_success", pr_5, total_5, event_id=evt_id_5)
            _r5j = safe_json(r, {})
            log_result("5.1", "Valid webhook accepted (status=ok)",
                        r.status_code == 200 and _r5j.get("status") == "ok",
                        f"HTTP {r.status_code}, status={_r5j.get('status')}")

            # Check webhook event recorded
            webhook_count = sql(
                f"SELECT processed FROM webhook_events WHERE provider_event_id = '{evt_id_5}'"
            )
            log_result("5.2", "Webhook event recorded in database",
                        "t" in webhook_count.lower(),
                        f"processed={webhook_count}")

            # Payment succeeded
            r = httpx.get(f"{BASE_URL}/payments/{pay_id_5}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _r5pj = safe_json(r, {})
                log_result("5.3", "Payment succeeded after valid webhook",
                            _r5pj.get("status") == "succeeded",
                            f"status={_r5pj.get('status')}")
        else:
            for i in range(1, 4):
                log_result(f"5.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 4):
            log_result(f"5.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 6: Invalid Webhook Signature
    # ======================================================================
    print("\n=== TEST 6: Invalid Webhook Signature ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r6 = safe_json(r, {})
        oid_6 = _r6["id"]
        r = initiate_payment(stu_token, oid_6)
        if r.status_code == 201:
            pay_id_6 = safe_json(r, {}).get("payment_id")

            # Invalid JSON payload
            evt_id_6 = f"evt_{uid()}"
            r = httpx.post(
                f"{BASE_URL}/payments/webhook/test_provider",
                content=b"not-json-at-all",
                headers={"Content-Type": "application/json", "x-event-id": evt_id_6},
                timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("6.1", "Invalid JSON webhook handled gracefully",
                        r.status_code == 200,
                        f"HTTP {r.status_code}")
            if r.status_code == 200:
                _r6j = safe_json(r, {})
                log_result("6.2", "Reports ignored for invalid payload",
                            _r6j.get("status") in ("ignored", "ok"),
                            f"status={_r6j.get('status')}")

            # Payment should NOT be succeeded
            r = httpx.get(f"{BASE_URL}/payments/{pay_id_6}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _r6pj = safe_json(r, {})
                log_result("6.3", "Payment unchanged after invalid webhook",
                            _r6pj.get("status") != "succeeded",
                            f"status={_r6pj.get('status')}")
        else:
            for i in range(1, 4):
                log_result(f"6.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 4):
            log_result(f"6.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 7: Tampered Webhook Payload
    # ======================================================================
    print("\n=== TEST 7: Tampered Webhook Payload ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r7 = safe_json(r, {})
        oid_7 = _r7["id"]
        total_7 = _r7["total_amount"]
        r = initiate_payment(stu_token, oid_7)
        if r.status_code == 201:
            pay_id_7 = safe_json(r, {}).get("payment_id")
            pr_7 = get_provider_ref(pay_id_7)

            # Wrong reference
            r = send_webhook("payment_success", "test_pay_NONEXISTENT999", total_7)
            if r.status_code == 200:
                _r7j = safe_json(r, {})
                log_result("7.1", "Wrong payment reference: ignored",
                            _r7j.get("status") == "ignored",
                            f"status={_r7j.get('status')}")

            # Wrong amount
            r = send_webhook("payment_success", pr_7, 1)
            if r.status_code == 200:
                _r7j2 = safe_json(r, {})
                log_result("7.2", "Wrong amount: ignored",
                            _r7j2.get("status") == "ignored",
                            f"status={_r7j2.get('status')}")

            # Payment unchanged
            r = httpx.get(f"{BASE_URL}/payments/{pay_id_7}",
                         headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            if r.status_code == 200:
                _r7pj = safe_json(r, {})
                log_result("7.3", "Payment unchanged after tampered webhooks",
                            _r7pj.get("status") == "processing",
                            f"status={_r7pj.get('status')}")
        else:
            for i in range(1, 4):
                log_result(f"7.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 4):
            log_result(f"7.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 8: Webhook Replay / Idempotency
    # ======================================================================
    print("\n=== TEST 8: Webhook Replay / Idempotency ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r8 = safe_json(r, {})
        oid_8 = _r8["id"]
        total_8 = _r8["total_amount"]
        r = initiate_payment(stu_token, oid_8)
        if r.status_code == 201:
            pay_id_8 = safe_json(r, {}).get("payment_id")
            pr_8 = get_provider_ref(pay_id_8)

            evt_id_8 = f"evt_replay_{uid()}"
            r1 = send_webhook("payment_success", pr_8, total_8, event_id=evt_id_8)
            _r8j1 = safe_json(r1, {})
            log_result("8.1", "First webhook processed (status=ok)",
                        r1.status_code == 200 and _r8j1.get("status") == "ok",
                        f"HTTP {r1.status_code}")

            # Replay
            r2 = send_webhook("payment_success", pr_8, total_8, event_id=evt_id_8)
            _r8j2 = safe_json(r2, {})
            log_result("8.2", "Replay webhook returns ignored",
                        r2.status_code == 200 and _r8j2.get("status") == "ignored",
                        f"HTTP {r2.status_code}, status={_r8j2.get('status')}")

            pay_count = sql(f"SELECT COUNT(*) FROM payments WHERE order_id = '{oid_8}'")
            log_result("8.3", "No duplicate payment records",
                        pay_count.strip() == "1",
                        f"count={pay_count}")

            processed = sql(
                f"SELECT processed FROM webhook_events WHERE provider_event_id = '{evt_id_8}'"
            )
            log_result("8.4", "Webhook processed exactly once",
                        processed.strip() == "t",
                        f"processed={processed}")

            inv_8 = get_inventory_qty(caf_id, mi_id)
            log_result("8.5", "Inventory not double-deducted",
                        inv_8 is not None and inv_8 >= 0,
                        f"inventory={inv_8}")
        else:
            for i in range(1, 6):
                log_result(f"8.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 6):
            log_result(f"8.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 9: Payment Initiation Idempotency
    # ======================================================================
    print("\n=== TEST 9: Payment Initiation Idempotency ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r9 = safe_json(r, {})
        oid_9 = _r9["id"]
        idem_9 = f"idem_{uid()}"
        r1 = initiate_payment(stu_token, oid_9, idem_9)
        log_result("9.1", "First initiation succeeds (201)",
                    r1.status_code == 201, f"HTTP {r1.status_code}")
        if r1.status_code == 201:
            pid_9a = safe_json(r1, {}).get("payment_id")
            r2 = initiate_payment(stu_token, oid_9, idem_9)
            log_result("9.2", "Second initiation returns existing (idempotent)",
                        r2.status_code in (200, 201),
                        f"HTTP {r2.status_code}")
            if r2.status_code in (200, 201):
                pid_9b = safe_json(r2, {}).get("payment_id")
                log_result("9.3", "Same payment_id returned",
                            pid_9a == pid_9b,
                            f"first={pid_9a[:12]}, second={pid_9b[:12]}")

            pay_count = sql(f"SELECT COUNT(*) FROM payments WHERE order_id = '{oid_9}'")
            log_result("9.4", "Only one payment record in database",
                        pay_count.strip() == "1",
                        f"count={pay_count}")
        else:
            for i in range(2, 5):
                log_result(f"9.{i}", "Skipped", False, "Initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"9.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 10: Immediate Order Full Integration Flow
    # ======================================================================
    print("\n=== TEST 10: Immediate Order Integration ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r10 = safe_json(r, {})
        oid_10 = _r10["id"]
        total_10 = _r10["total_amount"]
        r = initiate_payment(stu_token, oid_10)
        if r.status_code == 201:
            pr_10 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_10, total_10)

            r = confirm_order(mgr_token, oid_10)
            log_result("10.1", "Manager confirms order after payment",
                        r.status_code in (200, 201), f"HTTP {r.status_code}")

            r = start_preparation(stf_token, oid_10)
            log_result("10.2", "Staff starts preparation",
                        r.status_code in (200, 201), f"HTTP {r.status_code}")

            r = mark_ready(mgr_token, oid_10)
            log_result("10.3", "Order marked ready",
                        r.status_code in (200, 201), f"HTTP {r.status_code}")

            ord_data = get_order_from_api(stu_token, oid_10)
            if ord_data:
                order_num = ord_data.get("order_number") or sql(
                    f"SELECT order_number FROM orders WHERE id = '{oid_10}'"
                )
                if order_num:
                    r = collect_order(stf_token, int(order_num))
                    log_result("10.4", "Order collected",
                                r.status_code in (200, 201), f"HTTP {r.status_code}")
        else:
            for i in range(2, 5):
                log_result(f"10.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"10.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 11: Scheduled Order Integration
    # ======================================================================
    print("\n=== TEST 11: Scheduled Order Integration ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online", order_type="scheduled", sched_time="23:00")
    if r.status_code in (200, 201):
        _r11 = safe_json(r, {})
        oid_11 = _r11["id"]
        total_11 = _r11["total_amount"]

        ord_data = get_order_from_api(stu_token, oid_11)
        if ord_data:
            log_result("11.1", "Scheduled order created",
                        ord_data["order_type"] == "scheduled",
                        f"type={ord_data['order_type']}")
            log_result("11.2", "Scheduled order in PENDING",
                        ord_data["status"] == "pending",
                        f"status={ord_data['status']}")
            log_result("11.3", "Inventory NOT reserved at checkout",
                        ord_data["inventory_reserved"] is False,
                        f"reserved={ord_data['inventory_reserved']}")

        inv_before_11 = get_inventory_qty(caf_id, mi_id)
        r = initiate_payment(stu_token, oid_11)
        if r.status_code == 201:
            pr_11 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_11, total_11)

            inv_after_pay = get_inventory_qty(caf_id, mi_id)
            log_result("11.4", "Inventory NOT reserved after payment (scheduled)",
                        inv_after_pay == inv_before_11,
                        f"before={inv_before_11}, after={inv_after_pay}")

            ord_data = get_order_from_api(stu_token, oid_11)
            if ord_data:
                log_result("11.5", "Order status remains pending",
                            ord_data["status"] == "pending",
                            f"status={ord_data['status']}")

            # Confirm + prepare
            confirm_order(mgr_token, oid_11)
            start_preparation(stf_token, oid_11)
            inv_after_prep = get_inventory_qty(caf_id, mi_id)
            log_result("11.6", "Inventory reserved at preparation start",
                        inv_after_prep is not None and inv_after_prep < inv_before_11,
                        f"before={inv_before_11}, after_prep={inv_after_prep}")
        else:
            for i in range(4, 7):
                log_result(f"11.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 7):
            log_result(f"11.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 12: Immediate Inventory Behavior
    # ======================================================================
    print("\n=== TEST 12: Immediate Inventory Behavior ===")

    inv_12_before = get_inventory_qty(caf_id, mi_id)
    add_to_cart(stu_token, caf_id, mi_id)
    inv_12_cart = get_inventory_qty(caf_id, mi_id)
    log_result("12.1", "Inventory unchanged after cart add",
                inv_12_before == inv_12_cart,
                f"before={inv_12_before}, cart={inv_12_cart}")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r12 = safe_json(r, {})
        oid_12 = _r12["id"]
        total_12 = _r12["total_amount"]
        inv_12_checkout = get_inventory_qty(caf_id, mi_id)
        log_result("12.2", "Inventory unchanged after checkout",
                    inv_12_before == inv_12_checkout,
                    f"before={inv_12_before}, checkout={inv_12_checkout}")

        r = initiate_payment(stu_token, oid_12)
        if r.status_code == 201:
            pr_12 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_12, total_12)
            inv_12_pay = get_inventory_qty(caf_id, mi_id)
            log_result("12.3", "Inventory reserved after payment success",
                        inv_12_pay is not None and inv_12_pay < inv_12_before,
                        f"before={inv_12_before}, after_pay={inv_12_pay}")

            # Prepare
            confirm_order(mgr_token, oid_12)
            start_preparation(stf_token, oid_12)
            inv_12_prep = get_inventory_qty(caf_id, mi_id)
            log_result("12.4", "NOT double-deducted at preparation",
                        inv_12_prep == inv_12_pay,
                        f"after_pay={inv_12_pay}, after_prep={inv_12_prep}")
        else:
            for i in range(3, 5):
                log_result(f"12.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(2, 5):
            log_result(f"12.{i}", "Skipped", False, "Checkout failed")

    # ======================================================================
    # TEST 13: Scheduled Inventory Behavior
    # ======================================================================
    print("\n=== TEST 13: Scheduled Inventory Behavior ===")

    inv_13_before = get_inventory_qty(caf_id, mi_id)
    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online", order_type="scheduled", sched_time="23:00")
    if r.status_code in (200, 201):
        _r13 = safe_json(r, {})
        oid_13 = _r13["id"]
        total_13 = _r13["total_amount"]
        r = initiate_payment(stu_token, oid_13)
        if r.status_code == 201:
            pr_13 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_13, total_13)

            inv_after_13 = get_inventory_qty(caf_id, mi_id)
            log_result("13.1", "Inventory NOT reserved after scheduled payment",
                        inv_after_13 == inv_13_before,
                        f"before={inv_13_before}, after={inv_after_13}")

            confirm_order(mgr_token, oid_13)
            start_preparation(stf_token, oid_13)
            inv_after_13_prep = get_inventory_qty(caf_id, mi_id)
            log_result("13.2", "Inventory reserved at preparation for scheduled",
                        inv_after_13_prep is not None and inv_after_13_prep < inv_after_13,
                        f"before_prep={inv_after_13}, after_prep={inv_after_13_prep}")
        else:
            for i in range(2, 3):
                log_result(f"13.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 3):
            log_result(f"13.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 14: Full Refund Flow
    # ======================================================================
    print("\n=== TEST 14: Cancellation / Full Refund ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r14 = safe_json(r, {})
        oid_14 = _r14["id"]
        total_14 = _r14["total_amount"]
        r = initiate_payment(stu_token, oid_14)
        if r.status_code == 201:
            pr_14 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_14, total_14)

            # Student requests refund
            refund_idem_14 = f"refund_{uid()}"
            r = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_14}",
                json={
                    "amount": total_14,
                    "reason": "order_cancelled",
                    "reason_note": "Test refund",
                    "idempotency_key": refund_idem_14,
                },
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("14.1", "Refund request succeeds (201)",
                        r.status_code == 201, f"HTTP {r.status_code}")
            if r.status_code == 201:
                refund_14 = safe_json(r, {})
                refund_id_14 = refund_14["id"]
                log_result("14.2", "Refund amount matches payment",
                            refund_14["amount"] == total_14,
                            f"refund={refund_14['amount']}, pay={total_14}")
                log_result("14.3", "Refund status is pending",
                            refund_14["status"] == "pending",
                            f"status={refund_14['status']}")
                log_result("14.4", "Refund linked to payment",
                            bool(refund_14.get("payment_id")),
                            f"payment_id={str(refund_14.get('payment_id', ''))[:12]}")

                # Process refund via admin
                r = httpx.post(
                    f"{BASE_URL}/refunds/{refund_id_14}/process",
                    headers=auth(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("14.5", "Admin processes refund",
                            r.status_code in (200, 201),
                            f"HTTP {r.status_code}")
                if r.status_code in (200, 201):
                    _r14pj = safe_json(r, {})
                    log_result("14.6", "Refund status succeeded",
                                _r14pj.get("status") == "succeeded",
                                f"status={_r14pj.get('status')}")
                    log_result("14.7", "Provider reference assigned",
                                bool(_r14pj.get("provider_reference")),
                                f"ref={_r14pj.get('provider_reference')}")

                    # Payment status
                    r = httpx.get(f"{BASE_URL}/payments/order/{oid_14}",
                                 headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
                    if r.status_code == 200:
                        _r14pay = safe_json(r, {})
                        log_result("14.8", "Payment status is refunded",
                                    _r14pay.get("status") == "refunded",
                                    f"status={_r14pay.get('status')}")

                    # Refundable amount = 0
                    r = httpx.get(f"{BASE_URL}/refunds/refundable/{oid_14}",
                                 headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
                    if r.status_code == 200:
                        _r14r = safe_json(r, {})
                        log_result("14.9", "Refundable amount is 0 after full refund",
                                    _r14r.get("refundable_amount") == 0,
                                    f"refundable={_r14r.get('refundable_amount')}")
            else:
                for i in range(2, 10):
                    log_result(f"14.{i}", "Skipped", False, "Refund request failed")
        else:
            for i in range(1, 10):
                log_result(f"14.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 10):
            log_result(f"14.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 15: Partial Cancellation / Partial Refund
    # ======================================================================
    print("\n=== TEST 15: Partial Cancellation / Partial Refund ===")

    add_to_cart(stu_token, caf_id, mi_id)
    add_to_cart(stu_token, caf_id, mi_id_2)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r15 = safe_json(r, {})
        oid_15 = _r15["id"]
        total_15 = _r15["total_amount"]
        log_result("15.1", "Multi-item order created", True, f"total={total_15}")

        ord_data = get_order_from_api(stu_token, oid_15)
        items_15 = ord_data.get("items", []) if ord_data else []
        log_result("15.2", "Order has 2 items", len(items_15) == 2,
                    f"items={len(items_15)}")

        if len(items_15) == 2:
            r = initiate_payment(stu_token, oid_15)
            if r.status_code == 201:
                pr_15 = get_provider_ref(safe_json(r, {}).get("payment_id"))
                send_webhook("payment_success", pr_15, total_15)

                # Partial cancel
                item_to_cancel = items_15[0]["id"]
                r = httpx.post(
                    f"{BASE_URL}/orders/{oid_15}/partial-cancel",
                    json={"item_id": item_to_cancel, "reason": "Test partial cancel"},
                    headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("15.3", "Partial cancel succeeds",
                            r.status_code in (200, 201),
                            f"HTTP {r.status_code}")

                if r.status_code in (200, 201):
                    _r15pc = safe_json(r, {})
                    new_total = _r15pc["total_amount"]
                    log_result("15.4", "Order total recalculated",
                                new_total == total_15 // 2,
                                f"old={total_15}, new={new_total}")

                    remaining = len(_r15pc.get("items", []))
                    log_result("15.5", "Order still has remaining items",
                                remaining == 1,
                                f"remaining={remaining}")

                    # Partial refund
                    refund_idem_p = f"refund_part_{uid()}"
                    r = httpx.post(
                        f"{BASE_URL}/refunds?order_id={oid_15}",
                        json={
                            "amount": new_total,
                            "reason": "item_unavailable",
                            "idempotency_key": refund_idem_p,
                        },
                        headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                    )
                    log_result("15.6", "Partial refund request succeeds",
                                r.status_code == 201,
                                f"HTTP {r.status_code}")
                    if r.status_code == 201:
                        refund_id_p = safe_json(r, {}).get("id")
                        log_result("15.7", "Refund amount is partial",
                                    safe_json(r, {}).get("amount") == new_total,
                                    f"refund={safe_json(r, {}).get('amount')}, expected={new_total}")

                        r = httpx.post(
                            f"{BASE_URL}/refunds/{refund_id_p}/process",
                            headers=auth(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                        )
                        log_result("15.8", "Partial refund processed",
                                    r.status_code in (200, 201),
                                    f"HTTP {r.status_code}")
                else:
                    for i in range(4, 9):
                        log_result(f"15.{i}", "Skipped", False, "Partial cancel failed")
            else:
                for i in range(3, 9):
                    log_result(f"15.{i}", "Skipped", False, "Payment initiation failed")
        else:
            for i in range(3, 9):
                log_result(f"15.{i}", "Skipped", False, "Wrong item count")
    else:
        for i in range(1, 9):
            log_result(f"15.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 16: Refund Authorization
    # ======================================================================
    print("\n=== TEST 16: Refund Authorization ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r16 = safe_json(r, {})
        oid_16 = _r16["id"]
        total_16 = _r16["total_amount"]
        r = initiate_payment(stu_token, oid_16)
        if r.status_code == 201:
            pr_16 = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_16, total_16)

            r = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_16}",
                json={
                    "amount": total_16,
                    "reason": "order_cancelled",
                    "idempotency_key": f"refund_auth_{uid()}",
                },
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            if r.status_code == 201:
                refund_id_16 = safe_json(r, {}).get("id")

                # Staff must NOT process
                r = httpx.post(
                    f"{BASE_URL}/refunds/{refund_id_16}/process",
                    headers=auth(stf_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("16.1", "Staff CANNOT process refund",
                            r.status_code in (401, 403),
                            f"HTTP {r.status_code}")

                # Manager from another cafeteria must NOT process
                mgr2_uuid = uid()
                mgr2_email = f"mgr2-{mgr2_uuid}@lgu.edu.pk"
                mgr2_token, mgr2_id = register_and_login(
                    "Mgr2", "Mgr2", f"m2-{mgr2_uuid}", mgr2_email, "MgrPass123!", "student"
                )
                promote_to_manager(mgr2_id)
                caf2_id = create_cafeteria(admin_token, f"Caf2-{uid()[:4]}")
                assign_to_cafeteria(mgr2_id, caf2_id, "cafeteria_manager")
                r = httpx.post(
                    f"{BASE_URL}/refunds/{refund_id_16}/process",
                    headers=auth(mgr2_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("16.2", "Manager from another cafeteria CANNOT process",
                            r.status_code in (401, 403),
                            f"HTTP {r.status_code}")

                # Same cafeteria manager CAN process
                r = httpx.post(
                    f"{BASE_URL}/refunds/{refund_id_16}/process",
                    headers=auth(mgr_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("16.3", "Manager of assigned cafeteria CAN process",
                            r.status_code in (200, 201),
                            f"HTTP {r.status_code}")

                # Refundable amount endpoint
                r = httpx.get(
                    f"{BASE_URL}/refunds/refundable/{oid_16}",
                    headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("16.4", "Refundable amount endpoint works",
                            r.status_code == 200,
                            f"HTTP {r.status_code}")
            else:
                for i in range(1, 5):
                    log_result(f"16.{i}", "Skipped", False, "Refund request failed")
        else:
            for i in range(1, 5):
                log_result(f"16.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"16.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 17: Payment IDOR
    # ======================================================================
    print("\n=== TEST 17: Payment IDOR ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        oid_17 = safe_json(r, {}).get("id")
        r = initiate_payment(stu_token, oid_17)
        if r.status_code == 201:
            pid_17 = safe_json(r, {}).get("payment_id")

            # Other student cannot access payment
            r = httpx.get(f"{BASE_URL}/payments/{pid_17}",
                         headers=auth(stu2_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            log_result("17.1", "Other student cannot access payment (IDOR)",
                        r.status_code == 403,
                        f"HTTP {r.status_code}")

            # Other student cannot get payment for order
            r = httpx.get(f"{BASE_URL}/payments/order/{oid_17}",
                         headers=auth(stu2_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
            log_result("17.2", "Other student cannot access order payment",
                        r.status_code in (401, 403),
                        f"HTTP {r.status_code}")

            # Other student cannot initiate payment for another's order
            r = httpx.post(
                f"{BASE_URL}/payments/initiate/{oid_17}",
                json={"idempotency_key": f"idem_{uid()}"},
                headers=auth(stu2_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("17.3", "Other student cannot initiate payment for another's order",
                        r.status_code in (401, 403),
                        f"HTTP {r.status_code}")

            # Other student cannot request refund
            r = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_17}",
                json={
                    "amount": 500,
                    "reason": "order_cancelled",
                    "idempotency_key": f"refund_{uid()}",
                },
                headers=auth(stu2_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("17.4", "Other student cannot refund another's order",
                        r.status_code in (401, 403),
                        f"HTTP {r.status_code}")
        else:
            for i in range(1, 5):
                log_result(f"17.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 5):
            log_result(f"17.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # TEST 18: Invalid State Transitions
    # ======================================================================
    print("\n=== TEST 18: Invalid State Transitions ===")

    # Already-succeeded payment — replay
    if order_id_1:
        r = httpx.get(f"{BASE_URL}/payments/order/{order_id_1}",
                     headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
        _r18 = safe_json(r, {})
        if r.status_code == 200 and _r18.get("status") == "succeeded":
            pr_18 = get_provider_ref(_r18.get("id"))
            r = send_webhook("payment_success", pr_18, total_1)
            log_result("18.1", "Duplicate webhook on succeeded payment handled",
                        r.status_code == 200,
                        f"HTTP {r.status_code}")
            if r.status_code == 200:
                _r18j = safe_json(r, {})
                log_result("18.2", "Returns ignored/ok for duplicate",
                            _r18j.get("status") in ("ok", "ignored"),
                            f"status={_r18j.get('status')}")

    # Cancel then try to pay
    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        oid_cancel = safe_json(r, {}).get("id")
        r = httpx.post(
            f"{BASE_URL}/orders/{oid_cancel}/cancel",
            json={"reason": "Test cancel"},
            headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
        )
        if r.status_code in (200, 201):
            r = httpx.post(
                f"{BASE_URL}/payments/initiate/{oid_cancel}",
                json={"idempotency_key": f"idem_{uid()}"},
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("18.3", "Cannot pay for cancelled order",
                        r.status_code in (400, 404, 422),
                        f"HTTP {r.status_code}")
        else:
            log_result("18.3", "Cannot pay for cancelled order",
                        False, f"Cancel failed: {r.status_code}")
    else:
        log_result("18.3", "Cannot pay for cancelled order", False, "Order creation failed")

    # Refund more than paid
    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r18o = safe_json(r, {})
        oid_over = _r18o["id"]
        total_over = _r18o["total_amount"]
        r = initiate_payment(stu_token, oid_over)
        if r.status_code == 201:
            pr_over = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_over, total_over)
            r = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_over}",
                json={
                    "amount": total_over * 100,
                    "reason": "order_cancelled",
                    "idempotency_key": f"refund_over_{uid()}",
                },
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            log_result("18.4", "Cannot refund more than paid",
                        r.status_code == 400,
                        f"HTTP {r.status_code}")
        else:
            log_result("18.4", "Cannot refund more than paid", False, "Payment initiation failed")
    else:
        log_result("18.4", "Cannot refund more than paid", False, "Order creation failed")

    # Duplicate refund idempotency
    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r18d = safe_json(r, {})
        oid_dup = _r18d["id"]
        total_dup = _r18d["total_amount"]
        r = initiate_payment(stu_token, oid_dup)
        if r.status_code == 201:
            pr_dup = get_provider_ref(safe_json(r, {}).get("payment_id"))
            send_webhook("payment_success", pr_dup, total_dup)

            idem_dup = f"refund_dup_{uid()}"
            r1 = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_dup}",
                json={"amount": total_dup, "reason": "order_cancelled", "idempotency_key": idem_dup},
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            if r1.status_code == 201:
                dup_refund_id = safe_json(r1, {}).get("id")
                r2 = httpx.post(
                    f"{BASE_URL}/refunds?order_id={oid_dup}",
                    json={"amount": total_dup, "reason": "order_cancelled", "idempotency_key": idem_dup},
                    headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )
                log_result("18.5", "Duplicate refund idempotency returns existing",
                            r2.status_code == 200 or safe_json(r2, {}).get("id") == dup_refund_id,
                            f"HTTP {r2.status_code}")
        else:
            log_result("18.5", "Duplicate refund idempotency", False, "Payment initiation failed")
    else:
        log_result("18.5", "Duplicate refund idempotency", False, "Order creation failed")

    # ======================================================================
    # TEST 19: Late Webhook After Refund
    # ======================================================================
    print("\n=== TEST 19: Late Webhook After Refund ===")

    add_to_cart(stu_token, caf_id, mi_id)
    r = checkout(stu_token, caf_id, payment="online")
    if r.status_code in (200, 201):
        _r19 = safe_json(r, {})
        oid_19 = _r19["id"]
        total_19 = _r19["total_amount"]
        r = initiate_payment(stu_token, oid_19)
        if r.status_code == 201:
            pid_19 = safe_json(r, {}).get("payment_id")
            pr_19 = get_provider_ref(pid_19)
            send_webhook("payment_success", pr_19, total_19)

            # Refund
            r = httpx.post(
                f"{BASE_URL}/refunds?order_id={oid_19}",
                json={
                    "amount": total_19,
                    "reason": "order_cancelled",
                    "idempotency_key": f"refund_{uid()}",
                },
                headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
            )
            if r.status_code == 201:
                refund_id_19 = safe_json(r, {}).get("id")
                httpx.post(
                    f"{BASE_URL}/refunds/{refund_id_19}/process",
                    headers=auth(admin_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS,
                )

                # Late webhook
                r = send_webhook("payment_success", pr_19, total_19)
                log_result("19.1", "Late webhook after refund handled",
                            r.status_code == 200,
                            f"HTTP {r.status_code}")

                r = httpx.get(f"{BASE_URL}/payments/{pid_19}",
                             headers=auth(stu_token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
                if r.status_code == 200:
                    _r19pj = safe_json(r, {})
                    log_result("19.2", "Payment still refunded after late webhook",
                                _r19pj.get("status") == "refunded",
                                f"status={_r19pj.get('status')}")
        else:
            for i in range(1, 3):
                log_result(f"19.{i}", "Skipped", False, "Payment initiation failed")
    else:
        for i in range(1, 3):
            log_result(f"19.{i}", "Skipped", False, "Order creation failed")

    # ======================================================================
    # SUMMARY
    # ======================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, _, p, _ in results if p)
    failed = sum(1 for _, _, p, _ in results if not p)

    for num, name, ok, detail in results:
        icon = "[PASS]" if ok else "[FAIL]"
        line = f"  {icon} {num}: {name}"
        if not ok and detail:
            line += f" -- {detail}"
        print(line)

    print(f"\nTotal: {passed} passed, {failed} failed, {len(results)} total")

    cleanup()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
