# UniServe — Presentation Content (15 Slides)

**Purpose:** Speaker-ready slide content for the UniServe final demo. Every screenshot reference points to a real capture in the `presentation/` folder (taken from the running application, 2026-10-08). No fabricated metrics. Factual stack only.

**Presenter reminders:**
- Web console: `http://localhost:3000` · Mobile app (Expo web): `http://localhost:8081` · API health: `http://localhost:8000/api/v1/health` (see `LIVE_DEMO_RUNBOOK.md`).
- Demo passwords are committed test fixtures (see `DEMO_ACCOUNTS.md`) — they are not secrets, but do not display them on a projected screen.
- If "Menu not published yet" appears on mobile, that is honest live state (latest published menu: 2026-10-06). Publish via the manager console if a live menu is needed.

---

## Slide 1 — Title

**Title:** UniServe — Mobile-First Campus Cafeteria Ordering Platform

**Bullets:**
- Lahore Garrison University — campus food ordering, end to end
- Students & faculty order from mobile · Staff & managers fulfill · Admin governs
- Built on FastAPI + PostgreSQL + Next.js + React Native/Expo
- Phase 62 status: READY WITH KNOWN LIMITATIONS — verified end to end

**Recommended screenshot:** `presentation/02-login/01-login-page.png`

**Speaker notes:** "UniServe is a running system, not a mockup. Everything you'll see today was captured from the live application on the demo machine behind me."

**Transition:** "Let's start with why this system needs to exist."

---

## Slide 2 — The Problem

**Title:** Campus cafeterias run on queues and paper

**Bullets:**
- Students and faculty lose break time standing in line
- Staff lose track of orders during rush periods
- Managers can't see what sold, what's stale, what's missing
- No auditable record: who ordered, when, paid how, refunded why
- Payments, refunds, notifications, and inventory live in disconnected tools

**Recommended screenshot:** none (narrative slide)

**Speaker notes:** "This is the everyday reality at campus cafeterias — and it gets worse at rush hour. The university has no single system of record for any of it."

**Transition:** "UniServe replaces the queue with one platform."

---

## Slide 3 — The Solution

**Title:** One platform, five roles

**Bullets:**
- **UniServe is a mobile-first campus cafeteria ordering platform:** students and faculty order from their phones; cafeteria staff fulfill orders in real time; managers run their cafeteria; and the university administers users, cafeterias, and audit — all on one FastAPI + PostgreSQL backend with role-based access control
- Mobile app for the two customer roles (students, faculty)
- Web console for the three operational roles (staff, manager, admin)
- One backend, one database, one audit trail

**Recommended screenshot:** `presentation/07-admin/01-dashboard-overview.png`

**Speaker notes:** "One sentence defines the product — and one backend powers all five roles. Nobody is working from a different source of truth."

**Transition:** "Here's how the pieces fit together."

---

## Slide 4 — How It Works (Architecture)

**Title:** Architecture at a glance

**Bullets:**
- **Mobile:** React Native 0.86.3 + Expo SDK 57 — students & faculty
- **Web console:** Next.js 14 — staff, manager, admin (different dashboards per role)
- **API:** FastAPI (Python) — JWT auth, RBAC guards, orders, payments, refunds, notifications, audit
- **Database:** PostgreSQL 16 — SQLAlchemy async, Alembic migrations (at 0013)
- **Deployment:** Docker & Docker Compose (API + PostgreSQL containers verified live)

**Recommended screenshot:** `presentation/13-final/api-health-ready.png`

**Speaker notes:** "The health endpoint on screen says it all: status ready, database connected, schema present. This stack is what's running right now on the demo machine."

**Transition:** "Now the part that matters most — who can do what."

---

## Slide 5 — Five Roles, One Platform

**Title:** Role-based by design

**Bullets:**
- **Student** — mobile: browse, order, track, notify
- **Faculty** — mobile: same experience + access to **both** cafeterias
- **Cafeteria Staff** — web: order queue for their assigned cafeteria only
- **Manager** — web: full oversight of their cafeteria
- **University Admin** — web: users, cafeterias, refunds, reports, audit — system-wide

