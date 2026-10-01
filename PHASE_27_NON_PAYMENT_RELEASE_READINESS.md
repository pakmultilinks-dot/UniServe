# PHASE 27 — NON-PAYMENT RELEASE READINESS AUDIT & REMEDIATION

**Date:** 2026-10-01
**Commit:** `fix: resolve non-payment release readiness issues` (see Section 21 for hash)
**Scope:** Every UniServe subsystem that does NOT depend on the real JazzCash payment provider.
**Frozen constraint honored:** JazzCash/payment-provider implementation was NOT touched. Payment code was inspected read-only solely to confirm the fail-closed state remains safe.

---

## 1. Phase Overview

Phase 27 audits and fixes everything in UniServe that does not depend on the real payment provider. The JazzCash dependency remains externally blocked (technical access request delivered in Phase 26B, awaiting provider response). This phase therefore hardens the entire non-payment surface: authorization, cafeteria isolation, order lifecycle, stock/concurrency, scheduled orders, notifications, mobile, web, API/DB integrity, secrets/config, and production configuration.

## 2. Scope & Constraints

**In scope:** auth/RBAC, cafeteria isolation, order lifecycle, stock/concurrency, scheduled orders, notifications, mobile app, web console, API/DB integrity, secrets/config, Docker/production config (inspect only), full validation, genuine fixes with regression tests.

**Explicitly forbidden (all honored):** implementing JazzCash; inventing JazzCash endpoints; adding JazzCash credentials; modifying the JazzCash provider contract; enabling production online payments; replacing JazzCash; weakening the payment production fail-closed guard; modifying payment signing/webhook behavior; deploying to VPS; modifying DNS/domain/HTTPS; speculative payment refactoring; creating filler issues; deleting/weakening/skipping/rewriting tests to obtain a green result.

## 3. Baseline Validation (Pre-Fix)

| Validation | Result |
|---|---|
| Backend pytest (full) | **573 passed** in 259.69s |
| E2E (`scripts/phase19_e2e_test.py`) | **31/31 PASS** (100%) |
| Web `npx tsc --noEmit` | EXIT=0 |
| Web `npx next build` (static export) | EXIT=0, all 22 routes built |
| Mobile `npm run type-check` | EXIT=0 |

All five baselines were green before any fix, confirming the audit found genuine latent defects rather than regressions.

## 4. Audit: Authentication & RBAC

Verified: JWT + session check in `get_current_user`; `RequireRole`, `RequireCafeteriaWriteScope`, `RequireCafeteriaScope`, `verify_resource_cafeteria` in `core/deps.py`; exception→status map (NotFound=404, Auth=401, Authz=403, ValidationError=400, ServiceUnavailable=503) in `main.py`. Web refresh token in sessionStorage (XSS mitigation).

**Defect found (Issue 1):** `suspend_user` allowed a CAFETERIA_MANAGER to suspend STUDENT/FACULTY accounts — the admin/manager guard permitted any manager to suspend any user, including non-cafeteria university users.

## 5. Audit: Cafeteria Isolation (Menus / Favorites / Search)

**Defect found (Issue 2):** `GET /cafeterias/{cid}/menu-items/{item_id}` did not verify the resource's cafeteria against the path cafeteria — a student could read a faculty-cafeteria menu item by ID via their own cafeteria path (cross-cafeteria IDOR).

**Defect found (Issue 3):** Unscoped `GET /menu-search/` returned faculty-cafeteria items to students (faculty cafeteria should be invisible to student-category users).

**Defect found (Issue 4):** `POST /favorites/` allowed students to favorite faculty-cafeteria items; `GET /favorites/` listed legacy faculty favorites.

## 6. Audit: Order Lifecycle

Verified: `confirmOrder, prepareOrder, readyOrder, delayOrder, rejectOrder` in web UI; confirm-then-prepare flow followed by web UI; mobile has no order-status mutation calls; transition validation matrix intact.

**Defect found (Issue 6):** `PUT /orders/{id}/status` (generic `update_status`) bypassed business gates enforced by `/prepare` — it accepted `preparing` on unconfirmed orders and on online orders with unsucceeded payments.

## 7. Audit: Stock & Concurrency

Verified: `.with_for_update()` on PostgreSQL in orders service (SQLite-safe pattern); atomic raw UPDATE for `_allocate_order_number`; `FOR UPDATE SKIP LOCKED` in `process_expired_pickups`.

**Defect found (Issue 7):** `adjust_inventory` performed unlocked read-modify-write (`get_inventory_item` without row lock) — a lost-update race under concurrent adjustments.

## 8. Audit: Scheduled Orders

Verified: checkout validation uses `ZoneInfo(cafeteria.timezone)` for `scheduled_collection_time`.

**Defect found (Issue 5):** `_check_scheduled_cancellation_deadline` treated the cafeteria-local `HH:MM` collection time as UTC, shifting the cancellation deadline by the cafeteria's UTC offset (5 hours for PKT) — cancellations were wrongly blocked/allowed.

