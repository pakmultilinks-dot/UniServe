"""Phase 8 Task 10 - D8 remediation verification (isolated DB only)."""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"

def call(method, path, token=None, body=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def login(email, pw):
    status, text = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    assert status == 200, (email, status, text[:200])
    return json.loads(text)["tokens"]["access_token"]

admin = login("admin@lgu.edu.pk", "Admin123!")
fac_a = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")   # owner of order #4 (completed)
fac_b = login("dr.imran.chaudhry@lgu.edu.pk", "TestPass123!")  # non-owner
staff = login("ahmed.raza@lgu.edu.pk", "TestPass123!")      # Student Cafeteria staff

ORDER4 = "be1e501b-db4e-4a9b-bf63-bf873c33177e"  # completed, owned by sana
ORDER5 = "77797d57-7805-4857-a17f-f4e30ad656fc"  # cancelled, owned by sana
MISSING = "00000000-0000-4000-8000-000000000000"

results = []

def probe(name, expected, resp):
    code, text = resp
    ok = code == expected
    results.append((ok, name, expected, code))
    print(f"{'PASS' if ok else 'FAIL'} | {name} | expected {expected}, got {code} | {text[:110]}")

print("=== D8: cancel endpoint must not be an order-status oracle ===")
probe("non-owner cancel COMPLETED order -> 403", 403,
      call("POST", f"/orders/{ORDER4}/cancel", token=fac_b, body={"reason": "probe"}))
probe("non-owner cancel CANCELLED order -> 403", 403,
      call("POST", f"/orders/{ORDER5}/cancel", token=fac_b, body={"reason": "probe"}))
probe("non-owner cancel MISSING order -> 404 (GET parity)", 404,
      call("POST", f"/orders/{MISSING}/cancel", token=fac_b, body={"reason": "probe"}))
probe("non-owner cancel (GET parity) COMPLETED -> 403", 403,
      call("GET", f"/orders/{ORDER4}", token=fac_b))
probe("non-owner GET MISSING order -> 404 (parity baseline)", 404,
      call("GET", f"/orders/{MISSING}", token=fac_b))
probe("wrong-cafeteria staff manager-cancel COMPLETED -> 403", 403,
      call("POST", f"/orders/{ORDER4}/cancel", token=staff, body={"reason": "wrong cafeteria"}))
probe("owner cancel of already-CANCELLED order -> 400 (real status error)", 400,
      call("POST", f"/orders/{ORDER5}/cancel", token=fac_a, body={"reason": "dup"}))

print()
passed = sum(1 for ok, *_ in results if ok)
print(f"D8 RE-TEST: {passed}/{len(results)} passed")
