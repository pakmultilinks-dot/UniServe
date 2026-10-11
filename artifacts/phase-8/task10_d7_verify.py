"""Phase 8 Task 10 - D7 remediation verification (isolated DB only).

Before the fix, every cash-payment refund failed in the processor because
TestRefundProvider only accepts references starting with 'test_pay_' and cash
payments carry an empty provider_reference. After the fix, cash refunds are
settled manually (provider_reference = manual_cash_<refund-id>).
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
ORDER4 = "be1e501b-db4e-4a9b-bf63-bf873c33177e"  # completed, cash, succeeded payment
ORDER1 = "1012b956-1d49-4ffb-95bc-564cd57b6e21"  # completed, cash (pre-existing refunds untouched)


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
            return r.status, json.loads(r.read().decode()) if r.length != 0 else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    assert s == 200, (email, s, str(t)[:200])
    return t["tokens"]["access_token"]


admin = login("admin@lgu.edu.pk", "Admin123!")
fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")

results = []


def check(name, expected, got, detail=""):
    ok = str(got) == str(expected)
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected {expected}, got {got} {str(detail)[:150]}")


print("=== D7: cash refund must settle manually (not fail in processor) ===")
s, refund = call("POST", f"/refunds?order_id={ORDER4}", fac,
                 {"amount": 10000, "reason": "item_unavailable", "idempotency_key": "p8-d7-reverify-1"})
check("create refund request -> 201/200", True, s in (200, 201), refund)
rid = refund.get("id") if isinstance(refund, dict) else None
check("refund id returned", True, bool(rid), rid)

s, body = call("POST", f"/refunds/{rid}/process", admin, {})
check("process refund as admin -> 200", 200, s, body)

if s == 200:
    check("refund status == succeeded", "succeeded", body.get("status"), body)
    pref = (body.get("provider_reference") or "")
    check("provider_reference starts with manual_cash_", True, pref.startswith("manual_cash_"), pref)
    check("processed_by set", True, bool(body.get("processed_by")), body.get("processed_by"))
    check("refund_succeeded event present",
          True, any((e.get("event_type") == "refund_succeeded") for e in (body.get("events") or [])),
          [e.get("event_type") for e in (body.get("events") or [])])

# payment status verified directly against the isolated DB after the run

# second partial refund -> full refund flips payment to refunded
s, refund2 = call("POST", f"/refunds?order_id={ORDER4}", fac,
                  {"amount": 59800, "reason": "item_unavailable", "idempotency_key": "p8-d7-reverify-2"})
if s in (200, 201):
    rid2 = refund2.get("id")
    s, body2 = call("POST", f"/refunds/{rid2}/process", admin, {})
    check("second (remainder) refund -> succeeded", "succeeded", (body2 or {}).get("status"), body2)
else:
    print(f"[INFO] remainder refund create -> {s} {str(refund2)[:200]}")

print()
print("=== fail-closed: unknown processor name must raise (no silent fallback) ===")
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
os.environ.setdefault("POSTGRES_USER", "uniserve")
try:
    from app.modules.refunds.processors import create_refund_processor
    os.environ["REFUND_PROCESSOR"] = "definitely_not_a_processor"
    # Settings instance may already be cached; call with explicit name instead
    try:
        create_refund_processor("definitely_not_a_processor")
        check("unknown processor name -> raises", True, False, "no exception raised")
    except Exception as exc:
        check("unknown processor name -> raises", True, True, type(exc).__name__)
    p = create_refund_processor()
    check("default processor resolves to TestRefundProcessor", "TestRefundProcessor", type(p).__name__)
except Exception as exc:  # import/config issues should be visible, not hidden
    print(f"[FAIL] processor factory check errored: {type(exc).__name__}: {exc}")
    results.append(False)

print()
print(f"D7 RE-TEST: {sum(1 for r in results if r)}/{len(results)} passed")