**Recommended screenshot:** `presentation/05-staff/staff-dashboard.png`

**Speaker notes:** "Staff see one cafeteria and three active orders — the console is scoped to their job. Compare that with the admin dashboard: three cafeterias, system-wide. Same platform, different lenses."

**Transition:** "Let's walk the student experience first."

---

## Slide 6 — Student Experience (Mobile)

**Title:** Three taps from hungry to eating

**Bullets:**
- Login with LGU student email (invalid credentials → clear inline error)
- Home: cafeteria switcher, search, category chips (Breakfast → Soup)
- Menu items priced in PKR; favorites for quick reorder
- Order history with live status badges (Confirmed → Completed)
- In-app notifications with unread badge + Mark All Read
- Profile: University ID, verified email, security actions (PIN login, sign-out-all)

**Recommended screenshots:**
- `presentation/03-student/mobile-home-cafeterias.png`
- `presentation/03-student/mobile-orders-history.png`
- `presentation/03-student/mobile-notifications.png`
- `presentation/03-student/mobile-profile.png`

**Speaker notes:** "Students get the full consumer-app experience — switcher, search, categories, favorites. The order history shows real seeded orders with status transitions. One honest note: today's menu shows 'not published yet' because the latest published menu is October 6th — the app correctly refuses to show a menu that doesn't exist."

**Transition:** "Faculty get the same experience — with one important difference."

---

## Slide 7 — Faculty Experience (Mobile)

**Title:** Faculty order too — across both cafeterias

**Bullets:**
- Same mobile app, LGU faculty email login
- Defaults to **Faculty Cafeteria** (Administration Block, 1st Floor)
- **Cafeteria switcher includes both** Faculty and Student cafeterias
- Full order history + notification inbox
- Web console redirects faculty to "Use the Mobile App" — mobile-first by design

**Recommended screenshots:**
- `presentation/04-faculty/faculty-mobile-home.png`
- `presentation/04-faculty/faculty-mobile-cafeteria-picker.png`
- `presentation/04-faculty/faculty-web-view.png`

**Speaker notes:** "The switcher on screen is the differentiator: faculty can choose either cafeteria. If you spot 'Phase 56 E2E Cafeteria' in the list — that's documented test residue on our cleanup register, not a real cafeteria. And when faculty open the web console, they're routed to the mobile app — the console is intentionally for operations roles."

**Transition:** "Behind the app, cafeteria staff keep orders moving."

---

## Slide 8 — Cafeteria Operations (Staff Console)

**Title:** The order queue is the heartbeat

**Bullets:**
- Staff dashboard scoped to their cafeteria (Ahmed → Student Cafeteria)
- Live Order Queue: PENDING → PREPARING → READY → COMPLETED
- Staff manage today's menu and inventory for their cafeteria
- Route guard: staff navigating to admin URLs are redirected to their dashboard
- API-level RBAC: 13/13 forbidden cross-role probes returned HTTP 403

**Recommended screenshots:**
- `presentation/05-staff/staff-order-queue.png`
- `presentation/12-security/rbac-staff-on-admin-users-route.png`

**Speaker notes:** "The queue on screen is the real fulfillment board. And security isn't UI-deep: we ran 13 automated probes where a student token hits admin endpoints — all 13 were rejected with 403 by the backend itself. The redirect screenshot proves the UI layer enforces it too."

**Transition:** "Managers see more — but only their cafeteria."

---

## Slide 9 — Manager Console

**Title:** Cafeteria ownership, clearly bounded

**Bullets:**
- Manager dashboard scoped to Faculty Cafeteria (Sana Malik)
- Order queue + cafeterias view for their operation
- Menu and inventory oversight for their cafeteria
- **Boundary enforced:** managers get "Access denied" on admin-wide reports

**Recommended screenshots:**
- `presentation/06-manager/manager-dashboard.png`
- `presentation/12-security/rbac-manager-on-admin-reports-route.png`