## 9. Audit: Notifications

Clean. Notification creation, parameters, read/unread flows, and staff/student scoping verified; no defects found. Existing tests (`TestNotificationParameters`, E2E Phase 12) cover the surface.

## 10. Audit: Mobile App

Clean. Student/faculty-only role surface; no order-status mutation calls; type-check green. No defects found.

## 11. Audit: Web App

Clean. Admin/manager/staff-only console; refresh token in sessionStorage; confirm-then-prepare order flow already correct in UI; tsc and static build green. No defects found.

## 12. Audit: API & DB Integrity

Verified: Alembic at head `0009`; async SQLAlchemy 2.0; schema notes confirmed (`cafeterias.operational_status`, `type`=cafeteria_type, `timezone` default `Asia/Karachi`, `inventory_items.quantity/unit/low_threshold`, `cafeteria_assignments` UNIQUE on `user_id`).

**Defect found (Issue 8):** Query-scoped reports endpoints (`/reports/sales`, `/sales/daily`, `/orders/summary`, `/orders/volume`, `/orders/cancellation-rate`) accepted an omitted `cafeteria_id` from manager/staff and silently returned university-wide data (cross-cafeteria data exposure).

## 13. Audit: Secrets & Configuration

Clean. Only test fixtures (`StrongPass123!`) and dev seed scripts (`TestPass123!`, `Admin123!`) — no production secrets committed. All payment credential config fields have blank defaults.

## 14. Audit: Docker & Production Config (Inspect Only)

Clean. `docker-compose.prod.yml` sane (Caddy + API + Postgres, DB exposed-only not published, healthchecks, Redis commented out). No changes made — inspect-only constraint honored.

## 15. Payment Code Inspection (Frozen — Fail-Closed Confirmed)

Read-only inspection confirmed the blocked state remains safe:

- `PaymentProvider` ABC in `providers/base.py`; `PROVIDER_REGISTRY = {"test": TestPaymentProvider}` only.
- `create_payment_provider` fails closed (`ServiceUnavailableError`) on unknown provider names.
- Production guard in `initiate_payment_for_order` raises 503 when `APP_ENV == "production"` and provider is `TestPaymentProvider`.
- No credentials anywhere in the repo; `PAYMENT_PROVIDER="test"`, `PAYMENT_ENVIRONMENT="sandbox"`.
- Webhook idempotency: signature verified FIRST; `event_id` from verified payload.
- `verify_payment` has no call site (reconciliation poller = future work).

**No payment code was modified.**

## 16. Issues Discovered (8 Genuine)

| # | Area | Issue | Severity |
|---|---|---|---|
| 1 | RBAC | Manager could suspend student/faculty accounts | High |
| 2 | Isolation | Menu item GET cross-cafeteria IDOR (no resource-vs-path check) | High |
| 3 | Isolation | Unscoped search leaked faculty-cafeteria items to students | Medium |
| 4 | Isolation | Favorites allowed/blocklist-missed faculty items for students | Medium |
| 5 | Scheduled | Cancellation deadline compared local time as UTC | Medium |
| 6 | Orders | `update_status` bypassed confirm + payment gates | High |
| 7 | Stock | `adjust_inventory` lost-update race (no row lock) | Medium |
| 8 | Reports | Omitted `cafeteria_id` yielded university-wide data for manager/staff | High |

No filler issues were created; every item is a genuine defect with a security, correctness, or integrity impact.

## 17. Fixes Implemented (8)

1. **`users/router.py` `suspend_user`** — students/faculty are admin-only: `AuthorizationError("Only a University Admin can suspend students or faculty")`.
2. **`menus/router.py` `get_menu_item`** — `verify_resource_cafeteria` now checks `item.cafeteria_id` against the path cafeteria.
3. **`menus/router.py` + `menus/service.py`** — helper `_can_view_all_cafeterias`; unscoped search passes `exclude_faculty_cafeteria` (service joins `Cafeteria` and filters `type != FACULTY`) for student-category users.
4. **`menus/router.py` + `menus/service.py`** — `add_favorite` rejects faculty-cafeteria items for non-privileged users (403); `list_favorites` filters faculty items via `exclude_faculty_cafeteria`.
5. **`orders/service.py` `_check_scheduled_cancellation_deadline`** — now `async def`; loads cafeteria timezone (`ZoneInfo`, UTC fallback), combines `order_date` + `HH:MM` in local tz, converts to UTC before applying `CANCELLATION_DEADLINE_MINUTES`.
6. **`orders/service.py` `update_status`** — enforces the same gates as `/prepare`: `preparing` requires `confirmed_at`; online orders additionally require a `SUCCEEDED` payment row.
7. **`inventory/service.py` `adjust_inventory`** — locked select (`with_for_update()` on PostgreSQL) replaces the unlocked read; docstring updated.
8. **`reports/router.py`** — `_resolve_cafeteria_scope`: admin keeps university-wide; manager/staff with omitted `cafeteria_id` default to their single assignment (403 if unassigned, 400 if multiple — the latter retained as defense-in-depth; see Section 19). All 5 query-scoped endpoints use it.

