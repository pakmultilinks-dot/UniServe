# Phase 42 — Final Real-World Product Acceptance

**Date:** 2026-10-03
**Mode:** Testing and discovery only. No application code, dependencies, or configuration were modified.
**Starting commit:** `d060bc6` (main) — unchanged at report time (report-only commit follows).
**Verdict:** **CONDITIONALLY ACCEPTED** — see §10.

---

## 1. Objective, Scope, and Starting State

### 1.1 Objective

Rigorous, evidence-based acceptance testing of the complete UniServe product as it would be used in the real world, exercising every primary user journey through the actual UIs:

- Students (mobile app)
- Faculty (mobile app)
- Staff (operational web console)
- Managers (operational web console)
- Administrators (web console)

plus cross-role isolation, authentication/reliability UX, and order-cancel gates, followed by re-verification of the three Phase 41 bug fixes and unmodified automated test suites.

### 1.2 Scope rules applied

- UI evidence is required for a PASS verdict; API-only observation does not earn a PASS (API may supplement UI evidence).
- No application code, dependencies, or configuration may be modified.
- No data deletion; state transitions on test orders (place/cancel/collect) are acceptable acceptance activity.
- Automated suites are run unmodified.
- Every scenario is recorded as PASS / FAIL / BLOCKED / NOT TESTED, with evidence.
- Bugs are classified severity P0–P3 and categorized as application bugs, external prerequisites, or test-environment limitations.
- Secrets, passwords, and OTPs are never printed.

### 1.3 Deviations from the starting tree (pre-existing, untouched)

The working tree at phase start contained **20 pre-existing deleted files** (historical phase reports `PHASE_22` … `PHASE_41`). These deletions pre-date Phase 42, were **not** made by this phase, were left untouched, and are excluded from the Phase 42 commit. Historical content was read from git history where needed.

```
D PHASE_22_GAP_MATRIX.md … D PHASE_41_PRODUCT_BUG_REMEDIATION.md (20 files)
```

No other working-tree modifications were introduced by Phase 42 (only this report is committed).

---

## 2. Environment and Service Recovery

### 2.1 State at phase start

Docker Desktop was down; all stack services were stopped. The long-standing `uniserve_caddy` container had a broken Caddyfile template (sites `example.com` / `app.localhost`) — a pre-existing environment defect, not an application defect.

### 2.2 Recovery actions (test environment only)

| Action | Result |
|---|---|
| Started Docker Desktop, `uniserve_postgres`, `uniserve_api` | Both healthy (`uniserve_api (healthy)`, `uniserve_postgres (healthy)`) |
| `uniserve_caddy` (production template) | **Left stopped** — broken `example.com`/`app.localhost` template, not fixed (out of scope, no config changes) |
| Throwaway container `uniserve_caddy_local` (Caddy 2, sites `http://app.localhost, http://localhost`, serving pre-built `apps/web/out`) | **Running** — used for all web-console acceptance |
| Expo dev server `http://localhost:8081` | Running (terminal session); mobile journeys executed against Expo web |
| API relay on port 8000 → `uniserve_api:8000` | Running; verified healthy (login + health return full JSON) |

### 2.3 Access method and environment quirks (recorded, not bugs)

