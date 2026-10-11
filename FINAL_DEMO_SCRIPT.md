# UniServe — Final Demo Script

**Status:** Phase 62 concluded — READY WITH KNOWN LIMITATIONS. This script is for presentation rehearsal only.
**Local runtime:** Docker (`uniserve_api` + `uniserve_postgres`) on `localhost:8000` / `localhost:5433`; Next.js web console on `localhost:3000`; Expo web (mobile app) on `localhost:8081`.
**Screenshot evidence:** `presentation/` folder (41 captures from the running application, 2026-10-08).

> **Presenter rule:** Show only what is on screen. Do not click landmines (`npx next build`, `docker compose down -v`, `.env` files). Do not alter data to improve appearance. If asked about anything in the Known Limitations section, answer honestly using the wording provided.

---

## 1. Problem

Campus cafeterias at Lahore Garrison University run on paper queues and ad-hoc ordering. Students and faculty wait in line during short breaks, cafeteria staff lose track of orders, managers cannot see what is selling or stale, and the university has no auditable record of who ordered what, when, or paid how. Payments, refunds, notifications, and inventory are handled in disconnected tools or not at all.

**Say:** *"UniServe replaces that paper queue with one platform — mobile ordering for students and faculty, an operations console for cafeteria staff and managers, and a university-wide administration and audit layer."*

**Screenshot:** none required (narrative slide) — or `presentation/02-login/01-login-page.png` as a product-teaser.

---

## 2. Solution — the one-sentence quote

> **UniServe is a mobile-first campus cafeteria ordering platform: students and faculty order from their phones; cafeteria staff fulfill orders in real time; managers run their cafeteria; and the university administers users, cafeterias, and audit — all on one FastAPI + PostgreSQL backend with role-based access control.**

---

## 3. System Overview

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│  MOBILE APP (React      │   │  WEB CONSOLE (Next.js   │   │  WEB CONSOLE (Next.js   │
│  Native + Expo)         │   │  14) — Staff & Manager  │   │  14) — University Admin │
│  Students & Faculty     │   │  Order queue, menus,    │   │  Users, cafeterias,     │
│  Browse, order, pay,    │   │  inventory, broadcasts  │   │  inventory, refunds,    │
│  track, notify          │   │                         │   │  reports, audit, settings│
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            │            HTTPS/JSON (JWT bearer tokens)                 │
            └──────────────────────┬────────────────────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  FASTAPI BACKEND (uniserve_api)│
                    │  JWT auth · RBAC guards        │
                    │  Orders · Payments · Refunds   │
                    │  Notifications · Audit log     │
                    └──────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  POSTGRESQL 16 (uniserve_postgres)│
                    │  SQLAlchemy async · Alembic 0013  │
                    └──────────────────────────────┘