**Speaker notes:** "Notice the 'Access denied' screen — a manager clicking Reports doesn't get a filtered view, they get refused. That's deliberate: university-wide analytics belong to the admin. Permissions are decided by role, not by UI convenience."

**Transition:** "Which brings us to the university admin — the control room."

---

## Slide 10 — University Admin Console

**Title:** The university's control room

**Bullets:**
- Dashboard: 3 cafeterias · active orders · unread notifications at a glance
- Users ("Members") administration — 18 users in the demo database
- Cafeterias + inventory administration across campus
- Refund Management console + Reports & Analytics (admin-only)
- Settings: Active Sessions table (383 sessions recorded)
- Audit Log: append-only trail (844 audit events)

**Recommended screenshots:**
- `presentation/07-admin/01-dashboard-overview.png`
- `presentation/07-admin/users-administration.png`
- `presentation/07-admin/settings-administration.png`
- `presentation/12-security/audit-log.png`

**Speaker notes:** "Everything the university needs to govern the system is here — and the audit log is the piece institutions care about most: who did what, when, recorded append-only. Some seeded test accounts visible in the user list are on our cleanup register; that's honest demo state."

**Transition:** "Two subsystems deserve their own slides — notifications and refunds."

---

## Slide 11 — Notifications & Refunds

**Title:** Feedback loop and money safety

**Bullets:**
- **Notifications:** in-app inbox (mobile) + admin Broadcast console (university-wide messages)
- E2E order #31 generated 2 notifications to the order owner as status advanced
- Engineering honesty: a delivery-gap defect was found in Phase 61 verification, fixed in 61A, re-verified — this is what end-to-end rehearsal is for
- **Payments/refunds:** verified as a *workflow* with test data — order #31 was a cash order (PKR 80); 4 refund records exist from test flows
- Online payments are **fail-closed**: unconfigured/unreachable payment provider → HTTP 503, never a fake success

**Recommended screenshots:**
- `presentation/09-notifications/notifications-inbox.png`
- `presentation/09-notifications/broadcast-console.png`
- `presentation/10-refunds/refunds-console.png`

**Speaker notes:** "On notifications: we found our own bug during verification — a delivery gap — fixed it in the next phase, and re-verified. That's the process working. On money: we do not claim live payments. The safety behavior we'd ship is fail-closed — refuse rather than pretend. The refund console exists precisely because test payments need test refunds."

**Transition:** "Numbers are only useful to the right audience."

---

## Slide 12 — Reports & Analytics

**Title:** Right numbers, right people

**Bullets:**
- Admin-only Reports & Analytics screen (managers: "Access denied")
- Demo database: 52 orders · 39 payments · 3 cafeterias · 18 users — real chart shapes, not placeholders
- Order and cafeteria activity aggregated university-wide
- Scope discipline is a feature: operational views ≠ governance views

**Recommended screenshot:** `presentation/11-reports/reports-analytics.png`

**Speaker notes:** "The report on screen aggregates real seeded and E2E order activity. And remember slide 9 — this screen is admin-only on purpose. Visibility is a permission."

**Transition:** "Let's look at what's underneath — the technology and the proof."

---

## Slide 13 — Technology Architecture

**Title:** Boring technology, well-orchestrated

**Bullets:**
- **Backend:** FastAPI · SQLAlchemy async · Alembic (migration 0013) · PostgreSQL 16
- **AuthN/AuthZ:** JWT (access + refresh) + role-based access control on every sensitive endpoint
- **Web:** Next.js 14 (App Router) — role-scoped dashboards
- **Mobile:** React Native 0.86.3 + Expo SDK 57 — runs on iOS/Android; demoed via Expo web on this machine (no emulator required)
- **Infra:** Docker Compose — API + PostgreSQL containers; health-checked before every demo
- **Data safety:** session tracking (383 sessions), audit events (844), append-only audit model

**Recommended screenshot:** `presentation/13-final/api-health.png`

