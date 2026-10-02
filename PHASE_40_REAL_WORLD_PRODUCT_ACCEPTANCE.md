# Phase 40 — Real-World Product Acceptance Report

**Date:** 2026-10-02 · **HEAD:** `6318b05` (main, tree clean) · **Method:** End-to-end UI testing through the real Web console and the real Mobile (Expo) application. API calls were used only as documented preconditions (test-data setup) or as back-end cross-checks of UI-observed behavior.

---

## A. Environment

| Component | Detail |
|---|---|
| API | `uniserve_api` (production mode, Docker) |
| Database | PostgreSQL 16 — `uniserve_prod` (`docker exec uniserve_postgres psql -U uniserve -d uniserve_prod`) |
| Reverse proxy | Caddy 2 — `app.localhost` (ports 80/443) |
| API relay (local dev) | Node relay :8000 → :80 (CORS + 307 Location rewrite) — required because Expo web cannot call the Caddy origin directly |
| Web console | Next.js 14 static export at `http://app.localhost` |
| Mobile app | React Native Expo SDK 51 (expo-router) at `http://localhost:8081` (web build) |
| Test accounts | Admin `admin@lgu.edu.pk`/`Admin123!`; Students `ayesha.khan@`, `bilal.hussain@`, `fatima.raza@student.lgu.edu.pk`/`TestPass123!`; Faculty `dr.imran.chaudhry@`, `dr.sana.malik@lgu.edu.pk`/`TestPass123!`; Staff `ahmed.raza@lgu.edu.pk` (Student Cafeteria); Manager `sana.malik@lgu.edu.pk` (Faculty Cafeteria) |
| Cafeteria IDs | Faculty `287038a2-…`; Student `84ab69bb-…` |

**Limitations (environment, not product):**
- Expo web server is unstable in this environment — it exited 3× during the session and required restart; the API relay died once (took the register test down with it — retest after restart succeeded).
- Playwright interactions required DOM-evaluate click workarounds because polling-driven re-renders break Playwright's actionability/stability checks.
- SMTP is not configured locally → OTP emails cannot be delivered (see §E).
- Pull-to-refresh gesture not exercised (web build; touch simulation not available) — order detail auto-polling (~30 s) was observed instead and covers refresh persistence.

---

## B. Integration Matrix — Admin/Manager Action → Mobile Propagation

| # | Action (Web console / admin/manager UI) | Mobile result | Status |
|---|---|---|---|
| 1 | Login → Order Queue ("University-wide order overview") | — | ✓ |
| 2 | Create menu item (MenuItemModal: name/desc/category/price/prep-time) | Item visible on mobile menu | ✓ *see P1* |
| 3 | Edit menu item price 520 → 480 | Mobile shows updated PKR 480 | ✓ |
| 4 | Daily menu draft → publish | Published items appear in mobile daily menu | ✓ |
| 5 | Toggle item unavailable | Item un-addable on mobile | ✓ |
| 6 | Inventory adjust via web Inventory UI | Stock enforcement reflected at mobile add-to-cart | ✓ |
| 7 | — (checkout order placed) | Inventory decrements (burger 10→9, zinger 25→24) | ✓ |
| 8 | — (student mobile UI) Order placement | Orders #34 (PKR 800, Pay at Counter), #35 (scheduled 13:00), #36 created; visible in staff queue | ✓ |
| 9 | Staff lifecycle: Confirm → Prepare → Ready → Collect (with confirm dialog) | Mobile timeline advanced at every step (Pending→Preparing→Ready→Completed) | ✓ |
| 10 | Collect completed | Order #34 = `completed` in DB + mobile | ✓ |
| 11 | — (faculty mobile login) | Faculty Cafeteria only (Administration Block, 1st Floor); menu 100% disjoint from student menu; cafeteria switcher present | ✓ |
| 12 | Admin queue shows scheduled order | "Scheduled: 1:00 PM" chip on #35 | ✓ |
| 13 | Manager: Confirm → Prepare → Delay +30 min | Mobile: "Estimated 38 minutes" (eta 8→38) | ✓ |
| 14 | Admin attempts Delay | 403 — role separation correct (manager/staff only) | ✓ |
| 15 | Order cancelled (API; no mobile cancel UI — P2) | Mobile shows cancelled banner + Orders tab cancelled chip | ✓ |
| 16 | — (formatting) | PKR amounts correct on web + mobile | ✓ |
| 17 | — (role separation) Mobile login as staff `ahmed.raza@` / admin `admin@lgu.edu.pk` | RoleGate auto-logout: tokens cleared, all API calls 401, no unauthorized data served | ✓ *see P3-UX* |
| 18 | — (registration) Mobile register → verify-email screen | 6-digit OTP inputs + "Resend in 60s" countdown render; wrong OTP → "Invalid OTP. Please try again." (400); unverified login → "Email address is not verified" (403) | ✓ *(completion NOT TESTABLE — SMTP)* |
| 19 | — (token lifecycle) | Live traffic: access-token 401 → automatic refresh → 200 | ✓ |
| 20 | — (session persistence) | Admin web session stayed authenticated across the entire multi-hour session | ✓ |
| 21 | — (edge cases) Mobile search "zzzznotexist" | "No items found — No items match …" empty state | ✓ |
| 22 | — (edge cases) Mobile category filter Desserts | Gulab Jamun (2 pcs) PKR 100 shown | ✓ |
| 23 | Admin orders → `cancelled` filter | #36 (Naan, PKR 30) and other cancelled orders listed with `cancelled` chip | ✓ |

---