```

**Stack (factual):** Next.js 14 (web console) · React Native 0.86.3 + Expo SDK 57 (mobile) · FastAPI (Python) · PostgreSQL 16 · SQLAlchemy async · Alembic (migration 0013) · JWT authentication + role-based access control · Pytest / Vitest / React Testing Library / Jest · Docker & Docker Compose.

---

## 4. Role-Based Experience — five roles, one platform

| Role | Surface | What they do in the demo |
|---|---|---|
| **Student** | Mobile app | Browse cafeteria menu, place an order, track status, receive notifications, view order history |
| **Faculty** | Mobile app | Same ordering experience; can access **both** cafeterias (Faculty + Student) |
| **Cafeteria Staff** | Web console | Work the Order Queue — accept, prepare, mark ready; manage today's menu and inventory for their assigned cafeteria |
| **Manager** | Web console | Oversee their cafeteria — order queue, cafeterias view, menu/inventory oversight |
| **University Admin** | Web console | System-wide: users, cafeterias, inventory, refunds, reports & analytics, audit log, active sessions |

**Screenshot:** `presentation/07-admin/01-dashboard-overview.png` (admin dashboard — "3 cafeterias · 3 active orders").

---

## 5. Student Journey (mobile app)

**Start:** `presentation/03-student/` folder.

1. **Login screen** — "Welcome Back!", LGU student email + password. Invalid credentials show an inline error (captured). *(Screenshot: `02-login/02-login-error-invalid-password.png`)*
2. **Web console redirect** — when a student opens the web console they are routed to `/mobile-required` ("Use the Mobile App"). The web console is intentionally staff/manager/admin-only. *(Screenshot: `03-student/student-web-mobile-required.png`)*
3. **Mobile home** — cafeteria switcher ("Current cafeteria: Student Cafeteria · Block B, Ground Floor. Tap to change."), search box, category chips (All / Breakfast / Main / Sides / Desserts / Drinks / Snacks / Salad / Soup). *(Screenshots: `mobile-home-cafeterias.png`, `mobile-cafeteria-picker.png`)*
4. **Menu browse** — category-filtered menu items with prices in PKR. *Honest note:* as of the capture date (2026-10-08) no menu has been published for today, so the app correctly shows the "Menu not published yet — today's menu hasn't been published. Check back later!" empty state. The most recent published menus in the database are dated 2026-10-06. **Do not fabricate a menu for the demo** — if a live menu is needed, publish one through the manager console during rehearsal, not by editing data directly. *(Screenshot: `mobile-menu-browse.png`)*
5. **Order history** — past orders with status badges (Cancelled / Confirmed → Completed) and PKR totals. *(Screenshot: `mobile-orders-history.png`)*
6. **Notifications** — in-app notification inbox with unread badge and "Mark All Read". *(Screenshot: `mobile-notifications.png`)*
7. **Favorites & Profile** — saved menu items for quick reorder; profile shows University ID (FA22-001), verified email, category, security actions (Change Password, PIN Login, Sign Out All Devices). *(Screenshots: `mobile-favorites.png`, `mobile-profile.png`)*

**Say:** *"Ordering takes three taps: pick the cafeteria, pick the item, confirm. Everything after that — preparation, ready-for-pickup, completion — is tracked and pushed back as a notification."*

---

## 6. Faculty Journey (mobile app)

**Start:** `presentation/04-faculty/` folder.

1. Faculty log into the **same mobile app** with their LGU email (`dr.sana.malik@lgu.edu.pk` — committed demo fixture). *(Screenshot: `faculty-mobile-login.png`)*
2. Home defaults to **Faculty Cafeteria · Administration Block, 1st Floor**. *(Screenshot: `faculty-mobile-home.png`)*
3. **Key differentiator:** the cafeteria switcher shows faculty can select **both** cafeterias — Faculty Cafeteria and Student Cafeteria. *(Screenshot: `faculty-mobile-cafeteria-picker.png`)*
   - *Honest note:* the picker also lists "Phase 56 E2E Cafeteria" — this is known test residue (limitation F-61-06), documented and scheduled for cleanup. If an evaluator notices it: *"That's a leftover from our end-to-end test suite; it's on our known-limitations register and will be removed before any real deployment."*
4. **Order history** — faculty order records with statuses and PKR totals. *(Screenshot: `faculty-mobile-orders.png`)*
5. **Notifications** — faculty notification inbox. *(Screenshot: `faculty-mobile-notifications.png`)*

**Say:** *"Faculty are not second-class users — they get the full ordering experience, and unlike students they can switch between both campus cafeterias."*

---

## 7. Cafeteria Staff (web console)

**Start:** `presentation/05-staff/` folder. Log in as `ahmed.raza@lgu.edu.pk` (Cafeteria Staff, Student Cafeteria).

1. **Dashboard** — "Good morning, Ahmed", scoped to **1 cafeteria · 3 active orders**. Staff only see their assigned cafeteria — not the whole system. *(Screenshot: `staff-dashboard.png`)*
2. **Order Queue** — the live fulfillment board: orders in PENDING → PREPARING → READY → COMPLETED flow. *(Screenshot: `staff-order-queue.png`)*
3. **RBAC check (staff):** if a staff user manually navigates to `/dashboard/admin/users`, the client-side route guard redirects them to `/dashboard`. They cannot reach admin screens. *(Screenshot: `12-security/rbac-staff-on-admin-users-route.png`)*

**Say:** *"The staff console is deliberately narrow — one cafeteria, one job: work the queue. Access control is enforced both in the UI routing and, as we'll see, at the API."*

---

## 8. Manager (web console)

**Start:** `presentation/06-manager/` folder. Log in as `sana.malik@lgu.edu.pk` (Manager, Faculty Cafeteria).

1. **Dashboard** — manager overview scoped to Faculty Cafeteria. *(Screenshot: `manager-dashboard.png`)*
2. **Order Queue** — cafeteria-wide order oversight. *(Screenshot: `manager-order-queue.png`)*
3. **Cafeterias view** — cafeteria records under management. *(Screenshot: `manager-cafeterias.png`)*
4. **RBAC check (manager):** navigating to `/dashboard/admin/reports` shows **"Access denied"** — reports are admin-only. Managers get cafeteria-scoped data, not university-wide analytics. *(Screenshot: `12-security/rbac-manager-on-admin-reports-route.png`)*

**Say:** *"Managers own their cafeteria. They can see everything happening in their operation — but university-wide analytics and user administration stay with the admin."*

---

## 9. University Admin (web console)

**Start:** `presentation/07-admin/` folder. Log in as `admin@lgu.edu.pk` (System Administrator).

1. **Dashboard overview** — "Good morning, System": 3 cafeterias · 3 active orders · 2 unread notifications. *(Screenshot: `01-dashboard-overview.png`)*
2. **Users administration** — "Members": the user directory (18 users in the demo database) with roles. *Honest note:* some seeded/residue accounts appear here (limitation F-61-16) — if asked: *"Some seeded test accounts remain from our verification phases; they're on the cleanup list."* *(Screenshot: `users-administration.png`)*
3. **Cafeterias administration** — cafeteria records system-wide. *(Screenshot: `cafeterias-administration.png`)*
4. **Inventory administration** — inventory oversight across cafeterias. *(Screenshot: `inventory-administration.png`)*
5. **Administration overview** — cross-cutting admin summary. *(Screenshot: `overview-administration.png`)*
6. **Settings / Active Sessions** — session management table (383 sessions recorded in the demo DB). *(Screenshot: `settings-administration.png`)*
7. **Refund Management** — admin refund console (see Section 13 for honest framing). *(Screenshot: `10-refunds/refunds-console.png`)*
8. **Reports & Analytics** — university-wide reporting. *(Screenshot: `11-reports/reports-analytics.png`)*
9. **Audit Log** — append-only audit trail (844 audit events in the demo DB). *(Screenshot: `12-security/audit-log.png`)*

**Say:** *"The admin console is the university's control room: who uses the system, which cafeterias exist, what inventory is tracked, which refunds need approval, what the numbers say, and — critically — an audit log of what happened."*

---

## 10. Security & Role-Based Access Control

**Say:** *"Access control is not cosmetic. We verified it two ways."*

**Evidence 1 — API-level (automated):** 13/13 forbidden cross-role API probes returned **HTTP 403** — e.g., a student token calling admin endpoints is rejected by the backend itself, not just hidden by the UI.

**Evidence 2 — browser-level (rehearsed):**
- Unauthenticated access to `/dashboard/admin/users` redirects to `/login?redirect=%2Fdashboard%2Fadmin%2Fusers`. *(Screenshot: `12-security/unauthenticated-redirect-to-login.png`)*
- Unauthenticated API calls return `{"detail":"Invalid authorization header","code":"AUTHENTICATION_ERROR"}` with HTTP 401. *(Screenshot: `12-security/unauthenticated-api-401.png`)*
- Staff on admin routes → redirected to their dashboard. *(Screenshot: `rbac-staff-on-admin-users-route.png`)*
- Manager on admin reports → "Access denied". *(Screenshot: `rbac-manager-on-admin-reports-route.png`)*

**Authentication:** JWT bearer tokens (access + refresh) issued at login, stored by the mobile app in device storage (`uniserve_access_token`, `uniserve_refresh_token`). The API rejects any request without a valid token — verified live.

**Demo DB session/audit numbers:** 383 sessions, 844 audit events — every sensitive action is recorded.

---

## 11. Notifications

**Say:** *"Notifications are the feedback loop of the whole system — the student learns their order is ready without refreshing anything."*

- **What we saw live:** the mobile app shows a notification inbox with an unread badge and "Mark All Read" (`03-student/mobile-notifications.png`, `04-faculty/faculty-mobile-notifications.png`). The E2E order (order #31, see Section 14 metrics) generated **2 notifications to the order owner** as the order progressed.
- **Admin side:** the admin console has a notifications inbox and a **Broadcast** console for university-wide messages (`09-notifications/notifications-inbox.png`, `broadcast-console.png`).
- **Engineering honesty (mention only if asked):** our first notification implementation had a delivery-gap defect (Phase 61). It was found in verification, fixed in Phase 61A, and re-verified — the current build delivers notifications on order-status transitions. This is exactly why we run end-to-end rehearsals: *"We found a bug in our own demo feature and fixed it before showing it to you."*

---

## 12. Analytics & Reporting

**Start:** `presentation/11-reports/reports-analytics.png` (admin-only — managers see "Access denied", Section 8).

- Reports & Analytics screen in the admin console aggregates order and cafeteria activity university-wide.
- The demo database contains **52 orders** and **39 payments** across 18 users and 3 cafeterias — enough to show real chart shapes, not lorem ipsum.
- **Scope discipline:** analytics are admin-only by design. Managers get operational views of their cafeteria; only the admin sees university-wide reporting.

**Say:** *"Numbers only matter if the right people see them — and no one else. That's why reports sit behind the admin role."*

---

## 13. Payments & Refunds — honest framing

**This section must be framed honestly. Do NOT overclaim.**

- **Payments in the demo are test/seed data and E2E-test transactions** — cash-order flow verified end-to-end (order #31 was a **cash** order, PKR 80). No real money has moved.
- **Online payments:** the production payment integration (JazzCash) is **configured fail-closed** — if the payment provider is unreachable or unconfigured, the API returns **503** rather than pretending an order was paid. This is deliberate: *"We would rather refuse than lie about money."*
- **Refunds:** the Refund Management console (`10-refunds/refunds-console.png`) is where authorized staff process refund requests against recorded payments. The demo database contains **4 refund records** — all from test/seed flows.
- **What we do NOT claim:** no real financial settlement, no live JazzCash merchant integration, no production payment volume. Those are future work behind a real merchant account.

**If asked:** *"Payments are verified as a workflow — initiate, record, refund — using test data. The fail-closed 503 on the online path is the safety behavior we'd ship with; going live requires a real payment-merchant integration."*

---

## 14. Final Result — what Phase 62 proved

**Verification evidence (all from the Phase 62 verification cycle — no estimates):**

| Check | Result |
|---|---|
| Backend test suite (Pytest) | **872 passed, 5 skipped** |
| Web console unit tests (Vitest) | **40/40** · TypeScript: **0 errors** · ESLint: **0 errors** |
| Mobile unit tests (Jest) | **34/34** (--runInBand) · TypeScript: **0 errors** · ESLint: **0 errors** |
| Shared-types tests (Vitest) | **13/13** |
| RBAC forbidden-probe suite | **13/13 returned HTTP 403** |
| Role rehearsals (browser/API) | admin **8/8** · manager **7/7** · staff **5/5** · student **4/4** · faculty **3/3** |
| End-to-end order lifecycle | order **#31**: PENDING → PREPARING → READY → COMPLETED, **7-event audit trail**, **2 notifications** to owner |
| API health (live, capture day) | `{"status":"ready","service":"uniserve-api","database":"connected","schema":"present"}` |

**Demo database census (live):** 18 users · 52 orders · 39 payments · 4 refunds · 150 notifications · 844 audit events · 383 sessions · Alembic migration 0013.

**Closing line:** *"UniServe is not a slide — it's a running system. Every screenshot in this deck came from the application you can see behind me. It has real tests, real access control, and a real audit trail. And where it isn't finished — online payments, a few leftover test records — we say so plainly."*

---

## Known Limitations — handling policy for the demo

**Category A — Mention during the demo (only if a viewer sees it on screen):**

| Item | One-line honest wording |
|---|---|
| **F-61-06** — "Phase 56 E2E Cafeteria" visible in cafeteria lists | "Leftover from our end-to-end test suite; on the cleanup register before any real deployment." |
| **F-61-04** — a few stale online-pending orders + one pending refund on order #52 in the refund console | "Seed/test residue from payment-fail-closed testing; it demonstrates exactly why the admin refund console exists." |
| **F-61-10** — sparse dietary/allergen metadata (3/35 items have dietary tags, 2/35 allergens) | "Menu metadata is partially seeded — dietary badges are being completed cafeteria-by-cafeteria." |
| **F-61-16** — residue test accounts in the admin user list | "Seeded verification accounts; scheduled for cleanup." |
| **F-61-08** — itemless cancelled orders in history | "Cancelled orders from early test runs; the cancel flow keeps the record but items were voided." |

**Category B — Keep in technical documentation (do not volunteer):** F-61-02, F-61-03, F-61-05, F-61-07, F-61-09, F-61-11, F-61-12, F-61-13, F-61-14, F-61-15 — these are internal engineering notes (dev-server quirks, test-suite concurrency limits, warning counts) documented in `FINAL_KNOWN_LIMITATIONS.md`. If an evaluator asks directly: *"All open items are in our known-limitations register with owners and severity — none of them blocks the demonstrated functionality."*

**Category C — Future enhancements (frame as roadmap, not defects):** live JazzCash merchant integration, production deployment hardening, dietary/allergen data completion, test-data cleanup, mobile push notifications (current notifications are in-app).

**Menu-date note (repeat):** the capture date shows "Menu not published yet" because the latest published menu is 2026-10-06. This is honest live state. If the demo needs a live menu, publish one via the **manager console** during rehearsal. Never edit the database directly for appearance.
