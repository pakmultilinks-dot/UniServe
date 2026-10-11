#!/usr/bin/env python3
"""Phase 63 — DATA INTEGRITY CHECKS (Section 7).

Runs read-only SQL assertions against the live uniserve_prod database.
Each check returns (name, ok, detail). No writes, no deletes.
"""

import subprocess
import sys

DB = ["docker", "exec", "uniserve_postgres", "psql", "-U", "uniserve", "-d", "uniserve_prod", "-t", "-A", "-F", "|"]

CHECKS: list[tuple[str, str, bool, str]] = []  # (area, name, ok, detail)


def q(sql: str) -> str:
    r = subprocess.run(DB + ["-c", sql], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return f"__ERROR__ {r.stderr.strip()[:200]}"
    return r.stdout.strip()


def check(area: str, name: str, sql: str, expect_zero: bool = True) -> None:
    out = q(sql)
    if out.startswith("__ERROR__"):
        CHECKS.append((area, name, False, out))
        print(f"[FAIL] {area} :: {name} — {out}")
        return
    n = int(out) if out.isdigit() else -1
    ok = (n == 0) if expect_zero else (n > 0)
    CHECKS.append((area, name, ok, f"count={out}"))
    print(f"[{'PASS' if ok else 'FAIL'}] {area} :: {name} — {out}")


def scalar(sql: str, label: str) -> str:
    out = q(sql)
    print(f"       {label}: {out}")
    return out


def main() -> int:
    # ---- Orphan foreign keys ----
    check("FK", "orphan order_items->orders",
          "SELECT count(*) FROM order_items oi LEFT JOIN orders o ON o.id=oi.order_id WHERE o.id IS NULL")
    check("FK", "orphan order_items->menu_items",
          "SELECT count(*) FROM order_items oi LEFT JOIN menu_items mi ON mi.id=oi.menu_item_id WHERE mi.id IS NULL")
    check("FK", "orphan orders->users",
          "SELECT count(*) FROM orders o LEFT JOIN users u ON u.id=o.user_id WHERE u.id IS NULL")
    check("FK", "orphan orders->cafeterias",
          "SELECT count(*) FROM orders o LEFT JOIN cafeterias c ON c.id=o.cafeteria_id WHERE c.id IS NULL")
    check("FK", "orphan payments->orders",
          "SELECT count(*) FROM payments p LEFT JOIN orders o ON o.id=p.order_id WHERE o.id IS NULL")
    check("FK", "orphan refunds->orders",
          "SELECT count(*) FROM refunds r LEFT JOIN orders o ON o.id=r.order_id WHERE o.id IS NULL")
    check("FK", "orphan notifications->users",
          "SELECT count(*) FROM notifications n LEFT JOIN users u ON u.id=n.user_id WHERE u.id IS NULL")
    check("FK", "orphan menu_items->cafeterias",
          "SELECT count(*) FROM menu_items mi LEFT JOIN cafeterias c ON c.id=mi.cafeteria_id WHERE c.id IS NULL")
    check("FK", "orphan daily_menu_items->daily_menus",
          "SELECT count(*) FROM daily_menu_items dmi LEFT JOIN daily_menus dm ON dm.id=dmi.daily_menu_id WHERE dm.id IS NULL")
    check("FK", "orphan inventory->cafeterias",
          "SELECT count(*) FROM inventory_items i LEFT JOIN cafeterias c ON c.id=i.cafeteria_id WHERE c.id IS NULL")

    # ---- Duplicate constraints ----
    check("DUP", "duplicate user emails",
          "SELECT count(*) FROM (SELECT university_email FROM users GROUP BY university_email HAVING count(*)>1) d")
    check("DUP", "duplicate active daily menus per cafeteria/date",
          "SELECT count(*) FROM (SELECT cafeteria_id, menu_date FROM daily_menus WHERE status!='archived' GROUP BY 1,2 HAVING count(*)>1) d")
    check("DUP", "duplicate order numbers",
          "SELECT count(*) FROM (SELECT order_number FROM orders GROUP BY order_number HAVING count(*)>1) d")

    # ---- Payment/refund state consistency ----
    check("PAY", "payments with non-positive amount",
          "SELECT count(*) FROM payments WHERE amount <= 0")
    check("PAY", "refunds exceeding paid amount per order",
          "SELECT count(*) FROM (SELECT r.order_id FROM refunds r JOIN payments p ON p.order_id=r.order_id WHERE r.status='processed' GROUP BY r.order_id HAVING sum(r.amount) > max(p.amount)) d")
    check("PAY", "refunds with non-positive amount",
          "SELECT count(*) FROM refunds WHERE amount <= 0")
    check("PAY", "completed cash orders missing payment record",
          "SELECT count(*) FROM orders o WHERE o.status='completed' AND o.payment_method='cash' AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id=o.id)")

    # ---- Ownership & scoping ----
    check("SCOPE", "orders with cafeteria mismatch vs their items' cafeteria",
          "SELECT count(*) FROM orders o JOIN order_items oi ON oi.order_id=o.id JOIN menu_items mi ON mi.id=oi.menu_item_id WHERE mi.cafeteria_id<>o.cafeteria_id")
    check("SCOPE", "orphan notifications (no user and no cafeteria audience)",
          "SELECT count(*) FROM notifications WHERE user_id IS NULL AND cafeteria_id IS NULL")

    # ---- Order number sequence drift ----
    drift = q("SELECT (SELECT COALESCE(MAX(order_number),0) FROM orders) - (SELECT last_number FROM order_number_sequence)")
    ok = drift == "0"
    CHECKS.append(("SEQ", "order_number_sequence vs max(order_number)", ok, f"drift={drift}"))
    print(f"[{'PASS' if ok else 'FAIL'}] SEQ :: order_number_sequence drift — {drift}")

    # ---- Cross-cafeteria leakage (staff/manager scope) ----
    check("LEAK", "cafeteria_staff assigned to 2+ cafeterias",
          "SELECT count(*) FROM (SELECT user_id FROM cafeteria_assignments GROUP BY user_id HAVING count(DISTINCT cafeteria_id)>1) d")
    check("LEAK", "order_events referencing missing orders",
          "SELECT count(*) FROM order_events e LEFT JOIN orders o ON o.id=e.order_id WHERE o.id IS NULL")
    check("LEAK", "refund_events referencing missing refunds",
          "SELECT count(*) FROM refund_events e LEFT JOIN refunds r ON r.id=e.refund_id WHERE r.id IS NULL")

    # ---- Audit trail ----
    check("AUDIT", "security_audit_events present", "SELECT count(*) FROM security_audit_events", expect_zero=False)
    scalar("SELECT count(*) FROM security_audit_events WHERE event_type::text LIKE '%login%'", "login audit events")

    # ---- Test residue scan ----
    scalar("SELECT count(*) FROM users WHERE university_email LIKE 'phase63%'", "phase63 fixture users")
    scalar("SELECT count(*) FROM menu_items WHERE name LIKE 'Phase63%'", "phase63 fixture menu items")
    scalar("SELECT count(*) FROM orders WHERE order_number >= 56", "orders #56+ (phase63 E2E orders)")
    scalar("SELECT count(*) FROM orders WHERE status IN ('pending','preparing','ready')", "open orders (demo state)")

    print("\n================= INTEGRITY SUMMARY =================")
    fails = [c for c in CHECKS if not c[2]]
    print(f"Total: {len(CHECKS)} | PASS: {len(CHECKS) - len(fails)} | FAIL: {len(fails)}")
    for a, n, _, d in fails:
        print(f"  FAIL [{a}] {n} — {d}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
