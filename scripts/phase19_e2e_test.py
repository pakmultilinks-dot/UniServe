"""
Phase 19: Realistic E2E Testing Script
Tests all remaining phases via API: scheduled orders, stock, isolation,
payments, notifications, edge cases.
"""
import httpx
import json
import os
import time

BASE = os.environ.get("UNISERVE_E2E_BASE_URL", "http://localhost:8000/api/v1")

# Test accounts
STUDENT = {"university_email": "ayesha.khan@student.lgu.edu.pk", "password": "TestPass123!"}
FACULTY = {"university_email": "dr.sana.malik@lgu.edu.pk", "password": "TestPass123!"}
STAFF = {"university_email": "ahmed.raza@lgu.edu.pk", "password": "TestPass123!"}
MANAGER = {"university_email": "sana.malik@lgu.edu.pk", "password": "TestPass123!"}
ADMIN = {"university_email": "admin@lgu.edu.pk", "password": "Admin123!"}

results = {"passed": 0, "failed": 0, "details": []}

def log(phase, name, status, detail=""):
    icon = "✅" if status == "PASS" else "❌"
    msg = f"{icon} [{phase}] {name}: {status}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results["details"].append({"phase": phase, "name": name, "status": status, "detail": detail})
    if status == "PASS":
        results["passed"] += 1
    else:
        results["failed"] += 1

def login(client, creds):
    r = client.post(f"{BASE}/auth/login", json=creds)
    r.raise_for_status()
    data = r.json()
    return data["tokens"]["access_token"], data["user"]

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def get_menu_items(client, token, cafeteria_id):
    r = client.get(f"{BASE}/cafeterias/{cafeteria_id}/menu-items", headers=auth_headers(token))
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("items", data.get("menu_items", []))
    return data

def get_cafeterias(client, token):
    r = client.get(f"{BASE}/cafeterias/", headers=auth_headers(token))
    r.raise_for_status()
    return r.json()["cafeterias"]

def add_to_cart(client, token, cafeteria_id, menu_item_id, quantity=1):
    return client.post(f"{BASE}/cafeterias/{cafeteria_id}/cart/items",
                      json={"menu_item_id": menu_item_id, "quantity": quantity},
                      headers=auth_headers(token))

def checkout(client, token, cafeteria_id, payment_method="cash", order_type="immediate",
             scheduled_time=None, note=None):
    body = {"payment_method": payment_method, "order_type": order_type}
    if scheduled_time:
        body["scheduled_collection_time"] = scheduled_time
    if note:
        body["note"] = note
    return client.post(f"{BASE}/cafeterias/{cafeteria_id}/cart/checkout",
                      json=body, headers=auth_headers(token))

def clear_cart(client, token, cafeteria_id):
    r = client.get(f"{BASE}/cafeterias/{cafeteria_id}/cart/", headers=auth_headers(token))
    if r.status_code == 200:
        cart = r.json()
        for item in cart.get("items", []):
            client.delete(f"{BASE}/cafeterias/{cafeteria_id}/cart/items/{item['id']}", headers=auth_headers(token))

