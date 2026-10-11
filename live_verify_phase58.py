"""Phase 58 Live Verification — probes A–J against the host API at :8001.

Runs against http://127.0.0.1:8001/api/v1 with real PostgreSQL (uniserve_prod
inside the uniserve_postgres container — the DB the running uvicorn actually
connects to). Verifies the Phase 58 workstreams on the live contract the UIs
call:

  A  Student/faculty default cafeteria listing excludes inactive cafeterias
  B  Customer refund request (exact mobile contract: refundable + POST
     /refunds with idempotency_key `refund-req-{id}` + order refund history)
  C  Four admin report endpoints (stock levels, low stock, turnover, peak hours)
  E3 GET /orders/{id}/eta authorization + payload
  E2 POST /orders/{id}/partial-cancel (owner-only, recalculation)
  H  Manager reject with valid enum vs invalid enum (4xx + message)
  E1 POST /orders/cafeteria/{id}/close (manager-only, cancels open orders,
     cafeteria → closed), then status restored to open
  F  Password change lifecycle (disposable user; wrong current rejected)
  G  PIN enable → login → change → login → disable lifecycle
  J  Regression: assignment guards (staff/manager cross-cafeteria) + admin
     refunds console endpoint intact

No commits, no pushes, no deploys. All mutations are confined to the dev
database and a disposable probe user; cafeteria operational_status is
restored to open after probe E1.
"""

import json
import subprocess
import sys
import uuid as _uuid

import httpx

BASE = "http://127.0.0.1:8001/api/v1"
FOLLOW_REDIRECTS = True
PG = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_prod"

ADMIN = "admin@lgu.edu.pk"
ADMIN_PW = "Admin123!"
MGR = "sana.malik@lgu.edu.pk"          # cafeteria_manager — Faculty Cafeteria only
STAFF = "ahmed.raza@lgu.edu.pk"        # cafeteria_staff — Student Cafeteria only
STUDENT = "ayesha.khan@student.lgu.edu.pk"
FACULTY = "dr.sana.malik@lgu.edu.pk"
PW = "TestPass123!"

FACULTY_CAFETERIA = "287038a2-8f8d-494c-bea5-42ff24550136"
STUDENT_CAFETERIA = "84ab69bb-ea39-451f-aec7-427922795ca8"
INACTIVE_IDS = {
    "a7641b13-dfe4-4ac6-861f-e5145494ae6f",  # Phase 56 Inactive Probe
    "d1bc8830-21a7-4fe6-97ea-570dd099aef5",  # Phase48 Test E2E
}

# Probe targets from live data (verified via psql before scripting)
REFUND_ORDER = "18be2aa7-b30d-4aae-91b5-44dbadbc6ae1"  # ayesha #46 completed, succeeded payment 32000 paisa
ETA_ORDER = "35fe0c86-836b-4927-b595-00c2d4231077"      # ayesha #6 pending, 2 items, Student Cafeteria
ETA_ORDER_OTHER = "663ae9a9-36d8-4850-8607-3b8045997bbd"  # ayesha #9 pending (non-owner target)
REJECT_ORDER_VALID = "c6e77b69-b0df-4c81-98de-12a7f1b7eff7"   # dr.imran #43 pending, Faculty
REJECT_ORDER_INVALID = "620ee5af-39f7-4bf3-bb9d-56bf01571ac3"  # dr.sana #23 pending, Faculty

results = []


def req(method, path, token=None, body=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.request(method, url, json=body, headers=headers, timeout=30,
                          follow_redirects=FOLLOW_REDIRECTS)
        try:
            parsed = r.json() if r.content else None
        except Exception:
            parsed = r.text[:250]
        return r.status_code, parsed
    except Exception as e:  # noqa: BLE001 — probe harness surfaces any transport error
        return None, str(e)


def detail_text(obj):
    return json.dumps(obj, default=str)[:220] if not isinstance(obj, str) else obj[:220]


def cafeterias_of(payload):
    """Unwrap CafeteriaListResponse {cafeterias: [...]} (dict or bare list)."""
    if isinstance(payload, dict):
        return payload.get("cafeterias", [])
    return payload or []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}  ::  {detail}")


def login(email, password):
    status, data = req("POST", "/auth/login", None, {"university_email": email, "password": password})
    if status == 200 and isinstance(data, dict):
        return data["tokens"]["access_token"]
    print(f"  !! login failed for {email}: {status} {detail_text(data)}")
    return None


