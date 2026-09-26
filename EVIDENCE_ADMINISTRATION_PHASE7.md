# EVIDENCE: Phase 7 University Administration — Backend APIs

**Date:** 2026-09-26
**Phase:** 7 — University Administration Overview (Backend)

---

## 1. Administration Endpoint Implemented (1)

| # | Method | Endpoint | Authorization | Description |
|---|--------|----------|---------------|-------------|
| 1 | GET | `/api/v1/administration/overview` | Admin only | University-wide summary: users, cafeterias, orders, financial, exceptions |

### Response Sections

| Section | Fields | Description |
|---------|--------|-------------|
| `users` | `total`, `students`, `faculty`, `university_admins`, `cafeteria_managers`, `cafeteria_staff`, `active`, `suspended`, `ordering_suspended` | Role + status + suspension counts |
| `cafeterias` | `total`, `cafeterias[]` (id, name, operational_status, preparation_capacity) | Per-cafeteria operational details |
| `orders` | `total_orders`, `pending`, `preparing`, `ready`, `completed`, `cancelled`, `uncollected`, `cancellation_rate` | Status breakdown + computed rate |
| `financial` | `total_revenue`, `total_refunded`, `net_revenue`, `online_payment_volume`, `cash_payment_volume`, `currency` | Revenue, refunds, payment method split |
| `exceptions` | `overdue_refunds`, `ordering_suspended_users`, `uncollected_orders`, `cafeteria_closure_cancellations` | Exception/escalation counts |

---

## 2. Test Results

**Unit tests:** 501 passed, 3 failed (pre-existing scheduled-order tests)
**28/28 administration tests passed.**

**New test classes:** 7

```
TestAuthorization (6 tests — unauthenticated, student, faculty, manager, staff, admin)
TestUserAggregation (3 tests — role counts, active/suspended counts, ordering_suspended)
TestCafeteriaAggregation (4 tests — both cafeterias, operational status, manager/staff counts, prep capacity)
TestOrderAggregation (4 tests — status counts, uncollected count, date filtering, cancellation rate)
TestFinancialAggregation (5 tests — revenue, failed excluded, refunds, online/cash breakdown, net revenue)
TestExceptionAggregation (4 tests — overdue refunds, suspended users, uncollected, closure)
TestSecurity (2 tests — no sensitive fields, cross-role no leak)
```

**Pre-existing failures (not related to Phase 7):**
1. `test_scheduled_order_inventory_reserved_at_prep`
2. `test_checkout_scheduled_does_not_reserve_inventory`
3. `test_scheduled_inventory_reserved_at_preparation`

---

## 3. Live Verification Results (60/60 passed)

Tested against real PostgreSQL (Docker `uniserve_postgres` on port 5433).
Script: `live_verify_administration.py`

```
--- Setup ---
  ✅ Admin login

--- Test 1: Admin access to overview ---
  ✅ Admin gets 200

--- Test 2: Response structure ---
  ✅ Has 'users' key
  ✅ Has 'cafeterias' key
  ✅ Has 'orders' key
  ✅ Has 'financial' key
  ✅ Has 'exceptions' key

--- Test 3: Date filtering ---
  ✅ Date-filtered request 200

--- Test 4: Cafeteria summary ---
  ✅ Cafeterias has 'total'
  ✅ Cafeterias has 'cafeterias' list
  ✅ Cafeteria count >= 2
  ✅ Cafeteria has 'cafeteria_id'
  ✅ Cafeteria has 'name'
  ✅ Cafeteria has 'operational_status'
  ✅ Cafeteria has 'preparation_capacity'

--- Test 5: User counts ---
  ✅ Users has 'total'
  ✅ Users has 'students'
  ✅ Users has 'faculty'
  ✅ Users has 'university_admins'
  ✅ Users has 'cafeteria_managers'
  ✅ Users has 'cafeteria_staff'
  ✅ Users has 'active'
  ✅ Users has 'suspended'
  ✅ Users has 'ordering_suspended'
  ✅ Total users > 0

--- Test 6: Order counts ---
  ✅ Orders has 'total_orders'
  ✅ Orders has 'pending'
  ✅ Orders has 'completed'
  ✅ Orders has 'cancelled'
  ✅ Orders has 'uncollected'
  ✅ Orders has 'cancellation_rate'
  ✅ cancellation_rate is float or 0
  ✅ total_orders >= 0

--- Test 7: Financial totals ---
  ✅ Financial has 'total_revenue'
  ✅ Financial has 'total_refunded'
  ✅ Financial has 'net_revenue'
  ✅ Financial has 'online_payment_volume'
  ✅ Financial has 'cash_payment_volume'
  ✅ Financial has 'currency'
  ✅ Currency is PKR
  ✅ total_revenue >= 0
  ✅ net_revenue = revenue - refunded

--- Test 8: Refund totals ---
  ✅ total_refunded >= 0
  ✅ net_revenue <= total_revenue

--- Test 9: Exception counts ---
  ✅ Exceptions has 'overdue_refunds'
  ✅ Exceptions has 'ordering_suspended_users'
  ✅ Exceptions has 'uncollected_orders'
  ✅ Exceptions has 'cafeteria_closure_cancellations'
  ✅ overdue_refunds >= 0
  ✅ ordering_suspended_users >= 0

--- Test 10: Manager denied ---
  ✅ Manager gets 403

--- Test 11: Staff denied ---
  ✅ Staff gets 403

--- Test 12: Student denied ---
  ✅ Student gets 403

--- Test 13: Faculty denied ---
  ✅ Faculty gets 403

--- Test 14: No sensitive fields ---
  ✅ No 'password' in response
  ✅ No 'password_hash' in response
  ✅ No 'pin_hash' in response
  ✅ No 'refresh_token' in response
  ✅ No 'otp' in response
  ✅ No 'biometric' in response
```