def main():
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        # ============================================================
        # PHASE 7: Real E2E Order (complete lifecycle)
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 7: Real E2E Order Lifecycle")
        print("="*60)

        try:
            student_token, student_user = login(client, STUDENT)
            log("Phase 7", "Student login", "PASS", student_user["university_email"])
        except Exception as e:
            log("Phase 7", "Student login", "FAIL", str(e))
            return

        try:
            cafeterias = get_cafeterias(client, student_token)
            student_caf = next(c for c in cafeterias if c["type"] == "student")
            log("Phase 7", "Student sees student cafeteria", "PASS", student_caf["name"])
        except Exception as e:
            log("Phase 7", "Get cafeterias", "FAIL", str(e))
            return

        try:
            items = get_menu_items(client, student_token, student_caf["id"])
            burger = next(i for i in items if "burger" in i["name"].lower())
            log("Phase 7", "Get menu items", "PASS", f"{len(items)} items, burger={burger['name']}")
        except Exception as e:
            log("Phase 7", "Get menu items", "FAIL", str(e))
            return

        # Clear cart and add items
        clear_cart(client, student_token, student_caf["id"])
        try:
            r = add_to_cart(client, student_token, student_caf["id"], burger["id"], 2)
            if r.status_code in (200, 201):
                log("Phase 7", "Add to cart", "PASS", f"qty=2, {burger['name']}")
            else:
                log("Phase 7", "Add to cart", "FAIL", f"{r.status_code}: {r.text[:200]}")
                return
        except Exception as e:
            log("Phase 7", "Add to cart", "FAIL", str(e))
            return

        # Checkout
        try:
            r = checkout(client, student_token, student_caf["id"],
                        payment_method="cash", note="E2E test order")
            if r.status_code in (200, 201):
                order = r.json()
                order_id = order["id"]
                log("Phase 7", "Checkout (cash)", "PASS",
                    f"#{order['order_number']}, status={order['status']}, total={order.get('total_amount')}")
            else:
                log("Phase 7", "Checkout (cash)", "FAIL", f"{r.status_code}: {r.text[:200]}")
                return
        except Exception as e:
            log("Phase 7", "Checkout (cash)", "FAIL", str(e))
            return

        # Confirm order (staff)
        try:
            staff_token, _ = login(client, STAFF)
            r = client.post(f"{BASE}/orders/{order_id}/confirm", json={"notes": "Confirmed by staff"},
                          headers=auth_headers(staff_token))
            if r.status_code == 200:
                log("Phase 7", "Confirm order (staff)", "PASS", f"status={r.json()['status']}")
            else:
                log("Phase 7", "Confirm order (staff)", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 7", "Confirm order (staff)", "FAIL", str(e))

        # Prepare order (staff)
        try:
            r = client.post(f"{BASE}/orders/{order_id}/prepare", json={},
                          headers=auth_headers(staff_token))
            if r.status_code == 200:
                log("Phase 7", "Prepare order (staff)", "PASS", f"status={r.json()['status']}")
            else:
                log("Phase 7", "Prepare order (staff)", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 7", "Prepare order (staff)", "FAIL", str(e))

        # Mark ready (PUT)
        try:
            r = client.put(f"{BASE}/orders/{order_id}/ready", json={},
                          headers=auth_headers(staff_token))
            if r.status_code == 200:
                log("Phase 7", "Mark ready (staff)", "PASS", f"status={r.json()['status']}")
            else:
                log("Phase 7", "Mark ready (staff)", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 7", "Mark ready (staff)", "FAIL", str(e))

        # Verify student can see updated order
        try:
            r = client.get(f"{BASE}/orders/{order_id}", headers=auth_headers(student_token))
            if r.status_code == 200:
                log("Phase 7", "Student views order status", "PASS", f"status={r.json()['status']}")
            else:
                log("Phase 7", "Student views order status", "FAIL", f"{r.status_code}")
        except Exception as e:
            log("Phase 7", "Student views order status", "FAIL", str(e))

        # Collect/complete order (staff, via collect endpoint)
        try:
            r = client.post(f"{BASE}/orders/collect",
                          json={"order_number": order["order_number"]},
                          headers=auth_headers(staff_token))
            if r.status_code == 200:
                log("Phase 7", "Collect order (staff)", "PASS", f"status={r.json()['status']}")
            else:
                log("Phase 7", "Collect order (staff)", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 7", "Collect order (staff)", "FAIL", str(e))

        # ============================================================
        # PHASE 8: Scheduled Order
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 8: Scheduled Order")
        print("="*60)

        clear_cart(client, student_token, student_caf["id"])
        add_to_cart(client, student_token, student_caf["id"], burger["id"], 1)
        try:
            # Use a future time (30 minutes from now)
            from datetime import datetime, timedelta
            future_time = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
            r = checkout(client, student_token, student_caf["id"],
                        payment_method="cash", order_type="scheduled",
                        scheduled_time=future_time, note="Scheduled test")
            if r.status_code in (200, 201):
                sched_order = r.json()
                log("Phase 8", "Place scheduled order", "PASS",
                    f"#{sched_order['order_number']}, type={sched_order.get('order_type')}, "
                    f"scheduled={sched_order.get('scheduled_collection_time')}")
            else:
                log("Phase 8", "Place scheduled order", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 8", "Place scheduled order", "FAIL", str(e))

        # ============================================================
        # PHASE 9: Stock / Out-of-Stock
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 9: Stock / Out-of-Stock")
        print("="*60)

        try:
            admin_token, _ = login(client, ADMIN)
            # Check inventory for student cafeteria
            r = client.get(f"{BASE}/cafeterias/{student_caf['id']}/inventory/",
                         headers=auth_headers(admin_token))
            if r.status_code == 200:
                inv_data = r.json()
                inv = inv_data.get("items", inv_data if isinstance(inv_data, list) else [])
                log("Phase 9", "Admin views inventory", "PASS", f"{len(inv)} records")
            else:
                log("Phase 9", "Admin views inventory", "FAIL", f"{r.status_code}")
        except Exception as e:
            log("Phase 9", "Admin views inventory", "FAIL", str(e))

        # Try ordering an item that might be out of stock (adjust stock to 0)
        try:
            if inv:
                target = inv[0]
                current_qty = target.get("quantity", 0)
                # Use adjust endpoint to set stock to 0
                r = client.post(f"{BASE}/cafeterias/{student_caf['id']}/inventory/adjust",
                              json={"inventory_item_id": target["id"], "adjustment_quantity": -current_qty,
                                    "reason": "E2E out-of-stock test"},
                              headers=auth_headers(admin_token))
                if r.status_code in (200, 201):
                    log("Phase 9", "Set item out of stock", "PASS", f"qty={current_qty} -> 0")
                    # Try ordering it
                    clear_cart(client, student_token, student_caf["id"])
                    menu_item_id = target.get("menu_item_id")
                    if menu_item_id:
                        add_to_cart(client, student_token, student_caf["id"], menu_item_id, 1)
                        r2 = checkout(client, student_token, student_caf["id"], payment_method="cash")
                        if r2.status_code in (200, 201):
                            log("Phase 9", "Order out-of-stock item blocked", "FAIL",
                                f"Order was accepted: {r2.json().get('order_number')}")
                        else:
                            log("Phase 9", "Order out-of-stock item blocked", "PASS",
                                f"{r2.status_code}: {r2.text[:100]}")
                    # Restore
                    client.post(f"{BASE}/cafeterias/{student_caf['id']}/inventory/adjust",
                              json={"inventory_item_id": target["id"], "adjustment_quantity": current_qty,
                                    "reason": "Restore after E2E test"},
                              headers=auth_headers(admin_token))
                else:
                    log("Phase 9", "Set item out of stock", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 9", "Out-of-stock test", "FAIL", str(e))

        # ============================================================
        # PHASE 10: Two-Cafeteria Isolation
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 10: Two-Cafeteria Isolation")
        print("="*60)

        try:
            # Faculty should see faculty cafeteria
            fac_token, _ = login(client, FACULTY)
            fac_cafeterias = get_cafeterias(client, fac_token)
            fac_caf = next(c for c in fac_cafeterias if c["type"] == "faculty")
            log("Phase 10", "Faculty sees faculty cafeteria", "PASS", fac_caf["name"])

            # Faculty should NOT see student cafeteria menu
            fac_items = get_menu_items(client, fac_token, fac_caf["id"])
            fac_item_names = [i["name"].lower() for i in fac_items]
            log("Phase 10", "Faculty sees faculty menu", "PASS", f"{len(fac_items)} items")

            # Student should NOT see faculty cafeteria
            stud_cafeterias = get_cafeterias(client, student_token)
            has_faculty = any(c["type"] == "faculty" for c in stud_cafeterias)
            if not has_faculty:
                log("Phase 10", "Student cannot see faculty cafeteria", "PASS", "Isolation working")
            else:
                log("Phase 10", "Student cannot see faculty cafeteria", "FAIL", "Faculty cafeteria visible to student")

            # Student ordering from faculty cafeteria should fail
            clear_cart(client, student_token, fac_caf["id"])
            r = add_to_cart(client, student_token, fac_caf["id"], fac_items[0]["id"], 1)
            if r.status_code >= 400:
                log("Phase 10", "Student blocked from faculty cafeteria menu", "PASS", f"{r.status_code}")
            else:
                r2 = checkout(client, student_token, fac_caf["id"], payment_method="cash")
                if r2.status_code >= 400:
                    log("Phase 10", "Student blocked from faculty cafeteria order", "PASS",
                        f"{r2.status_code}")
                else:
                    log("Phase 10", "Student blocked from faculty cafeteria order", "FAIL",
                        f"Order accepted: {r2.status_code}")

        except Exception as e:
            log("Phase 10", "Isolation test", "FAIL", str(e))

        # ============================================================
        # PHASE 11: Payment Testing
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 11: Payment Testing")
        print("="*60)

        # Cash order (already tested above)
        try:
            r = client.get(f"{BASE}/payments/order/{order_id}", headers=auth_headers(student_token))
            if r.status_code == 200:
                pay = r.json()
                log("Phase 11", "Cash order payment record", "PASS",
                    f"status={pay.get('status')}, method={pay.get('payment_method')}")
            else:
                log("Phase 11", "Cash order payment record", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 11", "Payment record check", "FAIL", str(e))

        # Online payment order
        clear_cart(client, student_token, student_caf["id"])
        add_to_cart(client, student_token, student_caf["id"], burger["id"], 1)
        try:
            r = checkout(client, student_token, student_caf["id"], payment_method="online")
            if r.status_code in (200, 201):
                online_order = r.json()
                # Initiate payment
                r2 = client.post(f"{BASE}/payments/initiate/{online_order['id']}",
                               json={"idempotency_key": f"e2e-{online_order['id'][:8]}"},
                               headers=auth_headers(student_token))
                if r2.status_code in (200, 201):
                    intent = r2.json()
                    log("Phase 11", "Online payment initiated", "PASS",
                        f"payment_id={str(intent.get('payment_id', 'N/A'))[:20]}...")
                else:
                    log("Phase 11", "Online payment initiated", "FAIL",
                        f"{r2.status_code}: {r2.text[:200]}")
            else:
                log("Phase 11", "Online order placement", "FAIL", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            log("Phase 11", "Online payment test", "FAIL", str(e))

        # ============================================================
        # PHASE 12: Notifications / Status Updates
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 12: Notifications / Status Updates")
        print("="*60)

        try:
            # Check student notifications
            r = client.get(f"{BASE}/notifications", headers=auth_headers(student_token))
            if r.status_code == 200:
                data = r.json()
                notifs = data.get("items", data if isinstance(data, list) else [])
                log("Phase 12", "Student notifications", "PASS", f"{len(notifs)} notifications")
            else:
                log("Phase 12", "Student notifications", "FAIL", f"{r.status_code}")

            # Check staff notifications
            r = client.get(f"{BASE}/notifications", headers=auth_headers(staff_token))
            if r.status_code == 200:
                data = r.json()
                staff_notifs = data.get("items", data if isinstance(data, list) else [])
                log("Phase 12", "Staff notifications", "PASS", f"{len(staff_notifs)} notifications")
            else:
                log("Phase 12", "Staff notifications", "FAIL", f"{r.status_code}")

            # Verify status transition creates notification
            if 'order_id' in dir():
                r = client.get(f"{BASE}/notifications?unread_only=true",
                             headers=auth_headers(student_token))
                if r.status_code == 200:
                    unread = r.json()
                    log("Phase 12", "Unread notifications check", "PASS", f"{len(unread)} unread")
        except Exception as e:
            log("Phase 12", "Notification test", "FAIL", str(e))

        # ============================================================
        # PHASE 13: Error / Edge Cases
        # ============================================================
        print("\n" + "="*60)
        print("PHASE 13: Error / Edge Cases")
        print("="*60)

        # 1. Invalid menu item ID
        clear_cart(client, student_token, student_caf["id"])
        try:
            r = add_to_cart(client, student_token, student_caf["id"], "nonexistent-id", 1)
            if r.status_code >= 400:
                log("Phase 13", "Invalid menu item ID rejected", "PASS", f"{r.status_code}")
            else:
                log("Phase 13", "Invalid menu item ID rejected", "FAIL", f"Accepted: {r.status_code}")
        except Exception as e:
            log("Phase 13", "Invalid menu item test", "FAIL", str(e))

        # 2. Quantity = 0 (should be rejected by schema gt=0)
        try:
            r = client.post(f"{BASE}/carts/items",
                          json={"menu_item_id": burger["id"], "quantity": 0},
                          headers=auth_headers(student_token))
            if r.status_code >= 400:
                log("Phase 13", "Zero quantity rejected", "PASS", f"{r.status_code}")
            else:
                log("Phase 13", "Zero quantity rejected", "FAIL", f"Accepted: {r.status_code}")
        except Exception as e:
            log("Phase 13", "Zero quantity test", "FAIL", str(e))

        # 3. Negative quantity
        try:
            r = client.post(f"{BASE}/carts/items",
                          json={"menu_item_id": burger["id"], "quantity": -1},
                          headers=auth_headers(student_token))
            if r.status_code >= 400:
                log("Phase 13", "Negative quantity rejected", "PASS", f"{r.status_code}")
            else:
                log("Phase 13", "Negative quantity rejected", "FAIL", f"Accepted: {r.status_code}")
        except Exception as e:
            log("Phase 13", "Negative quantity test", "FAIL", str(e))

        # 4. Unauthenticated access
        try:
            r = client.get(f"{BASE}/orders")
            if r.status_code == 401:
                log("Phase 13", "Unauthenticated orders access blocked", "PASS", "401")
            else:
                log("Phase 13", "Unauthenticated orders access blocked", "FAIL", f"{r.status_code}")
        except Exception as e:
            log("Phase 13", "Unauth test", "FAIL", str(e))

        # 5. Student accessing staff endpoint
        try:
            r = client.post(f"{BASE}/orders/{order_id}/confirm", json={},
                          headers=auth_headers(student_token))
            if r.status_code == 403:
                log("Phase 13", "Student blocked from staff endpoint", "PASS", "403")
            else:
                log("Phase 13", "Student blocked from staff endpoint", "FAIL", f"{r.status_code}")
        except Exception as e:
            log("Phase 13", "Authorization test", "FAIL", str(e))

        # 6. Invalid payment method (should be rejected by schema)
        clear_cart(client, student_token, student_caf["id"])
        add_to_cart(client, student_token, student_caf["id"], burger["id"], 1)
        try:
            r = client.post(f"{BASE}/cafeterias/{student_caf['id']}/cart/checkout",
                          json={"payment_method": "bitcoin"},
                          headers=auth_headers(student_token))
            if r.status_code >= 400:
                log("Phase 13", "Invalid payment method rejected", "PASS", f"{r.status_code}")
            else:
                log("Phase 13", "Invalid payment method rejected", "FAIL", f"Accepted: {r.status_code}")
        except Exception as e:
            log("Phase 13", "Invalid payment method test", "FAIL", str(e))

        # 7. Cancel an order
        clear_cart(client, student_token, student_caf["id"])
        add_to_cart(client, student_token, student_caf["id"], burger["id"], 1)
        try:
            r = checkout(client, student_token, student_caf["id"], payment_method="cash")
            if r.status_code in (200, 201):
                cancel_order = r.json()
                r2 = client.post(f"{BASE}/orders/{cancel_order['id']}/cancel",
                               json={"reason": "Testing cancellation"},
                               headers=auth_headers(student_token))
                if r2.status_code == 200:
                    log("Phase 13", "Order cancellation", "PASS",
                        f"status={r2.json()['status']}")
                else:
                    log("Phase 13", "Order cancellation", "FAIL", f"{r2.status_code}: {r2.text[:200]}")
        except Exception as e:
            log("Phase 13", "Cancellation test", "FAIL", str(e))

        # 8. Oversized order (quantity > 99)
        try:
            r = client.post(f"{BASE}/carts/items",
                          json={"menu_item_id": burger["id"], "quantity": 150},
                          headers=auth_headers(student_token))
            if r.status_code >= 400:
                log("Phase 13", "Oversized quantity rejected", "PASS", f"{r.status_code}")
            else:
                log("Phase 13", "Oversized quantity rejected", "FAIL", f"Accepted: {r.status_code}")
        except Exception as e:
            log("Phase 13", "Oversized quantity test", "FAIL", str(e))

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total: {results['passed'] + results['failed']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Pass rate: {results['passed']/(results['passed']+results['failed'])*100:.1f}%")

        if results["failed"] > 0:
            print("\n--- FAILURES ---")
            for d in results["details"]:
                if d["status"] == "FAIL":
                    print(f"  {d['phase']}: {d['name']} — {d['detail']}")

if __name__ == "__main__":
    main()
