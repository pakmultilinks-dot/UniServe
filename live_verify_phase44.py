"""Phase 44 Live Verification — Product Completeness & UX Hardening.

Runs against the live API server at http://localhost:8000/api/v1 with real
PostgreSQL (uniserve_prod). Verifies the Phase 44 backend surface end-to-end:

- P3-3: GET /auth/me/cafeterias assignment discovery (manager/staff/admin/student)
- WS4: daily-menu unpublish (archive, /today exclusion, replacement draft,
  active-menu uniqueness, staff RBAC, write-scope)
- P3-2/P3-3: foreign-cafeteria 403 scoping on orders + inventory
- P3-8: generic PUT /orders/{id}/status → preparing sets preparation_started_at
- P3-9: PUT /orders/{id}/delay (manager/staff, range validation)
- P3-14: background worker cancels an expired scheduled PENDING order
  (controlled DB setup — the API by design cannot create an already-expired
  scheduled order)

CRITICAL CONSTRAINTS:
- Do NOT call internal service methods directly
- Do NOT manually set order status to simulate API behavior
- Database operations allowed ONLY for controlled setup, inspection, cleanup

Prerequisites:
- Docker: uniserve_api (Phase 44 image) + uniserve_postgres healthy
- Migration 0010 applied (partial unique index on daily_menus)
- Live accounts from scripts/create_live_accounts.py
"""

import subprocess
import sys
import time
import uuid

import httpx

BASE_URL = "http://localhost:8000/api/v1"
FOLLOW_REDIRECTS = True
PG_CONTAINER = "uniserve_postgres"
PG_USER = "uniserve"
PG_DB = "uniserve_prod"

# Live accounts (scripts/create_live_accounts.py)
MANAGER_EMAIL = "sana.malik@lgu.edu.pk"       # MGR-301, Faculty Cafeteria ONLY
STAFF_EMAIL = "ahmed.raza@lgu.edu.pk"         # STF-201, Student Cafeteria ONLY
STUDENT_EMAIL = "ayesha.khan@student.lgu.edu.pk"
ADMIN_EMAIL = "admin@lgu.edu.pk"
PASSWORD = "TestPass123!"
ADMIN_PASSWORD = "Admin123!"

results = []