**Speaker notes:** "Nothing here is exotic — FastAPI, Postgres, Next.js, React Native — and that's the point. The discipline is in the RBAC layer, the audit trail, and the migrations. The health endpoint on screen is what we check before every rehearsal."

**Transition:** "A system is only as good as its proof."

---

## Slide 14 — Testing & Reliability

**Title:** Verified, not assumed

**Bullets:**
- **Backend:** 872 Pytest tests passed, 5 skipped
- **Web console:** 40/40 Vitest · TypeScript 0 errors · ESLint 0 errors
- **Mobile:** 34/34 Jest · TypeScript 0 errors · ESLint 0 errors
- **Shared types:** 13/13 Vitest
- **RBAC probes:** 13/13 forbidden calls → HTTP 403
- **Role rehearsals:** admin 8/8 · manager 7/7 · staff 5/5 · student 4/4 · faculty 3/3
- **E2E order #31:** PENDING → PREPARING → READY → COMPLETED · 7-event audit trail · 2 notifications

**Recommended screenshot:** `presentation/13-final/api-health-ready.png`

**Speaker notes:** "These aren't projections — they're the Phase 62 verification results. Order #31 walked the entire lifecycle in our end-to-end rehearsal and left a seven-event audit trail behind it. That's the difference between 'it works' and 'we proved it works.'"

**Transition:** "And the honest picture — including what isn't done."

---

## Slide 15 — Final Value & Honest Roadmap

**Title:** What UniServe delivers — and what's next

**Bullets:**
- **Delivers now:** mobile ordering for students & faculty · real-time fulfillment for staff · cafeteria management for managers · governance, audit & analytics for the university
- **Proven:** 959+ automated tests green · RBAC enforced at API and UI · full order lifecycle E2E · audit trail on every sensitive action
- **Honest known limitations (15 open, documented):** no live payment-merchant integration (fail-closed by design) · test-residue records visible in demo data · sparse menu dietary metadata · in-app notifications only (no mobile push yet)
- **Roadmap:** live JazzCash merchant integration · production deployment hardening · menu metadata completion · test-data cleanup · push notifications
- **Every screenshot in this deck came from the running application**

**Recommended screenshot:** `presentation/03-student/mobile-menu-browse.png` (honest empty state) or `presentation/07-admin/overview-administration.png`

**Speaker notes:** "We close where we started: this is a running system with real tests and real access control — and a written register of everything that isn't finished. If you take one thing away: we would rather show you an honest empty state than a pretty lie. Thank you — questions welcome."

**Transition:** (End — open for Q&A; see `EVALUATOR_CHEAT_SHEET.md`.)

---

## Appendix — Slide-to-screenshot index

| Slide | Screenshots |
|---|---|
| 1 | `02-login/01-login-page.png` |
| 3 | `07-admin/01-dashboard-overview.png` |
| 4 | `13-final/api-health-ready.png` |
| 5 | `05-staff/staff-dashboard.png` |
| 6 | `03-student/mobile-home-cafeterias.png`, `mobile-orders-history.png`, `mobile-notifications.png`, `mobile-profile.png` |
| 7 | `04-faculty/faculty-mobile-home.png`, `faculty-mobile-cafeteria-picker.png`, `faculty-web-view.png` |
| 8 | `05-staff/staff-order-queue.png`, `12-security/rbac-staff-on-admin-users-route.png` |
| 9 | `06-manager/manager-dashboard.png`, `12-security/rbac-manager-on-admin-reports-route.png` |
| 10 | `07-admin/01-dashboard-overview.png`, `users-administration.png`, `settings-administration.png`, `12-security/audit-log.png` |
| 11 | `09-notifications/notifications-inbox.png`, `broadcast-console.png`, `10-refunds/refunds-console.png` |
| 12 | `11-reports/reports-analytics.png` |
| 13 | `13-final/api-health.png` |
| 14 | `13-final/api-health-ready.png` |
| 15 | `03-student/mobile-menu-browse.png`, `07-admin/overview-administration.png` |
