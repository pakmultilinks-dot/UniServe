# UniServe — Live Demo Runbook

**Purpose:** Step-by-step rehearsal instructions for the live demo, in three durations. Every action references the real running environment. If a live step fails, each beat has a **screenshot fallback** from `presentation/` — the demo never dead-ends.

**Environment quick reference (verified 2026-10-08):**

| Component | URL / endpoint | How it runs |
|---|---|---|
| API | `http://localhost:8000/api/v1/` | Docker container `uniserve_api` (image `uniserve-prod-api`) |
| Database | `localhost:5433` (postgres:16-alpine) | Docker container `uniserve_postgres`, DB `uniserve_prod` |
| API health | `http://localhost:8000/api/v1/health` | expect `{"status":"ready","service":"uniserve-api","database":"connected","schema":"present"}` |
| Web console | `http://localhost:3000` | `npx next dev` in `apps/web` |
| Mobile app (demo) | `http://localhost:8081` | `npx expo start --web --port 8081` in `apps/mobile` |

**Browser pages to pre-open before the audience arrives:**
1. `http://localhost:3000` (web console)
2. `http://localhost:8081` (mobile app)
3. `http://localhost:8000/api/v1/health` (health endpoint — great "it's really running" opener)

**Accounts:** see `DEMO_ACCOUNTS.md`. Students/faculty: `TestPass123!` · Admin: `Admin123!`.

---

## Resilience notes (read once before every rehearsal)

- **First compile is slow.** After starting `next dev` or Expo web, the first page load can take **30–60 seconds** (compilation). Pre-load every page before the demo starts. Subsequent loads are fast.
- **UI click workaround:** in this environment, layout overlay elements can intercept pointer clicks on buttons (Sign In, Log In, tabs). If a click does nothing in rehearsal: press **Enter** in the password field to submit a form, or use a JS click (`el.click()`) via devtools. The mobile app also works via **direct URL navigation**: `http://localhost:8081/orders`, `/notifications`, `/favorites`, `/profile`, `/login`.
- **Mobile empty cafeteria list on first login:** after logging into Expo web, the cafeteria list may briefly show "Find your campus cafe". **Reload the page** (`F5`) — the app attaches the stored token on boot and the list appears. This is a known demo-environment quirk, not a product bug being hidden; mention only if it happens live.
- **"Menu not published yet" on mobile:** the latest published menu in the database is dated **2026-10-06**. For any later demo date the app correctly shows the empty state. **If the demo needs a live menu:** log into the **manager console** and publish a menu through the UI during rehearsal — **never** edit the database directly.
- **Metro disconnect banner:** Expo web may show "Disconnected from Metro" — cosmetic in this demo setup; the page keeps working after reload.
- **Do not "fix" server warnings** (rewrites/middleware warnings, lockfile patch ENOWORKSPACES) — they are known non-blocking noise.

## ⛔ What NOT to click / run (landmines)

| Landmine | Why |
|---|---|
| `npx next build` | Known dual-React defect (F-61-03) + clobbers the running `.next` dev directory |
| `docker compose down -v` | **Destroys the demo database** (volumes) — demo data is unrecoverable |
| `ruff check app` (without `--no-fix`) | May auto-modify source files; demo tree must stay clean |
| `.env` / `.env.local` files on screen | May contain local config; never project them |
| Heavy test suites concurrently | Known memory-flake (F-61-14) on this machine |
| Editing DB rows for appearance | Violates the presentation constraints — show honest state |
| Clicking into "Phase 56 E2E Cafeteria" items | Test residue (F-61-06) — visible in lists is fine; don't build demo beats on it |

---

# 5-Minute Demo (elevator version)

**Goal:** Prove it's real and covers the roles. **Starting page:** health endpoint tab.

| # | Time | Action | Expected result | Screenshot fallback |
|---|---|---|---|---|
| 1 | 0:00–0:30 | Show `http://localhost:8000/api/v1/health` | JSON: `"status":"ready"`, `"database":"connected"`, `"schema":"present"` | `13-final/api-health-ready.png` |
| 2 | 0:30–1:30 | Tab to web console, logged in as **admin** (`admin@lgu.edu.pk` / `Admin123!`) | Dashboard: "Good morning, System" — 3 cafeterias, active orders | `07-admin/01-dashboard-overview.png` |
| 3 | 1:30–2:15 | Open **Users** then **Audit Log** in admin sidebar | Members list (18 users); audit trail (844 events) | `users-administration.png`, `12-security/audit-log.png` |
| 4 | 2:15–3:00 | Show **Reports & Analytics** | Admin-only analytics screen | `11-reports/reports-analytics.png` |
| 5 | 3:00–4:00 | Switch to mobile app tab, logged in as **student** (`ayesha.khan@student.lgu.edu.pk`) | Mobile home: cafeteria switcher, search, categories | `03-student/mobile-home-cafeterias.png` |
| 6 | 4:00–4:40 | Tap **Orders** tab (or goto `http://localhost:8081/orders`) | Order history with status badges + PKR totals | `03-student/mobile-orders-history.png` |
| 7 | 4:40–5:00 | Close on the quote: "Five roles, one platform, 872+ tests green" | — | `presentation/` folder open as backup |