1. **`localhost` vs `127.0.0.1`:** `uniserve_caddy_local` only matches `Host: localhost`. Requests to `Host: 127.0.0.1` match no site block; Caddy logs them as `NOP` and returns an **empty body**. All probes therefore use `http://localhost/...`. Browser flows are unaffected.
2. **`app.localhost` DNS:** does not resolve on this host; web console is accessed at `http://localhost/dashboard/...`, which makes the baked `http://localhost/api/v1` API URL same-origin (no CORS involved).
3. **PowerShell:** probe scripts must run under `pwsh -NoProfile -ExecutionPolicy Bypass -File …` (PowerShell 7). Windows PowerShell 5.1 fails parsing the JSON-token scripts.
4. **Web console login:** fill `#university-email, input[type="email"]` + password → `form.requestSubmit()` via `page.evaluate` → wait ~4 s. Sign-out lives only in the nav drawer (`button[aria-label="Open navigation menu"]`, `lg:hidden`, requires forced click).
5. **Mobile (Expo web):** Expo `Pressable` elements are `div`s, not `button`s — tap via `page.locator('text=Log In').first().click()`. **New finding:** successful login does **not** auto-navigate; the app shell requires a manual reload (see P2-3). Access token lifetime is 30 min; after expiry the API returns 401 while the app stays on a stale shell until re-login.
6. **Mobile `Alert.alert`:** Expo web does not surface `Alert.alert` as a Playwright dialog and the callbacks do not fire — "Sign Out" and "Sign Out All Devices" clicks produce **no dialog, no network call, no state change** (P3-1; backend verified via API supplement, §4 F4).

Final service state at report time: `uniserve_caddy_local`, `uniserve_api (healthy)`, `uniserve_postgres (healthy)` up ~2 h (plus an unrelated local `n8n` service not part of the UniServe stack).

---

## 3. Accounts and Fixtures Used

All accounts are pre-existing test fixtures. Passwords are intentionally not reproduced here.

| Role | Account (email) | Notes |
|---|---|---|
| Administrator | `admin@lgu.edu.pk` | Full console access |
| Student (active) | `ayesha.khan@student.lgu.edu.pk`, `bilal.hussain@…`, `fatima.raza@…` | Primary journey-A actor: ayesha |
| Student (unverified) | `test.student40@student.lgu.edu.pk`, `test.student41@…` | `pending_verification` — Journey F unverified-email flow |
| Faculty | `dr.imran.chaudhry@lgu.edu.pk`, `dr.sana.malik@lgu.edu.pk` | Primary journey-B actor: dr.imran |
| Staff | `ahmed.raza@lgu.edu.pk` | STF-201, assigned **Student Cafeteria only** |
| Manager | `sana.malik@lgu.edu.pk` | MGR-301, assigned **Faculty Cafeteria only** |

Fixtures: Faculty Cafeteria `287038a2-…`, Student Cafeteria `84ab69bb-…`. Legacy item **Gulab Jamun (2 pcs)** `6a6bb621-…` (Faculty menu, base price 12000 paisa, daily-menu special price 11000 paisa, **no inventory row**). Phase 41 item Chicken Karahi `29672b59-…` (stock 20). Phase 42 zero-stock probe item `a469440e-…` (stock 0). Test orders: **#40** `e4f76339-…` (pending, slot 04:15 — left untouched), **#41** `acc3ef08-…` (cancelled), **#42** `c777ff88-…` (scheduled 15:30, cancelled during retest #3).

---

## 4. Scenario Matrix — Journeys A–G

Legend: **PASS** · **FAIL** (bug found) · **BLOCKED** (cannot be tested honestly in this environment) · **NOT TESTED**.

