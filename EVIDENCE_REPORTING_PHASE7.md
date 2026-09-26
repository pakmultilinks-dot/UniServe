# EVIDENCE: Phase 7 Reporting & Analytics — Backend APIs

**Date:** 2026-09-25
**Phase:** 7 — Reporting & Analytics (Backend)

---

## 1. Reporting Endpoints Implemented (12)

| # | Method | Endpoint | Authorization | Description |
|---|--------|----------|---------------|-------------|
| 1 | GET | `/api/v1/reports/sales` | Admin, Manager, Staff | Sales summary (total revenue, refunds, net) |
| 2 | GET | `/api/v1/reports/sales/daily` | Admin, Manager, Staff | Daily revenue breakdown |
| 3 | GET | `/api/v1/reports/sales/by-cafeteria` | Admin only | Revenue per cafeteria (cross-cafeteria) |
| 4 | GET | `/api/v1/reports/orders/summary` | Admin, Manager, Staff | Order counts by status, type, payment method |
| 5 | GET | `/api/v1/reports/orders/volume` | Admin, Manager, Staff | Daily + hourly order volume |
| 6 | GET | `/api/v1/reports/orders/cancellation-rate` | Admin, Manager, Staff | Cancellation rate + reasons |
| 7 | GET | `/api/v1/reports/cafeteria/{id}/performance` | Admin, Manager (own), Staff (own) | Cafeteria lifecycle metrics |
| 8 | GET | `/api/v1/reports/cafeteria/{id}/popular-items` | Admin, Manager (own), Staff (own) | Popular menu items by quantity |
| 9 | GET | `/api/v1/reports/cafeteria/{id}/peak-hours` | Admin, Manager (own), Staff (own) | Order volume by hour of day |
| 10 | GET | `/api/v1/reports/cafeteria/{id}/inventory/stock-levels` | Admin, Manager (own), Staff (own) | Current stock levels |
| 11 | GET | `/api/v1/reports/cafeteria/{id}/inventory/low-stock` | Admin, Manager (own), Staff (own) | Low/out-of-stock items |
| 12 | GET | `/api/v1/reports/cafeteria/{id}/inventory/turnover` | Admin, Manager (own), Staff (own) | Inventory adjustment activity |

---

## 2. Test Results

**Unit tests:** 473 passed, 3 failed (baseline: 430 passed + 45 new report tests = 475, but 3 pre-existing scheduled-order tests fail on every run)
**45/45 reporting tests passed.**
**New test classes:** 14, covering all 12 endpoints + authorization + regression

```
TestSalesSummary (6 tests)
TestSalesDaily (2 tests)
TestSalesByCafeteria (2 tests)
TestOrderSummary (5 tests)
TestOrderVolume (2 tests)
TestCancellationRate (2 tests)
TestCafeteriaPerformance (3 tests)
TestCafeteriaPopularItems (2 tests)
TestCafeteriaPeakHours (2 tests)
TestInventoryStockLevels (2 tests)
TestInventoryLowStock (2 tests)
TestInventoryTurnover (2 tests)
TestAuthorization (11 tests — IDOR, role-based, cross-cafeteria)
TestExistingTestsUnaffected (2 tests — health + auth regression)
```

**Pre-existing failures (not related to Phase 7):**
1. `test_scheduled_order_inventory_reserved_at_prep`
2. `test_checkout_scheduled_does_not_reserve_inventory`
3. `test_scheduled_inventory_reserved_at_preparation`

---

## 3. Live Verification Results (not rerun — Docker unavailable)

The live verification script (`live_verify_reporting.py`) exists with 28 assertions covering all 12 endpoints, but was **not executed** during this cleanup because the Docker daemon (PostgreSQL, Redis) was not running. Live verification should be rerun when Docker is available.

```
Test 1:  Admin access to sales report ✅
Test 2:  Manager access own cafeteria performance ✅
Test 3:  Manager cross-cafeteria IDOR denied ✅
Test 4:  Student denied from reports ✅
Test 5:  Unauthenticated access denied ✅
Test 6:  Order summary endpoint ✅
Test 7:  Sales by cafeteria (admin only) ✅
Test 8:  Staff access own cafeteria popular items ✅
Test 9:  Empty date range returns zeroed data ✅
Test 10: Inventory stock levels ✅
Bonus:   Sales daily, Order volume, Cancellation rate, Peak hours, Low stock, Inventory turnover ✅
```

---

## 4. Authorization Verification

- ✅ **Unauthenticated** → 401/403 on all endpoints
- ✅ **Student** → 403 on all reporting endpoints
- ✅ **Faculty** → 403 on all reporting endpoints
- ✅ **Manager** → 200 on own cafeteria, 403 on other cafeteria (IDOR prevention)
- ✅ **Staff** → 200 on own cafeteria, 403 on cross-cafeteria
- ✅ **Admin** → 200 on all endpoints, including cross-cafeteria sales-by-cafeteria
- ✅ **Sales by cafeteria** → Admin only (manager/staff get 403)

---

## 5. Revenue Definition

Revenue = `SUM(Payment.amount) WHERE Payment.status = 'succeeded'` for orders in the date range. Failed, abandoned, and cancelled payments are excluded. Succeeded refund amounts are subtracted separately to produce net revenue. All monetary values are in **paisa** (smallest PKR unit).

---

## 6. Refund Handling

Refunds are tracked separately: `SUM(Refund.amount) WHERE Refund.status = 'succeeded'`. Net revenue = total_revenue − total_refunded. Refunds are NOT deducted from revenue directly — they appear as a separate `total_refunded` field and a computed `net_revenue`.

---

## 7. Database/Migrations

**No new database migration required.** Phase 7 reporting queries use existing tables: `orders`, `payments`, `refunds`, `cafeterias`, `menu_items`, `order_items`, `inventory_items`, `inventory_adjustments`. All aggregation is done via SQL `GROUP BY`, `SUM`, `COUNT`, `AVG`, `EXTRACT`.

---

## 8. Performance/Query Approach

All 12 endpoints use SQL-level aggregation (`GROUP BY`, `func.sum`, `func.count`, `func.avg`, `func.extract`). No full dataset loading into Python. Empty datasets return zeroed defaults. Cross-database compatibility via SQLAlchemy `func.extract()` (works on both SQLite tests and PostgreSQL production). Division-by-zero handled with `if total > 0 else 0.0`.

---

## 9. Ruff

```
ruff check app/modules/reports/ tests/test_reports.py → All checks passed!
ruff format --check → 1 cosmetic formatting difference in service.py (indentation only, no functional impact)
```

---

## 10. Mypy

```
mypy app/modules/reports/ --ignore-missing-imports → Success: no issues found in 4 source files
```

---

## 11. Known Pre-existing Issues

- 4 E402 errors (module-import-not-at-top-of-file) — pre-existing in payments, orders, refunds routers
- 1 N802 error (invalid-function-name) — pre-existing StrEnum
- 3 pre-existing scheduled-time test failures (hardcoded "14:00"/"14:30" times)

None of these are in the reports module.

---

## 12. Security Findings

No new security issues introduced. All endpoints:
- Enforce role-based authorization via `RequireRole`
- Enforce cafeteria scope via `_verify_cafeteria_assignment()` 
- Prevent IDOR (cross-cafeteria access blocked for manager/staff)
- No sensitive data leakage (no customer PII in reports)
- No N+1 queries (all SQL aggregation)
- Division-by-zero safe
- Date boundaries use `<=` for inclusive ranges
- No client-provided totals (all server-computed)