**What NOT to touch in 5-min version:** refunds console, cafeteria switcher dialog, any menu publishing.

---

# 10-Minute Demo (standard version)

**Goal:** Full role tour + security proof. **Starting page:** health endpoint → web console.

| # | Time | Action | Expected result | Screenshot fallback |
|---|---|---|---|---|
| 1 | 0:00–0:40 | Health endpoint + one-line problem statement | `"status":"ready"` JSON | `13-final/api-health-ready.png` |
| 2 | 0:40–1:40 | **Admin** login → dashboard overview | "Good morning, System" — 3 cafeterias / 3 active orders / 2 unread | `07-admin/01-dashboard-overview.png` |
| 3 | 1:40–2:30 | Admin: **Users** → **Cafeterias** → **Settings** (Active Sessions) | Members, cafeteria records, sessions table | `users-administration.png`, `cafeterias-administration.png`, `settings-administration.png` |
| 4 | 2:30–3:15 | Admin: **Reports & Analytics** + **Refund Management** | Analytics screen; refund console (frame test-data honestly — see demo script §13) | `11-reports/reports-analytics.png`, `10-refunds/refunds-console.png` |
| 5 | 3:15–4:15 | Sign out; **staff** login (`ahmed.raza@lgu.edu.pk`) → dashboard + Order Queue | "Good morning, Ahmed"; scoped queue (1 cafeteria / 3 active orders) | `05-staff/staff-dashboard.png`, `staff-order-queue.png` |
| 6 | 4:15–4:45 | Staff RBAC: manually visit `/dashboard/admin/users` | Redirect to `/dashboard` (route guard) | `12-security/rbac-staff-on-admin-users-route.png` |
| 7 | 4:45–5:30 | Sign out; **manager** login (`sana.malik@lgu.edu.pk`) → dashboard; then visit `/dashboard/admin/reports` | Manager dashboard; then **"Access denied"** | `06-manager/manager-dashboard.png`, `12-security/rbac-manager-on-admin-reports-route.png` |
| 8 | 5:30–6:30 | Switch to mobile app; **student** login → home + cafeteria picker | "Student Cafeteria · Block B"; picker lists cafeterias | `03-student/mobile-home-cafeterias.png`, `mobile-cafeteria-picker.png` |
| 9 | 6:30–7:15 | Student: Orders → Notifications tabs | Status history; notification inbox with unread badge | `mobile-orders-history.png`, `mobile-notifications.png` |
| 10 | 7:15–8:15 | Sign out mobile; **faculty** login (`dr.sana.malik@lgu.edu.pk`) → home + switcher | Faculty Cafeteria default; switcher shows **both** cafeterias | `04-faculty/faculty-mobile-home.png`, `faculty-mobile-cafeteria-picker.png` |
| 11 | 8:15–9:00 | Open **unauthenticated** tab: visit `http://localhost:3000/dashboard/admin/users` logged-out (use a private window) | Redirect to `/login?redirect=%2Fdashboard%2Fadmin%2Fusers` | `12-security/unauthenticated-redirect-to-login.png` |
| 12 | 9:00–10:00 | Close: metrics line — "872 backend tests, 13/13 RBAC 403s, order #31 E2E with 7-event audit trail" | — | `13-final/api-health.png` as backdrop |

**What NOT to click in 10-min version:** menu publishing, "Sign Out All Devices" (changes session state for other roles), broadcast send buttons, refund approve buttons.

---

# 15-Minute Demo (full version — adds lifecycle + notifications + honesty beats)

**Goal:** Complete story including E2E order lifecycle narrative, notifications, and known-limitations handling. **Starting page:** health endpoint → web console → mobile.