---

## 4. Authorization Verification

- ✅ **Unauthenticated** → 401/403
- ✅ **Student** → 403
- ✅ **Faculty** → 403
- ✅ **Cafeteria Manager** → 403
- ✅ **Cafeteria Staff** → 403
- ✅ **University Admin** → 200 (only authorized role)

Enforced via `RequireRole(Role.UNIVERSITY_ADMIN)` dependency in router.

---

## 5. Revenue & Financial Definition

- **Revenue** = `SUM(Payment.amount) WHERE Payment.status = 'succeeded'` for orders in date range
- **Refunded** = `SUM(Refund.amount) WHERE Refund.status = 'succeeded'`
- **Net Revenue** = total_revenue − total_refunded
- **Payment volumes** = online vs cash split from `Order.payment_method`
- All monetary values in **paisa** (smallest PKR unit)

---

## 6. Database/Migrations

**No new database migration required.** Phase 7 administration queries use existing tables: `users`, `cafeterias`, `orders`, `payments`, `refunds`, `no_shows`. All aggregation via SQL `GROUP BY`, `func.sum`, `func.count`, `func.filter`.

---

## 7. Performance/Query Approach

- Single aggregated endpoint (one request, five sections) minimizes client round-trips
- SQL-level aggregation — no full dataset loading into Python
- Uses `.select_from()` for explicit joins preventing SQLAlchemy ambiguity
- Empty datasets return zeroed defaults
- `CASE WHEN` for conditional counting (ordering_suspended, uncollected)
- Default date range: last 30 days (configurable via query params)

---

## 8. Linting & Type Checking

```
ruff check app/modules/administration/ → All checks passed!
ruff format --check app/modules/administration/ → 4 files already formatted
mypy app/modules/administration/ --ignore-missing-imports → Success: no issues found in 4 source files
```

---

## 9. Files Created/Modified

| File | Action | Lines | Description |
|------|--------|-------|-------------|
| `app/modules/administration/__init__.py` | Created | 5 | Module docstring |
| `app/modules/administration/schemas.py` | Created | 120 | 7 Pydantic response models |
| `app/modules/administration/service.py` | Created | 300 | 5 aggregation methods |
| `app/modules/administration/router.py` | Created | 68 | Single GET /overview endpoint |
| `app/api/router.py` | Modified | 7 | Registered administration router |
| `tests/test_administration.py` | Created | 744 | 28 tests across 7 classes |
| `live_verify_administration.py` | Created | 324 | 60 live verification assertions |
| `EVIDENCE_ADMINISTRATION_PHASE7.md` | Created | ~230 | This evidence document |

---

## 10. Security Findings

No new security issues introduced. The endpoint:
- Enforces `RequireRole(Role.UNIVERSITY_ADMIN)` — only university admins can access
- Returns no sensitive fields (passwords, tokens, PINs, OTPs)
- All aggregation is server-computed (no client-provided totals)
- Date range boundaries are validated
- Division-by-zero handled with `if total > 0 else 0.0`

---

## 11. Git Commit

```
feat(admin): add Phase 7 university administration overview APIs

- GET /api/v1/administration/overview (admin only)
- 5 sections: users, cafeterias, orders, financial, exceptions
- 28 unit tests (7 classes), 60 live verification assertions
- SQL-level aggregation, no new migrations required
- Pydantic v2 schemas, SQLAlchemy 2.0 async, ruff clean, mypy clean
```