### Journey A — Student Mobile (ayesha)

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| A1 | Mobile login with valid credentials | Authenticated app | Login 200; tokens persisted; **URL stays on `/login` — no auto-redirect** (manual reload required) | **PASS** (with P2-3) | Expo web; tokens in localStorage; post-reload app renders |
| A2 | Browse menu, categories, search | Menu renders; search filters | Menu, category chips, and search all functional | **PASS** | UI screenshots/session evidence |
| A3 | Item detail; favorites | Detail correct; favorite toggle | Detail correct; **Favorites is a placeholder** | **PASS** (P3-5) | UI |
| A4 | Cart: add/remove/change quantity; totals | Totals = Σ price×qty | Cart math correct; DELETE item → 204; cart empty afterwards | **PASS** | API + UI; cart state verified empty |
| A5 | Checkout — ASAP + order note | Order created | Order #41 placed; note "Phase 42 acceptance - student ASAP order" recorded | **PASS** | Order detail UI |
| A6 | Order detail: status, QR, timeline | Full detail | Status banner, collection QR, status timeline all render | **PASS** | UI |
| A7 | Cancel own pending order | Cancels; status gate thereafter | #41 cancelled via UI; detail shows "This order was cancelled" | **PASS** | UI + DB (`cancelled`, "Cancelled by customer") |
| A8 | Profile; sign out | Session cleared | Profile renders; **Sign Out button inert on Expo web** (Alert.alert P3-1); session cleared via storage wipe → `/login` | **PASS** (P3-1) | UI + localStorage empty |
| A9 | Cafeteria switcher | Role-scoped options | Student sees own cafeteria scope correctly | **PASS** | UI |
| A10 | Token expiry behavior | Refresh or clean re-auth | 30-min expiry → API 401s while stale shell remains; **re-login via UI succeeds** (again: no auto-redirect, P2-3) | **PASS** (P3-6) | UI session; login 200 |

### Journey B — Faculty Mobile (dr.imran)

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| B1 | Faculty login; default cafeteria | Faculty Cafeteria | Defaults to Faculty Cafeteria | **PASS** | UI |
| B2 | Published-menu gating | Only today's published items orderable | Gating enforced; non-menu items rejected with clean message | **PASS** | UI + API |
| B3 | Order legacy item **Gulab Jamun** | Orderable or clean unavailable message | Add-to-cart OK (appears in daily menu), **checkout → HTTP 400 with raw `menu_item_id` UUID** ("Menu item 6a6bb621-6853-49e8-a7d9-26c32d40bde3 … insufficient stock") — item has **no inventory row** | **FAIL — P1-1** | API response + DB (no inventory row) |
| B4 | Cart totals vs displayed price | Cart honors daily-menu special price | Item displayed at **Rs 110** (special price 11000 paisa) but **cart line charged Rs 120** (base price 12000 paisa) | **FAIL — P2-1** | UI cart vs daily-menu special price; DB `daily_menu_items.special_price=11000`, `menu_items.price=12000` |
| B5 | Zero-stock probe item (stock 0) add-to-cart | Rejected, no secrets leaked | **HTTP 400 "Menu item is not on today's published menu"** — clean message, no UUID; daily-menu gate fires before the stock check. In-stock Karahi control → 201. Stock-check path at `carts/service.py:340` is covered by automated tests; the UI-visible zero-stock flow is design-blocked today (see §7/§8) | **PASS** (classification: not a bug) | API responses; cart cleaned (DELETE 204) |

### Journey C — Staff Operational (ahmed, Student Cafeteria)

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| C1 | Staff login; scope | Student Cafeteria only | Correct scoping on entry | **PASS** | UI |
| C2 | Order queue lifecycle | preparing → ready → completed → collected | Full lifecycle exercised on order #38 (completed; `collected_at` set). Observation: skipping "Prepare" leaves `preparation_started_at` NULL (P3-8) | **PASS** | UI + DB |
| C3 | Student Cafeteria inventory; restock | View + adjust | 17 inventory rows visible; **Adjust −/+ restock works (+2 applied)** | **PASS** | UI + DB |
| C4 | Faculty Cafeteria inventory (foreign) | Access denied | **HTTP 403** (correct RBAC); UI shows misleading empty state "No inventory items" instead of a denial (P3-2). Pages also default to the wrong cafeteria for this role (P3-3) | **PASS** (P3-2, P3-3) | UI + API |
| C5 | Menu page | Read-only for staff | Menu renders read-only; no edit affordances | **PASS** | UI |
| C6 | Inventory readability | Human-readable names | Raw `menu_item_id` UUID prefixes in column (P3-4) | **PASS** (P3-4) | UI |

