"""Phase 7 Live IDOR Attack Test — verify GET /orders/{order_id} authorization fix.

Runs against the live API server at http://127.0.0.1:8001 with real PostgreSQL.
Tests 5 scenarios proving the IDOR fix works.

NOTE: Newly registered users require email OTP verification before login.
      This script auto-verifies users via direct DB update (dev environment only).
"""

import httpx
import subprocess
import sys
import uuid
import time

BASE_URL = "http://127.0.0.1:8001/api/v1"
FOLLOW_REDIRECTS = True
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_dev"


# ── Helpers ──────────────────────────────────────────────────────────

def unique_id():
    return uuid.uuid4().hex[:8]


def verify_user_via_db(user_id):
    """Mark a user as email-verified in the dev database (dev environment only)."""
    cmd = (
        f"docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} -c "
        f"\"UPDATE users SET email_verified = true, status = 'active' "
        f"WHERE id = '{user_id}' AND email_verified = false;\""
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f"    DB verify failed: {result.stderr.strip()}")
        return False
    return True


def register_and_verify(first_name, last_name, uni_id, email, password, category=None):
    """Register a user and auto-verify email via DB (dev-only)."""
    body = {
        "first_name": first_name,
        "last_name": last_name,
        "university_id": uni_id,
        "university_email": email,
        "password": password,
    }
    if category:
        body["selected_category"] = category
    r = httpx.post(f"{BASE_URL}/auth/register", json=body, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code != 201:
        print(f"    Registration failed: {r.status_code} {r.text[:100]}")
        return None

    resp = r.json()
    user_id = resp.get("user_id")
    if not user_id:
        print(f"    No user_id in response")
        return None

    if not verify_user_via_db(user_id):
        return None

    return user_id


def login(email, password):
    r = httpx.post(f"{BASE_URL}/auth/login", json={
        "university_email": email,
        "password": password,
    }, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code == 200:
        return r.json()["tokens"]["access_token"]
    else:
        print(f"    Login failed: {r.status_code} {r.text[:200]}")
        return None


def auth_header(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def get_menu_items(token, cafeteria_id):
    r = httpx.get(f"{BASE_URL}/cafeterias/{cafeteria_id}/menu-items",
                  headers=auth_header(token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    items = []
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict):
            items = data.get("items", data.get("menu_items", []))
        elif isinstance(data, list):
            items = data
    return items


def create_order(token, cafeteria_id, menu_item_id):
    h = auth_header(token)
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/items",
                   json={"menu_item_id": menu_item_id, "quantity": 1},
                   headers=h, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code not in (200, 201):
        print(f"    Cart add failed: {r.status_code} {r.text[:200]}")
        return None
    r = httpx.post(f"{BASE_URL}/cafeterias/{cafeteria_id}/cart/checkout",
                   json={"payment_method": "cash", "order_type": "immediate"},
                   headers=h, timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code in (200, 201):
        return r.json()["id"]
    else:
        print(f"    Checkout failed: {r.status_code} {r.text[:200]}")
        return None


def get_order(token, order_id):
    r = httpx.get(f"{BASE_URL}/orders/{order_id}",
                  headers=auth_header(token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    return r.status_code, r.json()


# ── Common setup ─────────────────────────────────────────────────────

def _setup(suffix):
    """Register user, verify email, login, get cafeteria + item.
    Returns (token, caf_id, item_id) or None.
    """
    user_id = register_and_verify("Test", "User", f"FA22-BSE-{suffix}",
                                  f"test_{suffix}@lgu.edu.pk", "TestPass123!",
                                  "student")
    if not user_id:
        print(f"    Registration/verification failed")
        return None
    token = login(f"test_{suffix}@lgu.edu.pk", "TestPass123!")
    if not token:
        return None
    r = httpx.get(f"{BASE_URL}/cafeterias", headers=auth_header(token), timeout=30, follow_redirects=FOLLOW_REDIRECTS)
    if r.status_code != 200:
        print(f"    Cafeterias request failed: {r.status_code}")
        return None
    caf_list = r.json().get("cafeterias", r.json()) if isinstance(r.json(), dict) else r.json()
    if not caf_list:
        print(f"    No cafeterias available")
        return None
    caf_id = caf_list[0]["id"]
    items = get_menu_items(token, caf_id)
    if not items:
        print(f"    No menu items")
        return None
    return token, caf_id, items[0]["id"]


# ── Test runner ──────────────────────────────────────────────────────

results = []

def run_test(name, test_fn):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        passed, detail = test_fn()
        results.append((name, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"  Result: {status} — {detail}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  Result: FAIL — Exception: {e}")


# ── Live IDOR Attack Tests ──────────────────────────────────────────

def test_owner_access():
    """Test A: Owner can access their own order."""
    s = _setup(unique_id())
    if not s:
        return False, "Setup failed"
    token, caf_id, item_id = s
    order_id = create_order(token, caf_id, item_id)
    if not order_id:
        return False, "Failed to create order"
    code, resp = get_order(token, order_id)
    if code == 200 and resp.get("id") == order_id:
        return True, f"Owner got 200 with correct order (id={order_id[:8]}...)"
    return False, f"Expected 200, got {code}: {str(resp)[:200]}"


def test_different_user_blocked():
    """Test B: Different student cannot access another user's order."""
    s_owner = _setup(unique_id())
    if not s_owner:
        return False, "Owner setup failed"
    token_owner, caf_id, item_id = s_owner
    order_id = create_order(token_owner, caf_id, item_id)
    if not order_id:
        return False, "Failed to create order"

    s_attacker = _setup(unique_id())
    if not s_attacker:
        return False, "Attacker setup failed"
    token_attacker = s_attacker[0]
    code, resp = get_order(token_attacker, order_id)
    if code == 403:
        return True, f"Attacker got 403 (denied) — IDOR blocked"
    elif code == 404:
        return True, f"Attacker got 404 (hidden) — IDOR mitigated"
    return False, f"Expected 403/404, got {code}: {str(resp)[:200]}"


def test_unauthenticated_blocked():
    """Test C: Unauthenticated request is rejected."""
    s = _setup(unique_id())
    if not s:
        return False, "Setup failed"
    token, caf_id, item_id = s
    order_id = create_order(token, caf_id, item_id)
    if not order_id:
        return False, "Failed to create order"

    code, resp = get_order(None, order_id)
    if code in (401, 403, 422):
        return True, f"Unauthenticated got {code} (denied)"
    return False, f"Expected 401/403/422, got {code}: {str(resp)[:200]}"


def test_nonexistent_order():
    """Test D: Nonexistent order returns 404."""
    s = _setup(unique_id())
    if not s:
        return False, "Setup failed"
    token = s[0]
    code, resp = get_order(token, "00000000-0000-0000-0000-000000000000")
    if code == 404:
        return True, "Nonexistent order returned 404"
    return False, f"Expected 404, got {code}: {str(resp)[:200]}"


def test_uuid_substitution():
    """Test E: Primary IDOR attack — User B guesses User A's order UUID."""
    s_a = _setup(unique_id())
    if not s_a:
        return False, "User A setup failed"
    token_a, caf_id, item_id = s_a
    order_a = create_order(token_a, caf_id, item_id)
    if not order_a:
        return False, "Failed to create order A"

    s_b = _setup(unique_id())
    if not s_b:
        return False, "User B setup failed"
    token_b = s_b[0]
    code, resp = get_order(token_b, order_a)
    if code in (403, 404):
        return True, f"UUID substitution blocked — got {code}"
    return False, f"Expected 403/404, got {code}: {str(resp)[:200]}"


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("UNISERVE — LIVE IDOR ATTACK TEST (Phase 7)")
    print(f"Target: {BASE_URL}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=10, follow_redirects=FOLLOW_REDIRECTS)
        print(f"Health check: {r.status_code}")
        if r.status_code != 200:
            print("Server not healthy — aborting")
            sys.exit(1)
    except Exception as e:
        print(f"Cannot reach server: {e}")
        sys.exit(1)

    run_test("A: Owner accesses own order", test_owner_access)
    run_test("B: Different student blocked", test_different_user_blocked)
    run_test("C: Unauthenticated request blocked", test_unauthenticated_blocked)
    run_test("D: Nonexistent order returns 404", test_nonexistent_order)
    run_test("E: UUID substitution attack blocked", test_uuid_substitution)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    for name, p, detail in results:
        icon = "PASS" if p else "FAIL"
        print(f"  [{icon}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    print("=" * 60)
    sys.exit(0 if passed == total else 1)
