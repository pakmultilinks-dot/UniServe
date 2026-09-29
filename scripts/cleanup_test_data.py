#!/usr/bin/env python3
"""
Phase 17: DB cleanup — remove LIVE-* test users, test orders, and test registrations.
Preserves original data. Uses raw SQL via docker exec.
"""
import subprocess
import sys

def psql(sql):
    """Execute SQL via docker exec."""
    r = subprocess.run(
        ["docker", "exec", "uniserve_postgres", "psql", "-U", "uniserve", "-d", "uniserve_dev", "-c", sql],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  SQL ERROR: {r.stderr.strip()}")
    return r.stdout.strip()

print("=" * 70)
print("PHASE 17: DB CLEANUP")
print("=" * 70)

# 1. Check current LIVE test users
print("\n--- Step 1: Identify LIVE test users ---")
users = psql("SELECT id, university_email, role FROM users WHERE university_email LIKE 'live.%' ORDER BY university_email;")
print(users)

# 2. Delete test orders from LIVE users
print("\n--- Step 2: Delete test orders ---")
result = psql("""
DELETE FROM order_items WHERE order_id IN (
    SELECT id FROM orders WHERE user_id IN (
        SELECT id FROM users WHERE university_email LIKE 'live.%'
    )
);
""")
print(f"  order_items: {result}")

result = psql("""
DELETE FROM order_events WHERE order_id IN (
    SELECT id FROM orders WHERE user_id IN (
        SELECT id FROM users WHERE university_email LIKE 'live.%'
    )
);
""")
print(f"  order_events: {result}")

result = psql("""
DELETE FROM orders WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  orders: {result}")

# 3. Delete test registrations
print("\n--- Step 3: Delete test registrations ---")
result = psql("DELETE FROM registrations WHERE university_email LIKE 'live.%';")
print(f"  registrations: {result}")

# 4. Delete test refund records
print("\n--- Step 4: Delete test refunds ---")
result = psql("""
DELETE FROM refund_events WHERE refund_id IN (
    SELECT id FROM refunds WHERE order_id IN (
        SELECT id FROM orders WHERE user_id IN (
            SELECT id FROM users WHERE university_email LIKE 'live.%'
        )
    )
);
""")
print(f"  refund_events: {result}")

result = psql("""
DELETE FROM refunds WHERE order_id IN (
    SELECT id FROM orders WHERE user_id IN (
        SELECT id FROM users WHERE university_email LIKE 'live.%'
    )
);
""")
print(f"  refunds: {result}")

# 5. Delete carts from LIVE users
print("\n--- Step 5: Delete test carts ---")
result = psql("""
DELETE FROM cart_items WHERE cart_id IN (
    SELECT id FROM carts WHERE user_id IN (
        SELECT id FROM users WHERE university_email LIKE 'live.%'
    )
);
""")
print(f"  cart_items: {result}")

result = psql("""
DELETE FROM carts WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  carts: {result}")

# 6. Delete notifications for LIVE users
print("\n--- Step 6: Delete test notifications ---")
result = psql("""
DELETE FROM notifications WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  notifications: {result}")

# 7. Delete favorites for LIVE users
print("\n--- Step 7: Delete test favorites ---")
result = psql("""
DELETE FROM favorites WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  favorites: {result}")

# 8. Delete refresh tokens for LIVE users
print("\n--- Step 8: Delete test sessions ---")
result = psql("""
DELETE FROM refresh_tokens WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  refresh_tokens: {result}")

# 9. Delete cafeteria assignments for LIVE users
print("\n--- Step 9: Delete test cafeteria assignments ---")
result = psql("""
DELETE FROM cafeteria_assignments WHERE user_id IN (
    SELECT id FROM users WHERE university_email LIKE 'live.%'
);
""")
print(f"  cafeteria_assignments: {result}")

# 10. Delete LIVE test users
print("\n--- Step 10: Delete test users ---")
result = psql("DELETE FROM users WHERE university_email LIKE 'live.%';")
print(f"  users: {result}")

# 11. Verify cleanup
print("\n--- Step 11: Verify cleanup ---")
remaining = psql("SELECT count(*) as live_users FROM users WHERE university_email LIKE 'live.%';")
print(f"  LIVE users remaining: {remaining}")

remaining_orders = psql("""
SELECT count(*) as test_orders FROM orders WHERE user_id IS NOT NULL AND user_id NOT IN (
    SELECT id FROM users WHERE university_email NOT LIKE 'live.%'
);
""")
print(f"  Test-related orders: {remaining_orders}")

# 12. Show final user count
total = psql("SELECT count(*) as total_users FROM users;")
print(f"  Total users: {total}")

print("\n" + "=" * 70)
print("CLEANUP COMPLETE")
print("=" * 70)