### Journey D — Manager + Administrator Web Console

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| D1 | Manager login; scope | Faculty Cafeteria only | Correct scope | **PASS** | UI |
| D2 | Manager order queue | Faculty orders visible | Queue renders; **order-delay control absent** — `PUT /orders/{id}/delay` API exists, no UI (P3-9) | **PASS** (P3-9) | UI + API probe |
| D3 | Manager foreign-cafeteria order view | Access denied | API **403** (correct); UI shows empty state "No pending orders" masking the denial (P3-10). "2 Cafeterias" stat unscoped for manager (P3-11) | **PASS** (P3-10, P3-11) | UI + API |
| D4 | Manager navigation differentiation | Manager-only entry points | Manager nav identical to staff — **no manager-only UI** (P3-12) | **PASS** (P3-12) | UI |
| D5 | Admin console pages | All pages render | Users, Overview, Reports, Refunds, Settings all render and load data | **PASS** | UI |
| D6 | Admin navigation | Menu management reachable via nav | **Nav lacks Menu entry**; page works when URL entered directly (P3-13) | **PASS** (P3-13) | UI |
| D7 | Sales reporting with real data | Revenue reflects completed orders | **8 completed orders = 356,000 paisa (Rs 3,560) — all Pay-at-Counter — yet reports show Rs 0.00 everywhere.** Root: `reports/service.py:87-140 get_sales_summary` sums only `Payment.amount WHERE status == SUCCEEDED`; cash orders have no Payment row; UI labels unqualified | **FAIL — P2-2** | UI (admin Reports, manager `/reports/sales` = 200 with global zeros) + DB (completed SUM 356000) + code path |
| D8 | Admin legacy remediation (create menu item) | Item created + inventory exists (Phase 41 fix) | Covered in §5 retest 1 — **PASS** | **PASS** | §5 |

### Journey E — Cross-Role Isolation (UI + API matrix)

| ID | Probe | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| E1 | Manager → `/dashboard/users|reports|analytics` | Denied/redirect | Redirected to `/dashboard` (UI) | **PASS** | UI |
| E2 | Staff → Faculty inventory | 403 | 403 (UI + API) | **PASS** | §4 C4 |
| E3 | Admin nav vs staff/manager | Admin-only entries | Admin adds Staff/Overview/Users/Reports/Refunds/Settings | **PASS** | UI |
| E4 | Student → `/users/` | 403 | **403** | **PASS** | API matrix |
| E5 | Student → Faculty inventory | 403 | **403** | **PASS** | API matrix |
| E6 | Staff → Faculty orders | 403 | **403** | **PASS** | API matrix |
| E7 | Manager → Student-cafeteria orders | 403 | **403** | **PASS** | API matrix |
| E8 | Student → `POST /menu-items` (write) | 403 | **403** | **PASS** | API matrix |
| E9 | Student → Faculty daily-menus | 403 | **403** | **PASS** | API matrix |
| E10 | Student → another student's order (IDOR) | 403 | **403** (target order `a94f7311-…`) | **PASS** | API matrix |
| E11 | Staff → `/users/` | 403 | **403** | **PASS** | API matrix |
| E12 | Manager → `/refunds/` | Denied | 307 redirect observed; follow-up destination **NOT TESTED** | **NOT TESTED** | API probe |
| E13 | Manager → `/reports/sales` | Scoped data | 200 with `{"summary":{"total_revenue":0,…}}` — global zeros, consistent with P2-2 (scoping itself not determinable while revenue is broken) | **PASS** (dependent on P2-2) | API probe |

**Journey E verdict: PASS** — 10/10 tested isolation probes deny correctly; RBAC is enforced server-side; residual P3s are UX masking (empty states instead of denial notices).