| # | Time | Action | Expected result | Screenshot fallback |
|---|---|---|---|---|
| 1 | 0:00–1:00 | Health endpoint; problem statement (script §1) | `"status":"ready"` | `13-final/api-health-ready.png` |
| 2 | 1:00–2:30 | **Admin** full tour: dashboard → Users → Cafeterias → Inventory → Administration overview | All admin screens render with live data | `07-admin/*.png` (all six) |
| 3 | 2:30–3:30 | Admin: **Settings/Active Sessions** + **Audit Log** | 383-session table; 844-event audit trail | `settings-administration.png`, `12-security/audit-log.png` |
| 4 | 3:30–4:30 | Admin: **Reports & Analytics**; explain scope discipline (slide 12) | Analytics; tie to manager "Access denied" beat coming later | `11-reports/reports-analytics.png` |
| 5 | 4:30–5:30 | Admin: **Refund Management**; honest sandbox framing (script §13): test data, fail-closed 503 on online path | Refund console; 4 test refund records | `10-refunds/refunds-console.png` |
| 6 | 5:30–6:00 | Admin: **Notifications inbox** + **Broadcast console** | Inbox; broadcast tool (do NOT send) | `09-notifications/notifications-inbox.png`, `broadcast-console.png` |
| 7 | 6:00–7:00 | **Staff** login → dashboard + Order Queue; narrate PENDING→PREPARING→READY→COMPLETED; show staff RBAC redirect | Scoped queue; redirect on admin URL | `05-staff/*.png`, `12-security/rbac-staff-on-admin-users-route.png` |
| 8 | 7:00–8:00 | **Manager** login → dashboard + cafeterias; then admin reports URL → "Access denied" | Manager scope enforced | `06-manager/*.png`, `rbac-manager-on-admin-reports-route.png` |
| 9 | 8:00–9:30 | **Student mobile**: login → home/switcher → menu browse (honest "not published yet" if applicable) → orders → notifications → favorites → profile | Full student journey | `03-student/*.png` |
| 10 | 9:30–10:30 | Student web-console visit → `/mobile-required` redirect (mobile-first design beat) | "Use the Mobile App" screen | `03-student/student-web-mobile-required.png` |
| 11 | 10:30–12:00 | **Faculty mobile**: login → home (Faculty Cafeteria) → switcher showing **both** cafeterias → orders → notifications | Dual-cafeteria access; F-61-06 residue visible in picker — use Category-A one-liner if noted | `04-faculty/*.png` |
| 12 | 12:00–12:45 | **Security proof:** private-window unauth redirect + API 401 JSON; cite 13/13 RBAC 403 probe suite | Redirect to login; `AUTHENTICATION_ERROR` 401 | `12-security/unauthenticated-*.png` |
| 13 | 12:45–14:00 | **E2E lifecycle narration** with order #31: PENDING→PREPARING→READY→COMPLETED, 7-event trail, 2 notifications — point at audit log + notification inbox screens as corroboration | Story of a proven full lifecycle | `audit-log.png`, `mobile-notifications.png` |
| 14 | 14:00–14:45 | **Known-limitations honesty beat** (script § limits section): test residue, no live payments, sparse dietary metadata — frame as documented + owned | Trust-building close | — (verbal; `FINAL_KNOWN_LIMITATIONS.md` available on request) |
| 15 | 14:45–15:00 | Close on metrics: 872/5 backend, 40/40 web, 34/34 mobile, 13/13 RBAC, role rehearsals 8/8·7/7·5/5·4/4·3/3 | — | `13-final/api-health.png` |

**What NOT to click in 15-min version:** broadcast **Send**, refund **Approve/Reject** buttons, menu **Publish** (unless pre-arranged as a planned beat), "Sign Out All Devices", any admin **Delete** control, `.env` files, terminals with secrets.

---

## Pre-demo checklist (run 15 minutes before doors open)

See `DEMO_SAFETY_CHECKLIST.md` for the full list. Minimum viable:

1. Docker Desktop running; `uniserve_api` + `uniserve_postgres` containers **healthy**.
2. API health returns `"status":"ready"`.
3. `http://localhost:3000` loads (pre-compile by visiting dashboard + login).
4. `http://localhost:8081` loads (pre-compile; reload once if cafeteria list is empty).
5. Browser has **only** the three demo tabs open (console, mobile, health) — no personal tabs, no `.env`, no terminal secrets visible.
6. Logged out of all accounts; know which account each beat uses.
7. `presentation/` folder open in a file browser as screenshot fallback.

## Post-demo

- Leave the running environment as-is (containers up, servers running). **Do not** run `docker compose down -v`.
- Do not commit anything. The working tree must contain only the presentation artifacts created for this demo.
