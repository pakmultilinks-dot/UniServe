# UniServe — Final Project Metrics

**Source of truth:** Phase 62 verification cycle (development CLOSED — READY WITH KNOWN LIMITATIONS). All values below were verified through automated test runs, browser/API role rehearsals, and end-to-end exercises recorded in the Phase 62 evidence documents. **No estimated, projected, or invented numbers appear in this document.**

**Capture date of live-state values:** 2026-10-08 (demo environment).

---

## 1. Automated test results (Phase 62)

| Suite | Framework | Result | Notes |
|---|---|---|---|
| Backend API | Pytest | **872 passed, 5 skipped** | Full backend suite |
| Web console | Vitest | **40/40 passed** | Unit/component tests |
| Web console | TypeScript (`tsc`) | **0 errors** | Strict compile check |
| Web console | ESLint | **0 errors**, 95 warnings | Warnings are known, non-blocking |
| Mobile app | Jest | **34/34 passed** (`--runInBand`) | Memory-safe serial execution |
| Mobile app | TypeScript (`tsc`) | **0 errors** | Strict compile check |
| Mobile app | ESLint | **0 errors**, 61 warnings | Warnings are known, non-blocking |
| Shared types | Vitest | **13/13 passed** | Cross-package type tests |

**Aggregate automated test count:** 872 + 40 + 34 + 13 = **959 tests passing** (plus 5 backend skips, by design).

---

## 2. Security & access control (RBAC)

| Check | Result |
|---|---|
| Forbidden cross-role API probes | **13/13 returned HTTP 403** |
| Unauthenticated API request | HTTP 401 — `{"detail":"Invalid authorization header","code":"AUTHENTICATION_ERROR"}` (verified live) |
| Unauthenticated web access to admin route | Redirect to `/login?redirect=%2Fdashboard%2Fadmin%2Fusers` (verified live, screenshot `12-security/unauthenticated-redirect-to-login.png`) |
| Staff on `/dashboard/admin/users` | Client-side route guard redirects to `/dashboard` (verified live) |
| Manager on `/dashboard/admin/reports` | "Access denied" (verified live, screenshot `12-security/rbac-manager-on-admin-reports-route.png`) |

---

## 3. Role rehearsals (browser + API, Phase 62)

| Role | Scenarios verified | Result |
|---|---|---|
| Admin (web console) | 8 browser scenarios — dashboard, users, cafeterias, inventory, refunds, reports, audit, settings | **8/8** |
| Manager (API) | 7 scenarios — cafeteria-scoped operations + denied admin paths | **7/7** |
| Cafeteria Staff (API) | 5 scenarios — queue operations within assigned cafeteria | **5/5** |
| Student (API) | 4 scenarios — ordering journey within scope | **4/4** |
| Faculty (API) | 3 scenarios — dual-cafeteria access | **3/3** |

---

## 4. End-to-end order lifecycle (Phase 62)

| Attribute | Value |
|---|---|
| Order | **#31** (UUID `caec2a1e-20c0-461a-913c-d2d0a0220834`) |
| Payment method | Cash |
| Order value | PKR 80 |
| Status path | **PENDING → PREPARING → READY → COMPLETED** |
| Audit trail | **7 events** recorded for the order |
| Notifications generated | **2** to the order owner |
| Integration suites (Phase 60, gated) | **5/5 passed** |

---

## 5. Live demo-database census (read-only, 2026-10-08)

| Entity | Count |
|---|---|
| Users | 18 |
| Orders | 52 |
| Payments | 39 |
| Refunds | 4 |
| Notifications | 150 |
| Audit events | 844 |
| Sessions | 383 |
| Alembic migration head | 0013 |
| Menu items | 35 |
| Cafeterias | 3 (incl. 1 known test-residue cafeteria, F-61-06) |

**Menu state note (honest):** latest **published** daily menus are dated **2026-10-06** (Faculty + Student cafeterias). The mobile app correctly shows "Menu not published yet" for any later date — this is truthful live state, not a defect being hidden.

---

## 6. Live environment verification (2026-10-08)

| Component | State |
|---|---|
| API health | `{"status":"ready","service":"uniserve-api","database":"connected","schema":"present"}` |
| API container | `uniserve_api` — image `uniserve-prod-api` built from HEAD `bc967b35` |
| Database container | `uniserve_postgres` — postgres:16-alpine, DB `uniserve_prod` |
| Web console | Next.js 14.2.35 dev server responding on `:3000` |
| Mobile demo | Expo web (react-native-web build) responding on `:8081` |
| Presentation screenshots | **41 captures** from the running application in `presentation/` |

---

## 7. Known-limitations register (status snapshot)

| Metric | Value |
|---|---|
| Total open items | **15** (F-61-02 … F-61-16) |
| Closed this cycle | F-61-01 (closed) |
| Demo-blocking items | **0** |
| Demo-visible items | 5 (F-61-04 stale pending payments, F-61-06 E2E cafeteria residue, F-61-08 itemless cancelled orders, F-61-10 sparse dietary/allergen metadata, F-61-16 residue accounts) |

---

## 8. Explicitly NOT claimed

Consistent with the evidence-based presentation constraint, the following are **not** claimed anywhere in this package — and must not be stated in the demo:

- ❌ No production uptime, availability, or SLA figures — this is a local demo environment.
- ❌ No performance benchmarks (latency, throughput, concurrent users) — not measured at production scale.
- ❌ No scalability claims — no load testing has been run.
- ❌ No real payment volume, settlement, or live JazzCash integration — payments are test/E2E data; online path is fail-closed (503 when unconfigured).
- ❌ No production deployment claim — Docker Compose configuration exists; production hardening is roadmap.
- ❌ No mobile-app-store distribution — demoed via Expo web on this machine (no Android emulator available).
- ❌ No user-acceptance statistics from real campus users — role rehearsals were performed by the engineering team.

---

## 9. Git integrity baseline (for post-demo verification)

| Item | Expected value |
|---|---|
| Git HEAD | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (branch `main`) |
| package-lock.json SHA-256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` |
| Working-tree expectation after presentation task | Tracked files unchanged; only new untracked presentation artifacts (markdown package + `presentation/` screenshots) |