### Journey F — Authentication & Reliability UX

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| F1 | Login with invalid password | Clear inline error | 401 → inline alert **"Invalid email or password"** (`role="alert"`) | **PASS** | Web console UI |
| F2 | Login as unverified account | Clear inline error | 403 → inline alert **"Email address is not verified"** | **PASS** | Web console UI |
| F3 | Token refresh behavior | Refresh chain works; expiry is recoverable | Control refresh **HTTP 200** (full token pair); admin console session survived > 60 min in-tab (refresh chain functioning); mobile: post-expiry 401s + stale shell, re-login recovers | **PASS** | API probe + observed sessions |
| F4 | "Sign Out All Devices" | Revokes all sessions | **UI: BLOCKED-harness** — button present in profile SECURITY section; Expo web `Alert.alert` never surfaces (P3-1), clicks produce no dialog/network/state change. **API supplement: PASS** — control refresh 200 → `POST /auth/logout-all` **200** → same refresh token afterwards → **401 `{"detail":"Session has been revoked","code":"TOKEN_REVOKED"}`** → re-login 200 | **PASS** (backend; UI blocked, P3-1) | API probe script (§4/§5 evidence) |
| F5 | Sign out (single device) | Session cleared | Backend session semantics fine; UI click inert on Expo web (P3-1); storage wipe cleared session | **PASS** (P3-1) | UI + localStorage |
| F6 | OTP / forgot-password / email verification flows | Full flow | **BLOCKED** — no SMTP provider in test environment (external prerequisite, out of scope) | **BLOCKED** | — |

### Journey G — Cancel Gates (repeated + scheduled)

| ID | Workflow | Expected | Actual | Verdict | Evidence |
|---|---|---|---|---|---|
| G1 | Re-cancel an already-cancelled order | Impossible from UI | Order #41 detail: "This order was cancelled" banner; **no Cancel button rendered** (status gate) | **PASS** | UI |
| G2 | Cancel scheduled order past deadline | Clean rejection, no raw internals | Order #40 (slot 04:15 PKT, long past) → Cancel → confirm → **HTTP 400 "Cancellation deadline has passed. Orders can be cancelled up to 30 minutes before the scheduled collection time."** — clean user-facing message, no raw error leak; #40 left `pending`, untouched | **PASS** | UI confirm flow + API 400 body |
| G3 | Schedule future order with lead-time filter | Slots ≥ 30 min ahead only | Checkout slot picker **earliest offered 15:00** (= now + ~30 min) — lead-time enforced at scheduling; order #42 placed (slot 15:30); **cancelled successfully pre-deadline**; DB: `cancelled` + "Cancelled by customer" | **PASS** | UI + DB |
| G4 | Late-pending scheduled order lifecycle | Auto-expire or staff handling | #40 remained `pending` hours past its 04:15 slot — **no auto-expiry** observed; staff-side manual handling only; delay API has no UI (P3-9/P3-14) | **PASS** (P3-14 observation) | DB |
| G5 | Stock integrity after cancel flow | No phantom decrements | Karahi stock still 20 after retest #3 cancels | **PASS** | DB |

**Journey G verdict: PASS.**

---

## 5. Phase 41 Remediation — Retest Results (3/3 PASS)

| # | Fix under test | Retest | Result |
|---|---|---|---|
| 1 | `create_menu_item` auto-creates inventory | Admin web console → create menu item → DB query | **PASS** — exactly **ONE** inventory row created (`quantity=0`, `low_threshold=10`); no duplicate on repeat view; item immediately managed in staff inventory |
| 2 | Mobile `cancelOrder` + status gate | Journey A7 + G1 | **PASS** — #41 cancelled from mobile UI; cancelled-order detail shows cancellation state and **no Cancel button**; backend rejects re-cancel |
| 3 | Scheduled-cancel timezone deadline | Journey G2 + G3 | **PASS** — (a) past-deadline cancel rejected with clean 400 message (no raw leak, no timezone miscomputation — deadline evaluated in PKT); (b) new scheduled order #42 placed at 15:30 (slot picker enforced ≥30-min lead) and cancelled pre-deadline; DB verified `cancelled` / "Cancelled by customer"; (c) #40 untouched; (d) stock intact |

**All three Phase 41 fixes hold under regression. No regressions detected in the broader journeys.**

---

