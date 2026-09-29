#!/usr/bin/env python3
"""IDOR test: Create an order as Student A and verify Student B cannot access it."""

import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"

def api(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def login(email, password):
    s, b = api("POST", "/auth/login", body={"university_email": email, "password": password})
    return b["tokens"]["access_token"] if s == 200 else None

# Login as Student A and B
tA = login("live.stu.alpha@lgu.edu.pk", "TestPass123!")
tB = login("live.stu.beta@lgu.edu.pk", "TestPass123!")
print(f"Student A token: {'OK' if tA else 'FAIL'}")
print(f"Student B token: {'OK' if tB else 'FAIL'}")

STUDENT_CAF = "205e8c71-7b9c-4a04-a40b-8f5ca8344bf2"

# Get menu items
s, menu = api("GET", f"/cafeterias/{STUDENT_CAF}/menu-items", tA)
items = menu.get("items", [])
print(f"Menu items: {len(items)}")

if not items:
    print("No menu items available")
    exit(1)

item_id = items[0]["id"]
print(f"Using item: {items[0]['name']} ({item_id})")

# Add to cart (cart is scoped under /cafeterias/{cafeteria_id}/cart)
s, cart = api("POST", f"/cafeterias/{STUDENT_CAF}/cart/items", tA, {"menu_item_id": item_id, "quantity": 1})
print(f"Cart add: {s} {json.dumps(cart)[:200]}")

# Checkout (also scoped under cafeteria)
s, order = api("POST", f"/cafeterias/{STUDENT_CAF}/cart/checkout", tA, {"payment_method": "cash"})
print(f"Checkout: {s} {json.dumps(order)[:200]}")

if s not in (200, 201):
    print(f"Checkout failed, checking cart...")
    s, cart_info = api("GET", f"/cafeterias/{STUDENT_CAF}/cart/", tA)
    print(f"Cart info: {s} {json.dumps(cart_info)[:200]}")
    exit(1)

# Get orders
s, orders_resp = api("GET", "/orders/", tA)
if isinstance(orders_resp, dict):
    orders = orders_resp.get("orders", [])
elif isinstance(orders_resp, list):
    orders = orders_resp
else:
    orders = []
print(f"Student A orders: {len(orders)}")

if not orders:
    print("No orders created")
    exit(1)

order_id = orders[0]["id"]
print(f"\nOrder ID: {order_id}")

# IDOR Test: Student B tries to access Student A's order ETA
s, eta = api("GET", f"/orders/{order_id}/eta", tB)
print(f"\n=== IDOR TEST ===")
print(f"Student B -> Student A ETA: {s} {'BLOCKED (403)' if s == 403 else 'ALLOWED (BUG!)' if s == 200 else f'OTHER: {eta}'}")

# Legitimate: Student A accesses own order ETA
s, eta = api("GET", f"/orders/{order_id}/eta", tA)
print(f"Student A -> own ETA: {s} {'OK (200)' if s == 200 else f'OTHER: {eta}'}")

# Cancel as Student A
s, cancel = api("POST", f"/orders/{order_id}/cancel", tA)
print(f"Student A cancel own order: {s}")

# Faculty cafeteria IDOR: Student tries to access faculty cafeteria orders
s, resp = api("GET", f"/orders/cafeteria/f47ac10b-58cc-4372-a567-0e02b2c3d479", tA)
print(f"\nStudent -> Faculty cafeteria orders: {s} {'BLOCKED' if s == 403 else 'BUG!'}")

print("\n=== IDOR TEST COMPLETE ===")
