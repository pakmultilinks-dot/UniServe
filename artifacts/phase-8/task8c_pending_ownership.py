"""Phase 8 — Task 8c: prove ownership is enforced on a PENDING order (no write-IDOR).

Uses the pending Order #3 created by task8b (faculty-owned). Isolated API only.
Reads status before/after to prove a stranger cannot cancel it.
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
ORDER_PENDING = "eb6c9731-361f-49a1-bc2d-53ce739b3fcc"   # order #3, faculty, pending


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
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw or "null")
            except Exception:
                return r.status, raw[:250]
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except Exception:
            return e.code, raw[:250]
    except Exception as e:
        return -1, str(e)[:200]


def login(email, pw):
    s, t = call("POST", "/auth/login", body={"university_email": email, "password": pw})
    return ((t.get("tokens") or {}).get("access_token")) if s == 200 else None


results = []


def check(label, expected, s, body=None):
    detail = body.get("detail") if isinstance(body, dict) else (str(body)[:140] if body else "")
    if isinstance(expected, (list, tuple, set)):
        ok = str(s) in {str(x) for x in expected}
        exp_txt = "/".join(str(x) for x in expected)
    else:
        ok = str(s) == str(expected)
        exp_txt = str(expected)
    results.append({"test": label, "expected": exp_txt, "got": s, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exp {exp_txt} got {s} | {detail}")
    return body if isinstance(body, dict) else {}


fac = login("dr.sana.malik@lgu.edu.pk", "TestPass123!")
stu = login("ayesha.khan@student.lgu.edu.pk", "TestPass123!")
mgr = login("sana.malik@lgu.edu.pk", "TestPass123!")
staff = login("ahmed.raza@lgu.edu.pk", "TestPass123!")
print("tokens:", {k: bool(v) for k, v in dict(fac=fac, stu=stu, mgr=mgr, staff=staff).items()})

s, before = call("GET", f"/orders/{ORDER_PENDING}", fac)
print("owner sees status:", before.get("status") if isinstance(before, dict) else s)

print("\n=== Stranger attempts on a PENDING order ===")
s, b = call("POST", f"/orders/{ORDER_PENDING}/cancel", stu, {"reason": "other"})
check("stranger (student) cancel pending -> denied (400 ownership / 403)", (400, 403), s, b)
print("   detail:", json.dumps(b)[:250])

s, b = call("GET", f"/orders/{ORDER_PENDING}", stu)
check("stranger GET pending order -> 403", "403", s, b)

print("\n=== Wrong-cafeteria staff attempts ===")
s, b = call("POST", f"/orders/{ORDER_PENDING}/confirm", staff, {})
check("staff(other caf) confirm pending -> 403", "403", s, b)
print("   detail:", json.dumps(b)[:250])
s, b = call("POST", f"/orders/{ORDER_PENDING}/manager-cancel", staff,
            {"reason": "other", "reason_note": "cross cafeteria should deny"})
check("staff: manager-cancel pending -> 403 (manager-only role)", "403", s, b)
# NOTE: mgr Sana IS assigned to the Faculty Cafeteria, so her manager-cancel on
# this Faculty-Cafeteria order is legitimately ALLOWED. Verified separately as a
# positive control in Task 6; deliberately not executed here so the pending order
# survives for the "still pending" proof below.

print("\n=== Proof the pending order survived all of the above ===")
s, b = call("GET", f"/orders/{ORDER_PENDING}", fac)
ok = isinstance(b, dict) and b.get("status") == "pending"
results.append({"test": "pending order still pending after stranger/wrong-caf attempts",
                "expected": "pending", "got": (b.get("status") if isinstance(b, dict) else s),
                "ok": ok, "detail": f"status={(b.get('status') if isinstance(b, dict) else s)}"})
print(f"[{'PASS' if ok else 'FAIL'}] pending order still pending: "
      f"{b.get('status') if isinstance(b, dict) else s}")

print("\n=== Cleanup: owner cancels their own pending order ===")
s, b = call("POST", f"/orders/{ORDER_PENDING}/cancel", fac, {"reason": "other"})
check("owner cancels own pending order -> 200", "200", s, b)

print("\n=== SUMMARY ===")
passed = sum(1 for r in results if r["ok"])
print(f"{passed}/{len(results)} checks matched expectation")
for r in results:
    if not r["ok"]:
        print(f"  FAIL: {r['test']} exp={r['expected']} got={r['got']} detail={r['detail']}")