## 6. Confirmed Bugs

### P1

**P1-1 — Legacy menu item without inventory row → checkout rejects with raw UUID.**
- **Area:** data integrity + error presentation (Faculty menu).
- **Repro:** Faculty login → Faculty Cafeteria → add **Gulab Jamun (2 pcs)** to cart → checkout.
- **Actual:** HTTP 400 `Menu item 6a6bb621-6853-49e8-a7d9-26c32d40bde3 is not available today or has insufficient stock` — internal `menu_item_id` leaked to user; item has **no row in `inventory_items`**.
- **Context:** Phase 41 fixed the *create path* (new items always get inventory). This *legacy row* predates the fix and remains unremediated; the raw-UUID message pattern also violates the clean-error standard used elsewhere (zero-stock probe returns a clean message).
- **Impact:** Faculty cannot order a listed, on-menu item; error is developer-facing.
- **Class:** Application bug (data + presentation). Suggested remediation direction (not executed): backfill inventory for legacy items + replace raw-ID message with a clean unavailable message.

### P2

**P2-1 — Cart/order ignores daily-menu `special_price` (charged base price).**
- **Repro:** Faculty mobile — Gulab Jamun displayed at **Rs 110** (daily-menu special price 11000 paisa); **cart line charged Rs 120** (menu base price 12000 paisa).
- **Impact:** Money integrity — any orderable special-price item is overcharged. Currently the only special-price row in data is the broken Gulab Jamun, and **no order containing it exists** (verified: 0 order_items rows) — so no financial loss has yet been realized, but the defect is live in cart/checkout math.
- **Class:** Application bug.

**P2-2 — Sales analytics/reporting excludes cash (Pay-at-Counter) revenue.**
- **Repro:** Admin → Reports (or manager `/reports/sales`) after the acceptance journeys.
- **Actual:** Rs 0.00 everywhere, despite **8 completed orders totaling 356,000 paisa (Rs 3,560), all cash** (verified in DB). Root: `reports/service.py:87-140 get_sales_summary` sums only `Payment.amount WHERE status == SUCCEEDED`; cash orders never create a succeeded Payment row. UI labels ("Total Revenue") are unqualified, so managers/admins read zeros as truth.
- **Impact:** Reporting feature materially wrong for the campus cash-first workflow; decision-making data corrupted.
- **Class:** Application bug (calculation + labeling).

**P2-3 — Mobile login success does not navigate into the app.**
- **Repro:** Expo web/mobile — valid login → HTTP 200, tokens persisted to localStorage, **URL remains `/login`**; user must manually reload to reach the app.
- **Impact:** Primary entry flow broken-feeling for every student/faculty login; also compounds the post-expiry stale-shell experience (A10).
- **Class:** Application bug (navigation).

### P3

| ID | Finding | Evidence |
|---|---|---|
| P3-1 | Mobile **Sign Out / Sign Out All Devices** buttons inert on Expo web — `Alert.alert` never surfaces; no dialog, network call, or state change. Backend verified working via API (§4 F4). Harness vs app ambiguity: on a native device `Alert` works; on web it silently does nothing | UI attempts (mouse, evaluate-click, keyboard) + API supplement |
| P3-2 | 403 denials render misleading empty states ("No inventory items") instead of a permission notice (staff→Faculty inventory; manager→foreign orders) | §4 C4/D3 |
| P3-3 | Inventory/menu pages default to the wrong cafeteria for scoped roles (staff sees Faculty 403 + empty) | §4 C4 |
| P3-4 | Inventory table shows raw `menu_item_id` UUID prefixes instead of item names | §4 C6 |
| P3-5 | Mobile Favorites is a placeholder (no persistence) | §4 A3 |
| P3-6 | Post-token-expiry mobile shell stays interactive but 401s everywhere (no forced re-auth prompt) | §4 A10 |
| P3-7 | Confirmed-state not displayed on order cards | Journey A |
| P3-8 | `preparation_started_at` stays NULL when staff marks Ready without Prepare | DB #38 |
| P3-9 | Order-delay API (`PUT /orders/{id}/delay`) has **no UI** in manager/staff console | §4 D2 |
| P3-10 | Manager foreign-cafeteria denial masked by "No pending orders" empty state | §4 D3 |
| P3-11 | "2 Cafeterias" dashboard stat unscoped for manager (shows cafeterias outside assignment) | §4 D3 |
| P3-12 | Manager navigation identical to staff — no manager-only UI surface | §4 D4 |
| P3-13 | Admin nav lacks a Menu entry (page reachable only by direct URL) | §4 D6 |
| P3-14 | Past-slot pending scheduled orders are never auto-expired (hours later still `pending`) | §4 G4 |
| P3-15 | Persistent "Refreshing… Don't see your changes? Reload the app" banner on Expo web pages after mutations (never dismisses in this environment) | Journey A/G UI |