def log_result(num, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((num, name, passed, detail))
    print(f"  [{status}] {num}: {name}")
    if detail and not passed:
        print(f"         Detail: {detail}")


def sql(query):
    cmd = (
        f'docker exec {PG_CONTAINER} psql -U {PG_USER} -d {PG_DB} '
        f'-t -A -c "{query}"'
    )
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip()


def login(client, email, password):
    r = client.post(
        f"{BASE_URL}/auth/login",
        json={"university_email": email, "password": password},
    )
    if r.status_code != 200:
        return None
    # LoginResponse nests tokens: {"tokens": {"access_token": ..., ...}, ...}
    body = r.json()
    tokens = body.get("tokens", body)
    return tokens.get("access_token")


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    client = httpx.Client(timeout=30, follow_redirects=FOLLOW_REDIRECTS)

    # ------------------------------------------------------------------
    # Setup: login all roles first, then resolve cafeterias (admin-scoped)
    # ------------------------------------------------------------------
    admin_tok = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    manager_tok = login(client, MANAGER_EMAIL, PASSWORD)
    staff_tok = login(client, STAFF_EMAIL, PASSWORD)
    student_tok = login(client, STUDENT_EMAIL, PASSWORD)
    tokens = {
        "manager": manager_tok,
        "staff": staff_tok,
        "student": student_tok,
        "admin": admin_tok,
    }
    for role, tok in tokens.items():
        if tok is None:
            print(f"FATAL: could not login as {role}")
            return 1

    # GET /cafeterias requires auth (all 5 roles); response is
    # CafeteriaListResponse {"cafeterias": [...], "total": N}.
    # Admin has universal visibility of both cafeterias.
    r = client.get(f"{BASE_URL}/cafeterias", headers=hdr(admin_tok))
    if r.status_code != 200:
        print(f"FATAL: GET /cafeterias -> {r.status_code} {r.text[:200]}")
        return 1
    caf_list = r.json().get("cafeterias", [])
    cafeterias = {c["name"].lower(): c["id"] for c in caf_list}
    faculty_caf = next(
        (cid for name, cid in cafeterias.items() if "faculty" in name), None
    )
    student_caf = next(
        (cid for name, cid in cafeterias.items() if "student" in name), None
    )
    if faculty_caf is None or student_caf is None:
        print(f"FATAL: could not resolve both cafeterias: {cafeterias}")
        return 1
    print(f"Faculty cafeteria: {faculty_caf}")
    print(f"Student cafeteria: {student_caf}")

    # ------------------------------------------------------------------
    # 1. P3-3 — /auth/me/cafeterias
    # ------------------------------------------------------------------
    print("\n== 1. GET /auth/me/cafeterias (P3-3) ==")
    r = client.get(f"{BASE_URL}/auth/me/cafeterias", headers=hdr(manager_tok))
    ids = r.json().get("cafeteria_ids", []) if r.status_code == 200 else []
    log_result(
        "1.1",
        "manager sees assigned cafeteria only",
        r.status_code == 200 and ids == [faculty_caf],
        f"status={r.status_code} ids={ids}",
    )

    r = client.get(f"{BASE_URL}/auth/me/cafeterias", headers=hdr(staff_tok))
    ids = r.json().get("cafeteria_ids", []) if r.status_code == 200 else []
    log_result(
        "1.2",
        "staff sees assigned cafeteria only",
        r.status_code == 200 and ids == [student_caf],
        f"status={r.status_code} ids={ids}",
    )

    r = client.get(f"{BASE_URL}/auth/me/cafeterias", headers=hdr(student_tok))
    ids = r.json().get("cafeteria_ids", []) if r.status_code == 200 else None
    log_result(
        "1.3", "student gets empty list", r.status_code == 200 and ids == [],
        f"status={r.status_code} ids={ids}",
    )

    r = client.get(f"{BASE_URL}/auth/me/cafeterias", headers=hdr(admin_tok))
    ids = r.json().get("cafeteria_ids", []) if r.status_code == 200 else None
    log_result(
        "1.4", "admin gets empty list", r.status_code == 200 and ids == [],
        f"status={r.status_code} ids={ids}",
    )

    # ------------------------------------------------------------------
    # 2. WS4 — daily-menu unpublish workflow (manager, Faculty cafeteria)
    # ------------------------------------------------------------------
    print("\n== 2. Daily-menu unpublish workflow (WS4) ==")
    today = time.strftime("%Y-%m-%d")
    r = client.post(
        f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/",
        headers=hdr(manager_tok),
        json={"menu_date": today},
    )
    # An active menu for today may already exist from earlier activity —
    # if so, reuse it; otherwise create a fresh draft.
    if r.status_code == 201:
        menu_id = r.json()["id"]
        menu_existed = False
    else:
        r = client.get(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus",
            headers=hdr(manager_tok),
        )
        body = r.json()
        # DailyMenuListResponse: {"menus": [...], "total": N}
        menus = body.get("menus", []) if isinstance(body, dict) else body
        todays = [
            m
            for m in menus
            if m.get("menu_date") == today and m.get("status") != "archived"
        ]
        menu_id = todays[0]["id"] if todays else None
        menu_existed = menu_id is not None

    # Re-run safety: if the resolved menu is already PUBLISHED, unpublish it
    # (the Phase 44 capability itself) and start a fresh draft so the
    # add-item and publish steps below run against a DRAFT.
    if menu_id is not None and menu_existed:
        r = client.get(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/{menu_id}",
            headers=hdr(manager_tok),
        )
        existing_status = r.json().get("status") if r.status_code == 200 else None
        if existing_status == "published":
            r = client.patch(
                f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/{menu_id}/unpublish",
                headers=hdr(manager_tok),
            )
            if r.status_code == 200:
                r = client.post(
                    f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/",
                    headers=hdr(manager_tok),
                    json={"menu_date": today},
                )
                if r.status_code == 201:
                    menu_id = r.json()["id"]
                    menu_existed = False
    log_result(
        "2.1",
        "manager can create (or reuse) today's daily menu",
        menu_id is not None,
        f"status={r.status_code} menu_id={menu_id}",
    )
    if menu_id is None:
        print("   Cannot continue WS4 flow without a daily menu.")
    else:
        # Ensure at least one item, then publish if still draft
        r = client.get(
            f"{BASE_URL}/cafeterias/{faculty_caf}/menu-items",
            headers=hdr(manager_tok),
        )
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items", [])
        if items:
            r = client.post(
                f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/{menu_id}/items",
                headers=hdr(manager_tok),
                json={"menu_item_id": items[0]["id"]},
            )
            item_ok = r.status_code in (200, 409)
        else:
            item_ok = False
        log_result("2.2", "manager can add item to daily menu", item_ok)

        r = client.patch(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/{menu_id}/publish",
            headers=hdr(manager_tok),
        )
        publish_ok = r.status_code == 200
        log_result(
            "2.3", "manager can publish daily menu", publish_ok, r.text[:120]
        )

        r = client.get(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/today",
            headers=hdr(manager_tok),
        )
        today_ok = r.status_code == 200 and r.json() is not None
        log_result(
            "2.4", "published menu visible in /daily-menus/today", today_ok,
            f"status={r.status_code} body={r.text[:80]}",
        )

        # Unpublish (the Phase 44 capability)
        r = client.patch(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/{menu_id}/unpublish",
            headers=hdr(manager_tok),
        )
        unpub_ok = r.status_code == 200 and r.json().get("status") == "archived"
        log_result(
            "2.5", "manager can unpublish → archived", unpub_ok, r.text[:120]
        )

        r = client.get(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/today",
            headers=hdr(manager_tok),
        )
        gone_ok = r.status_code == 200 and r.json() is None
        log_result(
            "2.6", "archived menu excluded from /daily-menus/today", gone_ok,
            f"status={r.status_code} body={r.text[:80]}",
        )

        # Replacement draft for the same date (archived must not block)
        r = client.post(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/",
            headers=hdr(manager_tok),
            json={"menu_date": today},
        )
        repl_ok = r.status_code == 201
        log_result(
            "2.7", "replacement draft creatable after unpublish", repl_ok,
            r.text[:120],
        )

        # Active-menu uniqueness still enforced
        r = client.post(
            f"{BASE_URL}/cafeterias/{faculty_caf}/daily-menus/",
            headers=hdr(manager_tok),
            json={"menu_date": today},
        )
        dup_ok = r.status_code == 409
        log_result(
            "2.8", "duplicate active menu for same date → 409", dup_ok,
            f"status={r.status_code}",
        )

        # Staff cannot unpublish (server-side RBAC)
        r = client.patch(
            f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/{menu_id}/unpublish",
            headers=hdr(staff_tok),
        )
        staff_ok = r.status_code in (401, 403, 404)
        log_result(
            "2.9", "staff cannot unpublish (RBAC)", staff_ok,
            f"status={r.status_code}",
        )

        # Manager (Faculty-assigned) cannot unpublish a foreign cafeteria's
        # menu — write-scope assignment check must reject with 403
        r = client.patch(
            f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/{menu_id}/unpublish",
            headers=hdr(manager_tok),
        )
        foreign_ok = r.status_code == 403
        log_result(
            "2.10", "foreign-cafeteria unpublish → 403", foreign_ok,
            f"status={r.status_code}",
        )

    # ------------------------------------------------------------------
    # 3. P3-2/P3-3 — foreign-cafeteria scoping on orders + inventory
    # ------------------------------------------------------------------
    print("\n== 3. Foreign-cafeteria scoping (P3-2/P3-3) ==")
    # Orders list route: GET /orders/cafeteria/{cafeteria_id}
    # (RequireCafeteriaWriteScope ADMIN/MANAGER/STAFF → assignment enforced)
    r = client.get(
        f"{BASE_URL}/orders/cafeteria/{student_caf}", headers=hdr(manager_tok)
    )
    log_result(
        "3.1", "manager (Faculty) → Student orders 403", r.status_code == 403,
        f"status={r.status_code}",
    )
    r = client.get(
        f"{BASE_URL}/orders/cafeteria/{faculty_caf}", headers=hdr(staff_tok)
    )
    log_result(
        "3.2", "staff (Student) → Faculty orders 403", r.status_code == 403,
        f"status={r.status_code}",
    )
    r = client.get(
        f"{BASE_URL}/cafeterias/{faculty_caf}/inventory", headers=hdr(staff_tok)
    )
    log_result(
        "3.3", "staff (Student) → Faculty inventory 403", r.status_code == 403,
        f"status={r.status_code}",
    )
    r = client.get(
        f"{BASE_URL}/cafeterias/{student_caf}/inventory", headers=hdr(staff_tok)
    )
    log_result(
        "3.4", "staff reads own cafeteria inventory 200", r.status_code == 200,
        f"status={r.status_code}",
    )

    # ------------------------------------------------------------------
    # 4. P3-8 + P3-9 — generic status transition + delay (Student cafeteria)
    # ------------------------------------------------------------------
    print("\n== 4. Order operations (P3-8/P3-9) ==")
    # Checkout requires a PUBLISHED daily menu for today at the target
    # cafeteria (pre-existing business rule in checkout()). Ensure one
    # exists at the Student cafeteria using the admin's universal scope.
    r = client.post(
        f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/",
        headers=hdr(admin_tok),
        json={"menu_date": today},
    )
    if r.status_code == 201:
        s_menu_id = r.json()["id"]
    else:
        r = client.get(
            f"{BASE_URL}/cafeterias/{student_caf}/daily-menus",
            headers=hdr(admin_tok),
        )
        body = r.json()
        menus = body.get("menus", []) if isinstance(body, dict) else body
        todays = [
            m
            for m in menus
            if m.get("menu_date") == today and m.get("status") != "archived"
        ]
        s_menu_id = todays[0]["id"] if todays else None
    if s_menu_id is not None:
        r = client.get(
            f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/{s_menu_id}",
            headers=hdr(admin_tok),
        )
        s_status = r.json().get("status") if r.status_code == 200 else None
        if s_status != "published":
            r = client.get(
                f"{BASE_URL}/cafeterias/{student_caf}/menu-items",
                headers=hdr(admin_tok),
            )
            s_items = r.json().get("items", []) if r.status_code == 200 else []
            if s_items:
                client.post(
                    f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/{s_menu_id}/items",
                    headers=hdr(admin_tok),
                    json={"menu_item_id": s_items[0]["id"]},
                )
            r = client.patch(
                f"{BASE_URL}/cafeterias/{student_caf}/daily-menus/{s_menu_id}/publish",
                headers=hdr(admin_tok),
            )
            print(f"  Student cafeteria today's menu publish -> {r.status_code}")
    # Build a cash order for the student in their cafeteria
    r = client.get(
        f"{BASE_URL}/cafeterias/{student_caf}/menu-items", headers=hdr(student_tok)
    )
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    available = [i for i in items if i.get("is_available") and i.get("is_active")]
    order_id = None
    if available:
        r = client.post(
            f"{BASE_URL}/cafeterias/{student_caf}/cart/items",
            headers=hdr(student_tok),
            json={"menu_item_id": available[0]["id"], "quantity": 1},
        )
        add_ok = r.status_code in (200, 201)
        if add_ok:
            r = client.post(
                f"{BASE_URL}/cafeterias/{student_caf}/cart/checkout",
                headers=hdr(student_tok),
                json={"payment_method": "cash"},
            )
            if r.status_code == 201:
                order_id = r.json()["id"]
    log_result(
        "4.1", "student can checkout a cash order", order_id is not None,
        f"order_id={order_id}",
    )

    if order_id:
        r = client.post(
            f"{BASE_URL}/orders/{order_id}/confirm",
            headers=hdr(staff_tok),
            json={},
        )
        log_result(
            "4.2", "staff confirms order", r.status_code == 200, r.text[:120]
        )

        # P3-8: generic status endpoint → preparing (must set lifecycle fields)
        r = client.put(
            f"{BASE_URL}/orders/{order_id}/status",
            headers=hdr(staff_tok),
            json={"status": "preparing"},
        )
        body = r.json() if r.status_code == 200 else {}
        p38_ok = (
            r.status_code == 200
            and body.get("status") == "preparing"
            and body.get("preparation_started_at") is not None
        )
        log_result(
            "4.3",
            "P3-8 generic status→preparing sets preparation_started_at",
            p38_ok,
            f"status={r.status_code} body={r.text[:160]}",
        )

        # P3-9: staff can delay a preparing order
        # (OrderDelayRequest: additional_minutes, ge=1 le=120)
        r = client.put(
            f"{BASE_URL}/orders/{order_id}/delay",
            headers=hdr(staff_tok),
            json={"additional_minutes": 10},
        )
        log_result(
            "4.4", "P3-9 staff can delay preparing order", r.status_code == 200,
            r.text[:120],
        )

        # P3-9: invalid range rejected (pydantic ge=1 → 422)
        r = client.put(
            f"{BASE_URL}/orders/{order_id}/delay",
            headers=hdr(staff_tok),
            json={"additional_minutes": 0},
        )
        log_result(
            "4.5", "P3-9 additional_minutes=0 rejected", r.status_code >= 400,
            f"status={r.status_code}",
        )

        # P3-8: generic path for ready invariants
        r = client.put(
            f"{BASE_URL}/orders/{order_id}/status",
            headers=hdr(staff_tok),
            json={"status": "ready"},
        )
        body = r.json() if r.status_code == 200 else {}
        ready_ok = (
            r.status_code == 200
            and body.get("status") == "ready"
            and body.get("ready_at") is not None
            and body.get("pickup_deadline") is not None
        )
        log_result(
            "4.6",
            "P3-8 generic status→ready sets ready_at + pickup_deadline",
            ready_ok,
            f"status={r.status_code} body={r.text[:160]}",
        )

        # Cleanup: mark collected so the order does not linger
        r = client.put(
            f"{BASE_URL}/orders/{order_id}/status",
            headers=hdr(staff_tok),
            json={"status": "completed"},
        )
        log_result(
            "4.7", "order collected (cleanup)", r.status_code == 200,
            r.text[:120],
        )

    # ------------------------------------------------------------------
    # 5. P3-14 — background worker cancels an expired scheduled order
    #     (controlled DB setup; API cannot create past-slot orders)
    # ------------------------------------------------------------------
    print("\n== 5. Scheduled order auto-expiry (P3-14) ==")
    student_row = sql(
        f"SELECT id FROM users WHERE university_email = '{STUDENT_EMAIL}'"
    )
    probe_number = int(sql("SELECT COALESCE(MAX(order_number),0)+1 FROM orders"))
    # Derive BOTH the slot time and its local date from the same past
    # datetime (cafeteria timezone is Asia/Karachi = host local) so a
    # midnight-crossing run still produces a coherent order_date + slot.
    past = time.localtime(time.time() - 5400)
    past_date = time.strftime("%Y-%m-%d", past)
    past_slot = time.strftime("%H:%M", past)
    probe_uuid = str(uuid.uuid4())
    # collection_token (NOT NULL unique, Python-side default) and
    # preparation_started (NOT NULL default False) must be supplied
    # explicitly — raw SQL INSERT bypasses ORM column defaults.
    sql(
        "INSERT INTO orders (id, order_number, user_id, cafeteria_id, "
        "order_type, payment_method, status, total_amount, currency, "
        "order_date, scheduled_collection_time, collection_token, "
        "preparation_started, inventory_reserved, created_at, updated_at) VALUES ("
        f"'{probe_uuid}', {probe_number}, '{student_row}', '{student_caf}', "
        f"'scheduled', 'cash', 'pending', 25000, 'PKR', "
        f"'{past_date}', '{past_slot}', "
        f"'p44{probe_uuid.replace('-', '')}', false, false, now(), now())"
    )
    print(
        f"  Inserted expired scheduled order #{probe_number} "
        f"(date {past_date}, slot {past_slot})"
    )
    # Raw INSERT bypasses the API's order_number_sequence allocator — keep
    # the sequence row ahead of this probe order so API checkouts never
    # collide with it (checkout allocates last_number + 1).
    sql(
        "UPDATE order_number_sequence SET last_number = "
        f"GREATEST(last_number, {probe_number})"
    )
    print("  Waiting up to 90s for the pickup-expiry worker tick...")
    expired = None
    for _ in range(9):
        time.sleep(10)
        row = sql(
            "SELECT status FROM orders WHERE order_number = "
            f"{probe_number} AND status = 'cancelled'"
        )
        if row:
            expired = row
            break
    log_result(
        "5.1",
        "worker cancels scheduled PENDING order past slot + grace",
        expired is not None,
        f"order_number={probe_number}",
    )
    reason = sql(
        "SELECT cancellation_reason FROM orders WHERE order_number = "
        f"{probe_number}"
    )
    log_result(
        "5.2",
        "cancellation reason mentions automatic expiry",
        "Automatic expiry" in reason,
        f"reason={reason!r}",
    )
    event = sql(
        "SELECT count(*) FROM order_events oe JOIN orders o ON o.id = oe.order_id "
        f"WHERE o.order_number = {probe_number} AND oe.event_type = 'cancelled'"
    )
    log_result(
        "5.3", "CANCELLED order event recorded", event == "1", f"events={event}"
    )
    notif = sql(
        "SELECT count(*) FROM notifications n JOIN orders o ON o.id = n.order_id "
        f"WHERE o.order_number = {probe_number}"
    )
    log_result(
        "5.4", "cancellation notification emitted", notif != "0",
        f"notifications={notif}",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    passed = sum(1 for _, _, p, _ in results if p)
    failed = len(results) - passed
    print(f"\n{'=' * 60}")
    print(f"Phase 44 live verification: {passed} passed, {failed} failed, "
          f"{len(results)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