def db_exec(sql):
    cmd = f'docker exec {PG} psql -U {PG_USER} -d {PG_DB} -t -c "{sql}"'
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
    return out.stdout.strip()


def main():
    admin_t = login(ADMIN, ADMIN_PW)
    mgr_t = login(MGR, PW)
    staff_t = login(STAFF, PW)
    student_t = login(STUDENT, PW)
    faculty_t = login(FACULTY, PW)
    if not all([admin_t, mgr_t, staff_t, student_t, faculty_t]):
        print("ABORT: a baseline login failed")
        sys.exit(1)

    # ── Probe A — inactive cafeteria default path ─────────────────────
    print("\n== Probe A: inactive cafeteria default listing ==")
    _, stu_list = req("GET", "/cafeterias", student_t)
    _, fac_list = req("GET", "/cafeterias", faculty_t)
    _, adm_list = req("GET", "/cafeterias", admin_t)
    _, mgr_list = req("GET", "/cafeterias", mgr_t)
    _, stu_inactive = req("GET", "/cafeterias?is_active=false", student_t)

    stu_ids = {c["id"] for c in cafeterias_of(stu_list)}
    fac_ids = {c["id"] for c in cafeterias_of(fac_list)}
    adm_ids = {c["id"] for c in cafeterias_of(adm_list)}
    mgr_ids = {c["id"] for c in cafeterias_of(mgr_list)}
    inactive_shown = {c["id"] for c in cafeterias_of(stu_inactive)}

    check("A1 student default listing excludes inactive", INACTIVE_IDS.isdisjoint(stu_ids),
          f"student sees {len(stu_ids)} cafeterias, inactive overlap={stu_ids & INACTIVE_IDS}")
    check("A2 faculty default listing excludes inactive", INACTIVE_IDS.isdisjoint(fac_ids),
          f"faculty sees {len(fac_ids)} cafeterias")
    check("A3 admin default listing includes inactive", INACTIVE_IDS.issubset(adm_ids),
          f"admin sees {len(adm_ids)} cafeterias, has inactive={INACTIVE_IDS & adm_ids}")
    check("A4 manager default listing includes inactive", INACTIVE_IDS.issubset(mgr_ids),
          f"manager sees {len(mgr_ids)} cafeterias")
    check("A5 student explicit ?is_active=false still honored", INACTIVE_IDS.issubset(inactive_shown),
          f"explicit filter returns {len(inactive_shown)} cafeterias")
    # Students must never see FACULTY-type cafeterias (pre-existing router
    # rule, line ~85-90) — so assert the active STUDENT cafeteria IS visible
    # and the FACULTY cafeteria is still hidden (type rule intact).
    check("A6 active STUDENT cafeteria visible to student", STUDENT_CAFETERIA in stu_ids,
          f"stu_ids={stu_ids}")
    check("A6b FACULTY cafeteria hidden from student (type rule preserved)",
          FACULTY_CAFETERIA not in stu_ids, f"stu_ids={stu_ids}")

    # ── Probe C — four admin report endpoints ─────────────────────────
    print("\n== Probe C: admin report endpoints ==")
    dates = "?start_date=2026-09-01&end_date=2026-10-07"
    s, peak = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/peak-hours{dates}", admin_t)
    check("C1 peak-hours 200 + shape", s == 200 and isinstance(peak, dict) and "hours" in peak
          and "cafeteria_id" in peak and "timezone" in peak, f"{s} {detail_text(peak)}")
    s, stock = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/inventory/stock-levels", admin_t)
    check("C2 stock-levels 200 + shape", s == 200 and isinstance(stock, dict)
          and {"cafeteria_id", "total_items", "out_of_stock_count", "low_stock_count", "items"} <= set(stock),
          f"{s} total_items={stock.get('total_items') if isinstance(stock, dict) else '?'}")
    s, low = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/inventory/low-stock", admin_t)
    check("C3 low-stock 200 + shape", s == 200 and isinstance(low, dict)
          and {"cafeteria_id", "total_low_stock", "items"} <= set(low), f"{s} {detail_text(low)}")
    s, turn = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/inventory/turnover{dates}", admin_t)
    check("C4 turnover 200 + shape", s == 200 and isinstance(turn, dict)
          and {"cafeteria_id", "total_adjustments", "adjustments"} <= set(turn),
          f"{s} adjustments={turn.get('total_adjustments') if isinstance(turn, dict) else '?'}")
    s, mgr_peak = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/peak-hours{dates}", mgr_t)
    check("C5 assigned manager can read her reports", s == 200, f"{s}")
    s, staff_rep = req("GET", f"/reports/cafeteria/{FACULTY_CAFETERIA}/inventory/stock-levels", staff_t)
    check("C6 staff of OTHER cafeteria denied (assignment guard)", s in (401, 403, 404), f"{s}")
    s, mgr_other = req("GET", f"/reports/cafeteria/{STUDENT_CAFETERIA}/inventory/stock-levels", mgr_t)
    check("C7 manager of OTHER cafeteria denied (assignment guard)", s in (401, 403, 404), f"{s}")

    # ── Probe E3 — ETA ────────────────────────────────────────────────
    print("\n== Probe E3: computed ETA ==")
    s, eta = req("GET", f"/orders/{ETA_ORDER}/eta", student_t)
    check("E3-1 owner gets ETA 200 + payload", s == 200 and isinstance(eta, dict)
          and "eta_minutes" in eta and "order_id" in eta, f"{s} {detail_text(eta)}")
    s, _ = req("GET", f"/orders/{ETA_ORDER}/eta", faculty_t)
    check("E3-2 non-owner denied", s in (403, 404), f"{s}")

    # ── Probe E2 — partial cancel (owner-only) ────────────────────────
    print("\n== Probe E2: customer partial cancel ==")
    s, order = req("GET", f"/orders/{ETA_ORDER}", student_t)
    items = order.get("items", []) if isinstance(order, dict) else []
    check("E2-1 pending order has 2 items before cancel", s == 200 and len(items) == 2,
          f"{s} items={len(items)} total={order.get('total_amount') if isinstance(order, dict) else '?'}")
    before_total = order.get("total_amount") if isinstance(order, dict) else None
    if items:
        victim = items[0]
        s, upd = req("POST", f"/orders/{ETA_ORDER}/partial-cancel", student_t,
                     {"item_id": victim["id"], "reason": "Item cancelled by customer"})
        new_items = upd.get("items", []) if isinstance(upd, dict) else []
        check("E2-2 owner partial-cancel 200, 1 item remains, total recalculated",
              s == 200 and len(new_items) == 1 and upd.get("total_amount") != before_total,
              f"{s} items={len(new_items)} total={upd.get('total_amount') if isinstance(upd, dict) else '?'}")
    s, _ = req("POST", f"/orders/{ETA_ORDER_OTHER}/partial-cancel", faculty_t,
               {"item_id": "00000000-0000-0000-0000-000000000000", "reason": "not mine"})
    check("E2-3 non-owner partial-cancel denied", s in (401, 403, 404), f"{s}")

    # ── Probe H — reject enum ─────────────────────────────────────────
    print("\n== Probe H: reject reason enum ==")
    s, rej = req("POST", f"/orders/{REJECT_ORDER_VALID}/reject", mgr_t,
                 {"reason": "capacity", "notes": "Phase 58 enum probe"})
    check("H-1 valid enum accepted, stored", s == 200 and isinstance(rej, dict)
          and rej.get("rejection_reason") == "capacity", f"{s} {detail_text(rej)}")
    s, bad = req("POST", f"/orders/{REJECT_ORDER_INVALID}/reject", mgr_t,
                 {"reason": "bogus_reason", "notes": "should fail"})
    bad_txt = detail_text(bad)
    check("H-2 invalid enum rejected 4xx + guidance", s is not None and 400 <= s < 500
          and "one of" in bad_txt.lower(), f"{s} {bad_txt}")

    # ── Probe E1 — close day (manager-only) ───────────────────────────
    print("\n== Probe E1: close-day ==")
    s, closed = req("POST", f"/orders/cafeteria/{FACULTY_CAFETERIA}/close", mgr_t,
                    {"notes": "Phase 58 close-day probe"})
    cancelled = closed.get("total") if isinstance(closed, dict) else None
    check("E1-1 assigned manager closes day 200, open orders cancelled",
          s == 200 and isinstance(closed, dict) and cancelled is not None, f"{s} total={cancelled}")
    _, caf = req("GET", "/cafeterias", admin_t)
    fac_row = next((c for c in cafeterias_of(caf) if c.get("id") == FACULTY_CAFETERIA), {})
    check("E1-2 cafeteria operational_status now closed",
          str(fac_row.get("operational_status", "")).lower() == "closed",
          f"status={fac_row.get('operational_status')}")
    s, _ = req("POST", f"/orders/cafeteria/{STUDENT_CAFETERIA}/close", student_t, {"notes": "nope"})
    check("E1-3 non-manager close denied", s in (401, 403, 404), f"{s}")
    s, _ = req("PATCH", f"/cafeterias/{FACULTY_CAFETERIA}/status", admin_t, {"status": "open"})
    _, caf2 = req("GET", "/cafeterias", admin_t)
    fac_row2 = next((c for c in cafeterias_of(caf2) if c.get("id") == FACULTY_CAFETERIA), {})
    check("E1-4 cafeteria restored to open", str(fac_row2.get("operational_status", "")).lower() == "open",
          f"restore={s} status={fac_row2.get('operational_status')}")

    # ── Probe B — customer refund request (mobile contract) ───────────
    print("\n== Probe B: customer refund request ==")
    s, refable = req("GET", f"/refunds/refundable/{REFUND_ORDER}", student_t)
    refundable = refable.get("refundable_amount") if isinstance(refable, dict) else None
    check("B-1 refundable info 200 for owner", s == 200 and refundable is not None,
          f"{s} {detail_text(refable)}")
    if s == 200 and refundable and refundable > 0:
        key = f"refund-req-{REFUND_ORDER}"
        body = {"amount": refundable, "reason": "other",
                "reason_note": "Phase 58 probe refund request", "idempotency_key": key}
        s1, r1 = req("POST", f"/refunds?order_id={REFUND_ORDER}", student_t, body)
        rid = r1.get("id") if isinstance(r1, dict) else None
        check("B-2 refund request 201 (exact mobile body)", s1 == 201 and rid is not None,
              f"{s1} {detail_text(r1)}")
        s2, r2 = req("POST", f"/refunds?order_id={REFUND_ORDER}", student_t, body)
        rid2 = r2.get("id") if isinstance(r2, dict) else None
        check("B-3 idempotent replay returns same refund", s2 in (200, 201) and rid is not None and rid == rid2,
              f"{s2} id1={rid} id2={rid2}")
        s3, hist = req("GET", f"/refunds/order/{REFUND_ORDER}", student_t)
        ids = [x.get("id") for x in hist.get("refunds", [])] if isinstance(hist, dict) else []
        check("B-4 owner refund history lists the request", s3 == 200 and rid in ids,
              f"{s3} history={ids}")
    else:
        check("B-2 refund request 201 (exact mobile body)", False,
              f"no refundable amount (s={s}, refundable={refundable}) — deadline/status gate active")
    s, _ = req("GET", f"/refunds/refundable/{REFUND_ORDER}", faculty_t)
    check("B-5 non-owner refund endpoints denied", s in (401, 403, 404), f"{s}")

    # ── Probe F — password change (disposable user) ───────────────────
    print("\n== Probe F: password self-service ==")
    suffix = _uuid.uuid4().hex[:8]
    email = f"phase58.probe{suffix}@student.lgu.edu.pk"
    s, reg = req("POST", "/auth/register", None, {
        "first_name": "Phase", "last_name": "Probe58",
        "university_id": f"LIVE-P58-{suffix.upper()}",
        "university_email": email, "password": "TempPass123!",
    })
    probe_uid = reg.get("user_id") if isinstance(reg, dict) else None
    check("F-0 disposable user registered", s == 201 and probe_uid is not None, f"{s} {detail_text(reg)}")
    if probe_uid:
        db_exec(f"UPDATE users SET email_verified = true, status = 'active' WHERE id = '{probe_uid}';")
        tok = login(email, "TempPass123!")
        check("F-1 login with original password", tok is not None, "")
        s, ch = req("POST", "/auth/password/change", tok,
                    {"current_password": "TempPass123!", "new_password": "NewPass58A!"})
        check("F-2 password change 200", s == 200, f"{s} {detail_text(ch)}")
        check("F-3 login with new password works", login(email, "NewPass58A!") is not None, "")
        check("F-4 login with old password fails", login(email, "TempPass123!") is None, "")
        s, _ = req("POST", "/auth/password/change", tok,
                   {"current_password": "Wrong999!", "new_password": "NewPass58B!"})
        check("F-5 wrong current password rejected", s is not None and 400 <= s < 500, f"{s}")
        s, _ = req("POST", "/auth/password/change", tok,
                   {"current_password": "NewPass58A!", "new_password": "weak"})
        check("F-6 weak new password rejected", s is not None and 400 <= s < 500, f"{s}")
        # restore original password so the disposable account matches its seed state
        req("POST", "/auth/password/change", tok,
            {"current_password": "NewPass58A!", "new_password": "TempPass123!"})

        # ── Probe G — PIN lifecycle ───────────────────────────────────
        print("\n== Probe G: PIN self-service ==")
        s, en = req("POST", "/auth/pin/enable", tok,
                    {"current_password": "TempPass123!", "pin": "4821", "confirm_pin": "4821"})
        check("G-1 PIN enable 200", s == 200, f"{s} {detail_text(en)}")
        s, pin_login = req("POST", "/auth/pin/login", None, {"user_id": probe_uid, "pin": "4821"})
        pin_tok = pin_login["tokens"]["access_token"] if isinstance(pin_login, dict) and "tokens" in pin_login else None
        check("G-2 PIN login 200 returns tokens", s == 200 and pin_tok is not None, f"{s}")
        s, _ = req("POST", "/auth/pin/login", None, {"user_id": probe_uid, "pin": "0000"})
        check("G-3 wrong PIN rejected", s is not None and 400 <= s < 500, f"{s}")
        s, _ = req("POST", "/auth/pin/change", tok,
                   {"current_pin": "4821", "new_pin": "9137", "confirm_pin": "9137"})
        check("G-4 PIN change 200", s == 200, f"{s}")
        s, _ = req("POST", "/auth/pin/login", None, {"user_id": probe_uid, "pin": "9137"})
        check("G-5 login with new PIN works", s == 200, f"{s}")
        s, _ = req("POST", "/auth/pin/login", None, {"user_id": probe_uid, "pin": "4821"})
        check("G-6 old PIN no longer works", s is not None and 400 <= s < 500, f"{s}")
        s, _ = req("POST", "/auth/pin/change", tok,
                   {"current_pin": "9137", "new_pin": "5566", "confirm_pin": "7788"})
        check("G-7 mismatched confirm PIN rejected", s is not None and 400 <= s < 500, f"{s}")
        s, _ = req("POST", "/auth/pin/disable", tok, {"current_password": "TempPass123!"})
        check("G-8 PIN disable 200", s == 200, f"{s}")
        s, _ = req("POST", "/auth/pin/login", None, {"user_id": probe_uid, "pin": "9137"})
        check("G-9 PIN login rejected after disable", s is not None and 400 <= s < 500, f"{s}")
        s, _ = req("POST", "/auth/pin/disable", tok, {"current_password": "Wrong999!"})
        check("G-10 disable with wrong password rejected", s is not None and 400 <= s < 500, f"{s}")

    # ── Probe J — regression: assignment guards + admin refunds console ─
    print("\n== Probe J: regression guards ==")
    s, _ = req("GET", f"/orders/cafeteria/{FACULTY_CAFETERIA}", staff_t)
    check("J-1 staff cannot list other cafeteria's orders", s in (401, 403, 404), f"{s}")
    s, _ = req("GET", f"/orders/cafeteria/{STUDENT_CAFETERIA}", mgr_t)
    check("J-2 manager cannot list unassigned cafeteria's orders", s in (401, 403, 404), f"{s}")
    s, all_refunds = req("GET", "/refunds/admin/all", admin_t)
    check("J-3 admin refunds console endpoint intact", s == 200 and isinstance(all_refunds, dict),
          f"{s} {detail_text(all_refunds)}")
    s, _ = req("GET", "/refunds/admin/all", student_t)
    check("J-4 student cannot access admin refunds console", s in (401, 403, 404), f"{s}")

    # ── Summary ───────────────────────────────────────────────────────
    passed = sum(1 for _, ok in results if ok)
    print(f"\n==== PHASE 58 LIVE PROBES: {passed}/{len(results)} passed ====")
    for name, ok in results:
        if not ok:
            print(f"  FAILED: {name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