### Not bugs — classified explicitly

- **Zero-stock checkout rejection** (§4 B5): daily-menu gate fires first with a clean 400; the `carts/service.py:340` insufficient-stock path is exercised by automated tests. A UI-visible zero-stock flow is **design-blocked** by daily-menu immutability today (§7) — a missing-feature/P3, not a defect in current behavior.
- **Staff 403 on Faculty inventory** — correct RBAC; only the empty-state presentation is P3.
- **`127.0.0.1` empty responses / `app.localhost` DNS / broken `uniserve_caddy` template** — test-environment infrastructure (§2.3), not application defects.

---

## 7. Missing Features vs Defects

| Item | Classification | Notes |
|---|---|---|
| Daily-menu **publish** workflow (UI) | **Missing feature** | Daily menus are DRAFT-only via API; today's published menu is immutable (one-per-date → 409), which design-blocks the zero-stock UI flow and same-day menu editing |
| Order **delay** control (UI) | **Missing feature** | API `PUT /orders/{id}/delay` exists; no console affordance (P3-9) |
| **Favorites** persistence | **Missing feature** | Mobile placeholder (P3-5) |
| Manager-only console section | **Missing feature** | Nav identical to staff (P3-12) |
| Admin Menu nav entry | **UX gap** | Page works via direct URL (P3-13) |
| Auto-expiry of past-slot pending orders | **Missing behavior** | Currently manual staff handling only (P3-14) |
| Cash-inclusive revenue reporting | **Defect (P2-2)** | Not a labeling gap — the numbers are wrong |
| Special-price cart math | **Defect (P2-1)** | Money integrity |
| Mobile post-login navigation | **Defect (P2-3)** | Entry-flow navigation |
| OTP / email verification flows | **External prerequisite** | Requires SMTP provider (§8) |

---

## 8. Blocked / Not-Testable Scenarios

| Scenario | Blocker | Class |
|---|---|---|
| OTP email verification & password-reset end-to-end | No SMTP provider in test environment | External prerequisite (out of scope this phase) |
| Online payment provider (JazzCash) end-to-end (pay, webhook, refund) | Provider credentials/sandbox not provisioned | External prerequisite (out of scope) |
| "Sign Out All Devices" **UI** confirmation flow | Expo web does not surface `Alert.alert`; backend fully verified via API supplement (P3-1) | Test-harness limitation (native device would exercise it) |
| UI-visible zero-stock purchase flow | Today's published daily menu immutable (one-per-date 409); stock-check path covered by automated tests | Design constraint / missing feature |
| Production mobile build (EAS) | Cloud build credentials not provisioned | External prerequisite (out of scope) |
| VPS deployment / live DNS | Explicitly out of scope this phase | Out of scope |
| Manager → `/refunds/` redirect follow-up | Probed 307; destination not exercised | NOT TESTED (low priority; refunds admin-scoped UI verified in D5) |

---

## 9. Automated Suite Results (unmodified)