## C. Bugs Found

| ID | Sev | Summary | Evidence / Root cause |
|---|---|---|---|
| P1 | **P1** | **New menu items created via admin UI are un-orderable.** MenuItemModal has no stock/inventory field and the create flow creates no inventory record → item displays on mobile but add-to-cart fails with "No inventory record for item {id}". Inventory page offers no create affordance either. | `apps/web/src/app/dashboard/menu/page.tsx` MenuItemModal (lines 373–486); reproduced via UI, worked around with a direct `inventory_items` DB insert to continue testing. Blocks the full "admin creates item → student buys it" journey. |
| P2 | **P2** | **Mobile app has no customer cancel-order UI.** API `POST /orders/{id}/cancel` works (immediate order #36 cancelled via API → cancelled banner displayed on mobile correctly), but the mobile order-detail screen exposes no cancel action — customers cannot self-serve cancellation. | `apps/mobile/app/(app)/order/[id].tsx` — no cancel button; only the cancelled *display* state exists. |
| P2 | **P2** | **Scheduled-order cancellation deadline timezone bug.** Server compares the user-entered PKT scheduled time against a naive UTC `now()` → same-day PKT slots (e.g. 13:00) are judged past the 30-minute deadline → "Cancellation deadline has passed" for cancellations that should be allowed. | Reproduced on scheduled order #35; immediate-order cancel (no scheduled time) succeeded with 200. |
| P3 | P3 | Web inventory table shows `menu_item_id` prefix (e.g. "dd37eb8e") instead of the item name. | Inventory page rendering. |
| P3 | P3 | Mobile item detail shows "Available now" even when inventory stock = 0; the block only surfaces later as a cart error. | Item detail screen does not surface stock state. |
| P3 | P3 | Web orders page Delay button renders only for `ready` status — managers cannot delay pending/preparing orders via UI (API supports preparing→ready delays). | `apps/web/src/app/dashboard/orders/page.tsx` (~line 285: `status === "ready" && isManager`). |
| P3 | P3 | Post-login navigation delay on web console (~4 s before authenticated shell renders). | Observed on every web login. |
| P3 | P3-UX | **RoleGate logout UX is rough but secure:** staff/admin mobile login → tokens cleared and all subsequent API calls 401 (no unauthorized data), but the UI first renders an error shell ("Failed to load cafeterias") before settling on the landing page instead of redirecting cleanly to login. | Observed for both `ahmed.raza@lgu.edu.pk` (staff) and `admin@lgu.edu.pk` (admin) logins. |
| — | Env | Expo web server instability (3×), relay death (1×), Playwright click workarounds required. Environment/infrastructure — not product defects. | §A limitations. |

---

## D. Final Status — **Conditionally Accepted**

**Verified through real UIs (acceptance criteria met):**
- Menu lifecycle: admin create/edit/publish/availability → mobile display and enforcement (price edits, daily menu publish, availability toggle).
- Inventory: web adjust → mobile enforcement; stock decrements on order.
- Ordering: mobile cart → checkout → staff queue, including scheduled-slot picker and Pay at Counter.
- Staff lifecycle: Confirm → Prepare → Ready → Collect with live mobile timeline propagation at every step.
- Role separation: faculty cafeteria isolation on mobile; manager-only delay; admin 403 on delay; staff/admin mobile logins auto-logged-out by RoleGate with zero unauthorized data access.
- Cancellation display + manager delay → mobile ETA propagation ("Estimated 38 minutes").
- Registration + OTP gate UI (6-digit code screen, invalid-code error, unverified-login block); live token-refresh cycle; session persistence; search/filter empty states; PKR formatting.

**Blocking or deferring full acceptance:**
1. **P1** — admin-created menu items are un-orderable without a manual DB fix (no inventory record created, no UI to create one).
2. **P2** — no mobile customer cancel-order flow (API works, UI missing).
3. **P2** — scheduled-order cancellation deadline timezone bug rejects valid same-day cancellations.
4. **OTP completion NOT TESTED** — the verify-email UI and API contract (register → 201 "verify your email", resend 200, invalid-code 400, unverified login 403 `EMAIL_NOT_VERIFIED`) were all exercised, but completing verification with a *valid* code requires an actual OTP email — impossible without SMTP (§E).

**Decision:** Core admin/manager → mobile propagation is real and works end-to-end for menu, ordering, lifecycle, isolation, scheduling display, and delay. Fix P1 (auto-create inventory record on menu-item creation + stock field in MenuItemModal) and the two P2s before calling the product fully accepted; OTP completion re-verification once SMTP is provisioned.

---

## E. External Prerequisites (unchanged from Phase 40 provisioning)

| Prerequisite | Blocks | Status |
|---|---|---|
| SMTP / email delivery | OTP verification completion (email_verification + password_reset flows); registration cannot complete end-to-end | Not configured locally — API contract verified, delivery not testable |
| JazzCash merchant account | Online payment method (orders tested with Pay at Counter) | External |
| VPS + DNS + TLS (`app.localhost` → public domain) | Production deployment | Provisioned per Phase 40 (`VPS_PROVISIONING_REPORT.md`) — out of scope here |
| EAS build credentials | Native mobile binaries (acceptance ran on Expo web build) | External |

**Test artifacts left in DB:** unverified accounts `test.student40@student.lgu.edu.pk`, `test.student41@student.lgu.edu.pk`; test orders #34 (completed), #35 (preparing/delayed), #36 (cancelled); test menu item "Acceptance Test Burger" with inventory record. Clean via `scripts/cleanup_test_data.py` before production cutover.
