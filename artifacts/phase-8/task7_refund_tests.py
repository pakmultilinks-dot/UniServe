"""Phase 8 — Task 7: refund/cancellation workflow.

Isolated API only (127.0.0.1:8001 / uniserve_test_phase7). Never prod.
Covers: refundable query, request (owner), RBAC, over-refund, invalid
reason, idempotency, process, reject, double-process, no-payment order.
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
ORDER_COMPLETED = "1012b956-1d49-4ffb-95bc-564cd57b6e21"  # order #1, paid 34900
ORDER_CANCELLED = "a05d5eed-a7e0-405d-9df1-9301c28de8b1"  # order #2, cancelled, no payment


def call(method, path, token=None, body=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + token} if token else {})},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except Exception:
            return e.code, raw[:250]


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    return ((t.get("tokens") or {}).get("access_token")) if s == 200 else None


results = []


def check(label, expected, s, body=None):
    detail = body.get("detail") if isinstance(body, dict) else (str(body)[:120] if body else "")
    code = body.get("code") if isinstance(body, dict) else ""
    ok = str(s) == str(expected)
    results.append({"test": label, "expected": str(expected), "got": s, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exp {expected} got {s} | {detail} {code}")
    return body if isinstance(body, dict) else {}


admin = login("admin@lgu.edu.pk", "Admin123!")
mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
other_stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")
print("tokens:", {k: bool(v) for k, v in dict(admin=admin, mgr=mgr, fac=fac, stu=other_stu).items()})

print("\n=== A. Refundable amount (order #1, owner) ===")
r = check("GET refundable -> 200", "200", *call("GET", f"/refunds/refundable/{ORDER_COMPLETED}", fac))
print("   refundable payload:", json.dumps(r))

print("\n=== B. Request refund — RBAC / validation ===")
check("other user request refund -> 403", "403",
      *call("POST", f"/refunds?order_id={ORDER_COMPLETED}", other_stu,
            {"amount": 100, "reason": "other", "idempotency_key": "p8-r1"}))
check("amount 0 -> 422", "422",
      *call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
            {"amount": 0, "reason": "other", "idempotency_key": "p8-r2"}))
check("invalid reason -> 400", "400",
      *call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
            {"amount": 100, "reason": "not_a_reason", "idempotency_key": "p8-r3"}))
check("over-refund (999999) -> 400", "400",
      *call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
            {"amount": 999999, "reason": "item_unavailable", "idempotency_key": "p8-r4"}))
check("refund on unpaid/cancelled order -> 400", "400",
      *call("POST", f"/refunds?order_id={ORDER_CANCELLED}", fac,
            {"amount": 100, "reason": "order_cancelled", "idempotency_key": "p8-r5"}))

print("\n=== C. Valid refund request (owner, partial) ===")
s, body = call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
               {"amount": 10000, "reason": "item_unavailable",
                "reason_note": "Phase 8 partial refund test",
                "idempotency_key": "phase8-refund-001"})
check("create refund -> 201", "201", s, body)
refund_id = body.get("id")
print("   refund id:", refund_id, "status:", body.get("status"))

print("\n=== D. Idempotency: same key returns same refund ===")
s, body2 = call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
                {"amount": 10000, "reason": "item_unavailable",
                 "idempotency_key": "phase8-refund-001"})
same = isinstance(body2, dict) and body2.get("id") == refund_id
ok = s in (200, 201) and same
results.append({"test": "refund idempotency", "expected": "same id", "got": s, "ok": ok,
                "detail": f"same={same}"})
print(f"[{'PASS' if ok else 'FAIL'}] refund idempotency: {s} same={same}")

print("\n=== E. RBAC on process/reject ===")
if refund_id:
    check("student process refund -> 403", "403",
          *call("POST", f"/refunds/{refund_id}/process", other_stu, {}))
    check("faculty process refund -> 403", "403",
          *call("POST", f"/refunds/{refund_id}/process", fac, {}))
    check("student reject refund -> 403", "403",
          *call("POST", f"/refunds/{refund_id}/reject", other_stu,
                {"rejection_reason": "Not eligible per policy testing"}))

    print("\n=== F. Reject path (manager) on a second refund ===")
    s, body3 = call("POST", f"/refunds?order_id={ORDER_COMPLETED}", fac,
                    {"amount": 5000, "reason": "other",
                     "reason_note": "to be rejected",
                     "idempotency_key": "phase8-refund-002"})
    rid2 = body3.get("id") if s == 201 else None
    check("second refund -> 201", "201", s, body3)
    if rid2:
        r = check("manager reject -> 200", "200",
                  *call("POST", f"/refunds/{rid2}/reject", mgr,
                        {"rejection_reason": "Phase 8: duplicate request rejected in test"}))
        print("   reject status:", r.get("status") if isinstance(r, dict) else r)
        check("re-reject already rejected -> 4xx", "400",
              *call("POST", f"/refunds/{rid2}/reject", mgr,
                    {"rejection_reason": "Trying to reject twice in test"}))

    print("\n=== G. Process the valid refund (admin) ===")
    r = check("admin process -> 200", "200",
              *call("POST", f"/refunds/{refund_id}/process", admin, {}))
    print("   process result:", json.dumps(r)[:400])
    check("double-process -> 400", "400",
          *call("POST", f"/refunds/{refund_id}/process", admin, {}))

    print("\n=== H. List refunds for order (owner) ===")
    r = check("GET order refunds -> 200", "200",
              *call("GET", f"/refunds/order/{ORDER_COMPLETED}", fac))
    print("   list:", json.dumps(r)[:300])

    print("\n=== I. Admin listing ===")
    check("GET admin/all -> 200", "200", *call("GET", "/refunds/admin/all", admin))
    check("GET admin/all as manager -> 403", "403", *call("GET", "/refunds/admin/all", mgr))

print("\n=== SUMMARY ===")
passed = sum(1 for x in results if x["ok"])
print(f"{passed}/{len(results)} checks matched expectation")
for x in results:
    if not x["ok"]:
        print("  MISMATCH:", x)