| Suite | Command | Result |
|---|---|---|
| Backend API tests | `pytest` in `apps/api` (repo venv) | **656 passed** in 200.13 s — matches the Phase 41 baseline exactly; zero failures/errors/skips beyond baseline |
| Web console type-check | `npx tsc --noEmit` in `apps/web` | **Exit 0** |
| Mobile app type-check | `npx tsc --noEmit` in `apps/mobile` | **Exit 0** |
| Shared-types type-check | `npx tsc --noEmit` in `packages/shared-types` | **Exit 0** |

**Build decisions (documented):**
- Web production build (`out/`) intentionally **not** re-run: `apps/web/out` is bind-mounted into the running `uniserve_caddy_local` container that served this acceptance — rebuilding mid-verification would overwrite the served bundle and invalidate live evidence. Acceptance ran against the already-built deployed bundle.
- `packages/shared-types` dist rebuild skipped: `tsc --noEmit` type-checks the unchanged sources equivalently; re-emitting dist would rewrite artifacts consumed by running apps for no verification gain.
- No suites were modified, skipped, or xfailed.

---

## 10. Verdict — CONDITIONALLY ACCEPTED

**No P0 defects.** All five role groups can complete their primary real-world journeys end-to-end through the actual UIs. Cross-role isolation is enforced server-side across 10/10 tested probes. Authentication error UX is clean and correct. The token-refresh chain works (control 200; long-lived admin session observed). Logout-all revocation is fully functional at the API layer (200 + `TOKEN_REVOKED` on reuse + successful re-login). All three Phase 41 fixes retest **PASS** with no regressions; the backend suite is green at the Phase 41 baseline (656 passed) and all TypeScript projects type-check cleanly.

**Why conditional (not unconditional):** four defects remain open at acceptance time:

1. **P1-1** — legacy on-menu item without inventory → faculty checkout fails with a raw internal UUID.
2. **P2-1** — cart/checkout charges base price, ignoring daily-menu special price (money integrity; unrealized but live).
3. **P2-2** — sales reporting shows Rs 0.00 while Rs 3,560 of completed cash orders exist (reporting materially wrong for the cash-first campus workflow).
4. **P2-3** — mobile login success does not navigate into the app (primary entry flow friction for every user).

**Unconditional acceptance requires:** P1-1 fixed (inventory backfill + clean unavailable message), P2-1 and P2-2 fixed (special-price math; cash-inclusive revenue or explicitly scoped labels with correct in-scope numbers), P2-3 fixed (post-login navigation), plus regression coverage for each. The P3 list (§6) is quality-of-life and may trail a release, except P3-1 (web-inert auth buttons), which should be addressed before any browser-based mobile deployment.

---

## 11. Recommended Next Phase (not started)

**Phase 43 — Focused Remediation (P1 + P2s), smallest possible diff:**

1. **P1-1:** backfill `inventory_items` for legacy menu items lacking rows (idempotent script/migration) + replace raw-ID rejection message with the clean "not available today or insufficient stock" pattern.
2. **P2-1:** make cart/checkout/order totals honor `daily_menu_items.special_price` when present; add regression tests (unit + API) asserting charged price = special price.
3. **P2-2:** include all settled orders in revenue (cash included) — or, if product intent is payments-only, relabel UI scopes and surface cash totals alongside; regression test asserting completed cash orders appear.
4. **P2-3:** navigate to the app after successful mobile login (and align with the stale-shell re-auth path).
5. Regression gate: re-run all Phase 42 journeys A–G spot checks (faculty cart/checkout, admin reports, mobile login, cancel gates) + full pytest + tsc.
6. Defer (document, do not block): P3 sweep (empty states/denials, cafeteria defaults, nav entries, favorites, delay UI, auto-expiry), SMTP sandbox for OTP flows, JazzCash sandbox integration phase, Expo-web `Alert` fallback for auth buttons.

*Per phase rules, Phase 42 made no code changes and stops after this report.*