## 18. Regression Tests Added

| File | Tests | Covers |
|---|---|---|
| `test_auth_authorization.py` | 3 (2 new + 1 control) | Manager cannot suspend student/faculty; admin can (control) |
| `test_hardening_authorization.py` | 9 | Menu GET cross-cafeteria IDOR (deny×2 + control); search faculty exclusion (student deny + faculty/admin controls); favorites faculty exclusion (student deny + faculty control + legacy-list filter) |
| `test_orders.py` | 5 | Timezone deadline (local-past rejects, local-future passes); `update_status` gates (confirm required, unpaid online blocked, succeeded-payment control) |
| `test_reports.py` | 5 | Scope resolution: single-assignment default (manager/staff), unassigned denied, admin university-wide control, all 5 endpoints resolved |
| `test_inventory.py` | 2 | Locked-select NotFound path; sequential accumulation (10+7−4=13) |

**Total: 24 new tests** (597 = 573 baseline + 24).

## 19. Test Adjustments & Justification

- **7 existing `test_orders.py` call sites** had a `POST /orders/{id}/confirm` step inserted before `PUT .../status → preparing`. **Assertions were unchanged** — these tests previously exercised the buggy bypass path; they now follow the documented confirm-then-prepare workflow. This corrects test premises, not assertions; nothing was weakened.
- **`test_manager_multiple_assignments_must_specify` removed.** The schema enforces `UNIQUE(user_id)` on `cafeteria_assignments` (`uq_cafeteria_assignment_user`), so a manager can never hold two assignments — the test asserted an impossible state and failed with `IntegrityError` at insert time. The `>1 assignments` branch in `_resolve_cafeteria_scope` is retained as defense-in-depth (cheap, unreachable under current schema). Removing the impossible test corrects an invalid premise; no valid test was deleted or weakened.
- **Test-internal fixes during development:** inventory accumulation test needed `db.refresh()` (adjustments commit in the app session, separate from the test session — identity-map staleness, not a product bug); timezone tests derive date/time from local datetimes to avoid midnight-rollover flakes. These are test-correctness fixes; final assertions unchanged.

**Failure classification used:** all interim failures were classified as *test-premise defects* (invalid fixture state, stale identity map, missing local imports) — none were genuine product regressions, flaky-time-dependent failures, environment-only issues, or blocked external dependencies in the final run.

## 20. Post-Fix Validation Results

| Validation | Pre-Fix | Post-Fix |
|---|---|---|
| Backend pytest (full) | 573 passed | **597 passed** in 292.86s |
| E2E (31 checks) | 31/31 PASS | **31/31 PASS** |
| Web `tsc --noEmit` | EXIT=0 | **EXIT=0** |
| Web `next build` | EXIT=0 | **EXIT=0** (all 22 routes) |
| Mobile `type-check` | EXIT=0 | **EXIT=0** |

All five post-fix validations green. No genuine regressions, no flaky-time-dependent failures, no environment-only failures, and no blocked external dependencies in the final validation run.

## 21. Remaining Limitations, Observations & Next Phase

**Blocked externally (NOT fixed — recorded):**
- **JazzCash provider integration** remains blocked on the provider's technical-access response (Phase 26B request delivered). Until credentials and endpoint contracts arrive, online payments cannot be enabled for production. UniServe must not be described as fully production-ready while this dependency is unresolved.
- **Payment webhook inventory-reservation failure path** (observed during frozen-state inspection): if `_reserve_inventory_for_online_payment` raises inside `handle_payment_success`, `process_webhook`'s except treats it as a terminal state and marks the webhook processed while the payment stays `SUCCEEDED` with `inventory_reserved=False`. This is a payment-module concern and is deferred to the provider-integration phase per the freeze constraint.

**Minor observations (not fixed — negligible practical risk):**
- `cancel_order` raises `ValidationError` (400) instead of masked `AuthorizationError` (403) for non-owners; order UUIDs are v4 random/unguessable.
- `_allocate_order_number` docstring says "SELECT FOR UPDATE" but code uses a raw atomic UPDATE — safe at SQL level; comment slightly inaccurate.

**Commit:** `fix: resolve non-payment release readiness issues` — 11 files (6 source + 5 test), +848/−32 lines.

**Exact next technical phase:** Phase 28 — JazzCash provider integration, executed only after the provider's technical-access response (credentials, endpoints, signature scheme, webhook contract) is received and the frozen payment contract is unfrozen. Until then, the production fail-closed guard (503 on test provider in production) remains the correct and final state.
