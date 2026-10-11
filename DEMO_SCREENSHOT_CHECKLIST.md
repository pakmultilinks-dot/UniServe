# DEMO SCREENSHOT CHECKLIST — UniServe

**Phase:** 62 — Demo Readiness, Rehearsal & Final Release Checklist
**Status legend**

| Marker | Meaning |
|---|---|
| **VERIFIED (browser)** | Screen rendering confirmed live in the web console during Phase 62 rehearsal (2026-10-07/08). Demo operator still captures the actual image at show time — this checklist confirms the screen *works*. |
| **VERIFIED (API)** | Endpoint + data confirmed live via authenticated API probes in Phase 62. Screen renders from the same client code paths proven in earlier UI phases. |
| **DEMO-TIME CAPTURE** | Not rendered in this rehearsal (simulator/heavy Metro intentionally not launched). Screen is backed by verified APIs/tests; capture at demo time. |

No screenshots are fabricated or embedded here. All "VERIFIED" markers refer to live checks performed in this phase (probe logs in `%TEMP%\uniserve_p62\`, browser session on `http://localhost:3000`). Credentials: see `FINAL_LOCAL_RUN_GUIDE.md` §7 (emails listed; passwords via `scripts/seed_realistic_data.py`).

**Rehearsal environment:** web dev server `npx next dev` (Next.js 14.2.35, port 3000) · API container `uniserve_api` (`uniserve-prod-api`, healthy, :8000) · postgres `uniserve_postgres` (PG 16, :5433, healthy) · web → API via `apps/web/.env.local`.

---

## 1. University Admin — web console (`http://localhost:3000`)

| # | Screen | Route | What to show | Status |
|---|---|---|---|---|
| A1 | Login | `/login` | Email + password login, error state on bad password | **VERIFIED (browser)** — admin login used to open all sessions below |
| A2 | Dashboard | `/dashboard` | Greeting, 3 stat tiles, Recent Orders, Notifications widget with `admin_announcement` rows | **VERIFIED (browser)** — full render with live data |
| A3 | Orders console | `/dashboard/admin/orders` | Order queue, status filter chips, **Student Cafeteria** cafeteria filter (10 pending at rehearsal time), order detail | **VERIFIED (browser)** |
| A4 | Users administration | `/dashboard/admin/users` | User list with role badges; **residue test accounts are visible in the list** (documented limitation F-61-16 — do not present as production data) | **VERIFIED (browser)** |
| A5 | Refunds console | `/dashboard/admin/refunds` | Pending / processing / rejected refund rows with reasons | **VERIFIED (browser)** — states matched DB (4 refunds) |
| A6 | Reports & analytics | `/dashboard/admin/reports` | Revenue/orders/cancellation stats, sales-by-cafeteria, date filters | **VERIFIED (browser)** — live analytics rendered |
| A7 | Audit log | `/dashboard/admin/audit-log` | Security audit event stream (806 events at rehearsal start; 844 post-rehearsal) | **VERIFIED (browser)** |
| A8 | Notifications inbox | `/dashboard/admin/notifications` | Inbox with unread badge (2 unread), **Mark All Read**, broadcast history incl. `admin_announcement` types | **VERIFIED (browser)** + **VERIFIED (API)** — `/notifications`, `/unread-count`, `/broadcasts`, `/broadcasts/audience-count?audience=all_users\|students` all 200 |
| A9 | Cafeteria administration | `/dashboard/admin/cafeterias` | Cafeteria cards — note **"Phase 56 E2E Cafeteria" appears** (F-61-06 demo-visible) | **VERIFIED (browser)** |

## 2. Cafeteria Manager — web console

| # | Screen | Route | What to show | Status |
|---|---|---|---|---|
| M1 | Login | `/login` | Manager login | **VERIFIED (API)** — token issued, role `cafeteria_manager`, assignment = Faculty Cafeteria |
| M2 | Dashboard / own queue | `/dashboard` (manager scope) | Own-cafeteria stats + order queue | **VERIFIED (API)** — `/auth/me` 200, `/orders/cafeteria/{Faculty}` 200 (queue live), `/orders/` = own orders (0 — expected) |
| M3 | Sales report (own cafeteria) | `/dashboard/manager/reports` | Revenue/volume for assigned cafeteria | **VERIFIED (API)** — `/reports/sales?days=7` 200 (PKR 1,800 net, 4 orders, 100% cash in window) |
| M4 | Low-stock / performance / peak-hours | manager reports tabs | Inventory alerts + lifecycle metrics | **VERIFIED (API)** — `/reports/cafeteria/{Faculty}/inventory/low-stock` 200 (0 items), `/peak-hours` 200, `/performance` 200 |
| M5 | Cross-cafeteria guard | — | Manager **cannot** open another cafeteria's queue | **VERIFIED (API)** — `/orders/cafeteria/{Student}` → 403 `You are not assigned to this cafeteria` |

## 3. Cafeteria Staff — web console

| # | Screen | Route | What to show | Status |
|---|---|---|---|---|
| S1 | Login | `/login` | Staff login | **VERIFIED (API)** — role `cafeteria_staff`, assignment = Student Cafeteria |
| S2 | Order queue (assigned cafeteria) | staff dashboard | Pending → preparing → ready → collect flow | **VERIFIED (API)** — queue 200; **full lifecycle rehearsed live on order #31** (pending → preparing → ready → completed, all 200; DB confirms `completed`, lifecycle events `preparation_started → eta_updated → ready_for_collection → collected`) |
| S3 | Collection by order number / token | collect screen | Staff collect flow | **VERIFIED (API)** — `POST /orders/collect {order_number:31}` → 200 completed |
| S4 | Notifications (staff) | staff notifications | Operational notices incl. `admin_announcement` | **VERIFIED (API)** — `/notifications` 200 (announcement visible) |

## 4. Student — mobile app (Expo) + API

| # | Screen | Where | What to show | Status |
|---|---|---|---|---|
| ST1 | Login | mobile login screen | Student login | **VERIFIED (API)** — role `student`; mobile app compiles clean (`tsc` 0 errors, jest 34/34) |
| ST2 | Cafeteria browse | mobile home | Active cafeterias + menus | **VERIFIED (API)** — `/cafeterias/` 200 (scoped: active cafeterias incl. Phase 56 E2E — F-61-06) |
| ST3 | Cart → checkout | mobile order flow | Cart, payment method (cash/online), order placement | **DEMO-TIME CAPTURE** — flow proven in Phase 58 (51/51 probes, 853 tests); no new orders created in Phase 62 by design |
| ST4 | Order tracking | mobile orders tab | Status timeline + ETA | **VERIFIED (API)** — `/orders/` 200 (owner-scoped), `/orders/{id}/eta` 200 (6 min); owner saw order #31 transition to ready + completed in real time |
| ST5 | Favorites | mobile | Saved menu items | **VERIFIED (API)** — `/favorites/` 200 (live favorites returned) |
| ST6 | Notifications | mobile bell | Refund/order notices | **VERIFIED (API)** — `/notifications?limit=5` 200 (`refund_requested`, order notices) |
| ST7 | Refund request | mobile order detail | Refund reason entry + pending state | **DEMO-TIME CAPTURE** — refund rows live in admin console (A5); Phase 58 evidence |

## 5. Faculty — mobile app + API

| # | Screen | Where | What to show | Status |
|---|---|---|---|---|
| F1 | Login | mobile login screen | Faculty login | **VERIFIED (API)** — role `faculty` |
| F2 | Cafeteria browse | mobile home | Faculty cafeteria menus visible | **VERIFIED (API)** — `/cafeterias/` 200 (Faculty Cafeteria present) |
| F3 | Orders | mobile orders tab | Faculty order history | **VERIFIED (API)** — `/orders/?page=1` 200 |
| F4 | Notifications | mobile bell | Operational notices | **VERIFIED (API)** — `/notifications?limit=5` 200 (`cafeteria_closed` notice) |

## 6. Cross-cutting / negative-path slides (recommended, quick)

| # | Slide | How | Status |
|---|---|---|---|
| X1 | RBAC denials in one frame | Student/manager/staff calling admin endpoints → 403 with role message | **VERIFIED (API)** — 8 forbidden probes all 403 (users, audit-events, system-overview `admin/overview` path, broadcast, refunds/admin/all, cafeteria create) |
| X2 | Unauthenticated → 401 | Any protected endpoint without token | **VERIFIED (API)** — standard JWT enforcement (transient `/auth/me` 401s at web boot are a documented client retry pattern, not a defect) |
| X3 | Notifications broadcast → audience preview | Admin broadcast screen shows recipient count before send | **VERIFIED (API)** — audience-count `all_users`=11, `students`=6 |
| X4 | Backend health | `GET /api/v1/health` + `/health/ready` in terminal | **VERIFIED** — both 200; 0 LookupError in logs since Phase 61A |

## 7. Capture guidance (demo day)

1. Start stack per `FINAL_LOCAL_RUN_GUIDE.md` §4; run the 60-second smoke check (§8) before capturing anything.
2. Capture order: login → dashboard → orders → refunds → reports → audit → notifications → manager → staff (use order #31's completed record as the lifecycle exhibit, or walk any fresh pending order live).
3. Mobile screens (ST3, ST7): launch Expo against the same API (`apps/mobile`, `npx expo start`); backends already verified.
4. Blur/avoid capturing: `.env` files, tokens, `collection_token` values, any password text.
5. If anything on this list fails at capture time, that is a demo blocker → do **not** improvise fixes; re-open Phase 62 evidence trail and stop.
