# PHASE 35 — Final Product-Gap Inventory

**Date:** 2026-10-02
**Type:** Analysis/audit only. Zero code changes.
**Commit message:** `docs: add final product gap inventory`

---

## 1. Baseline

| Item | Value |
|---|---|
| HEAD | `5d381d4` (`docs: finalize UniServe production deployment runbook`) |
| Working tree | Clean (verified before audit) |
| Production deployment | Has NOT happened (no VPS/domain/DNS/credentials — `DEPLOYMENT_BLOCKERS.md`) |
| Backend tests | **622 collected** (`pytest --collect-only`, this phase) — last full run **622 passed** at `70ae399` (docs-only commits since) |
| Method | Code + test inspection (backend agents, mobile agent, web agent, ops/tests agent) + repo-wide greps. Documentation claims were re-verified against code, never trusted alone. |

**Primary question answered:** if the VPS and domain existed tomorrow, the application work below is what remains before UniServe could reasonably be considered launch-ready.

---

## 2. Requirements Matrix (94 requirements classified)

Classification key: `IMPLEMENTED` · `PARTIALLY IMPLEMENTED` · `DEFERRED` · `BLOCKED EXTERNALLY` · `NOT IMPLEMENTED` · `UNCLEAR`. Every non-IMPLEMENTED row has a 5-part detail in §2.6.

### 2.1 Users and authentication (11)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 1 | Student access | IMPLEMENTED | Email pattern classification (`core/university.py`), mobile student flow, `MOBILE_ROLES` |
| 2 | Faculty access | IMPLEMENTED | Faculty email patterns; faculty on mobile; both cafeterias |
| 3 | Staff access | IMPLEMENTED | `WEB_DASHBOARD_ROLES` incl. `cafeteria_staff`; web `/dashboard/orders` |
| 4 | Admin access | IMPLEMENTED | `university_admin` → web admin pages + `/administration/overview` |
| 5 | University email authentication | **PARTIALLY IMPLEMENTED** | Real classification + password auth + OTP verification flow; **production email delivery is a stub** (`core/email.py` `ProductionEmailProvider.send_otp` returns `False`, logs "OTP not delivered") → self-registration/password reset cannot complete in production. Detail §2.6-A1 |
| 6 | Student/employee ID | IMPLEMENTED | `university_id` (3–50 chars) collected for all users at registration/admin-creation; no separate employee-ID field |
| 7 | Email immutability after setup | IMPLEMENTED | No mutation endpoint exists (set once at registration/admin creation); normalization `.lower().strip()` at auth layer |
| 8 | Editable profile fields | **NOT IMPLEMENTED** | No backend profile-update endpoint (searched `profile\|update_profile` — docstring only); web profile save is a stub toast; mobile profile read-only. Detail §2.6-A2 |
| 9 | Session handling | IMPLEMENTED | JWT HS256 access 30 min / refresh 30 d; `sid`-bound; rotation + reuse detection; per-request session-active check; revoke-on-suspend; logout/logout-all; sessions list |
| 10 | Account status | IMPLEMENTED | `pending_verification → active → suspended → deleted`; per-request enforcement; login/PIN lockout (423) |
| 11 | RBAC | IMPLEMENTED | `RequireRole`, `RequireCafeteriaWriteScope`, `RequireCafeteriaScope`, `verify_resource_cafeteria`; 71 authorization/scope tests |

### 2.2 Cafeterias (6)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 12 | Student Cafeteria | IMPLEMENTED | Model + tests + dev seed script (`apps/api/scripts/seed_student_cafeteria.py`); **no auto-seed at startup** — operator creates both cafeterias at first deployment (runbook Steps 12–13) |
| 13 | Faculty Cafeteria | IMPLEMENTED | Same as #12 |
| 14 | Cafeteria independence | IMPLEMENTED | Separate menu-items/daily-menus/inventory/carts/orders per cafeteria; per-cafeteria operational status + capacity + closing time |
| 15 | Student isolation | IMPLEMENTED | Students forced to STUDENT type on `GET /cafeterias`; `RequireCafeteriaScope` blocks faculty cafeteria; favorites/search filter faculty items; tests |
| 16 | Faculty access to both | IMPLEMENTED | Server-side category filtering; `test_faculty_can_access_student_cafeteria` |
| 17 | Staff cafeteria scope | IMPLEMENTED | Assignment-based write scope; multi-assignment requires explicit `cafeteria_id`; cross-cafeteria denied; 25 scope-enforcement tests |

### 2.3 Menu (10)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 18 | Daily menu | IMPLEMENTED | `DailyMenu` draft/published/archived, unique `(cafeteria, menu_date)`, `/today`, publish flow |
| 19 | Menu creation | IMPLEMENTED | POST menu-items (write scope) + web `/dashboard/menu` create modal |
| 20 | Menu editing | IMPLEMENTED | PUT endpoint + web edit modal; admin-only soft delete |
| 21 | Availability | IMPLEMENTED | `is_available` / `is_active` toggles (web); `is_available_today` per daily menu; published menus immutable |
| 22 | Inventory/portions | IMPLEMENTED | `InventoryItem` quantity/threshold/`last_restocked_at`; checks at cart-add and checkout reserve |
| 23 | Out-of-stock behavior | IMPLEMENTED | HTTP 400 exact messages at cart add (`carts/service.py`) and checkout reserve (`orders/service.py`); mobile unavailable warning |
| 24 | Stock refresh | IMPLEMENTED | `POST /inventory/adjust` (positive = restock) is the refresh mechanism; low-stock endpoints; web adjust modal |
| 25 | Images | **PARTIALLY IMPLEMENTED** | `image_url` nullable string only; **no file-upload endpoint** (no multipart anywhere); static `app/static/food/` mounted; `scripts/generate_food_images.py` exists. Detail §2.6-B1 |
| 26 | Pricing | IMPLEMENTED | Price in paisa, PKR currency, per-daily-menu `special_price`, server-authoritative totals |
| 27 | Cafeteria isolation | IMPLEMENTED | All menu/inventory queries scoped; `verify_resource_cafeteria`; cross-cafeteria tests |

### 2.4 Ordering (12)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 28 | Cart | IMPLEMENTED | Server-side cart: one ACTIVE cart per user per cafeteria; GET/POST/PUT/DELETE + checkout; mobile `CartContext` server-backed |
| 29 | Immediate orders | IMPLEMENTED | `order_type immediate`; cash reserves inventory + confirms at collection; online → `PAYMENT_PENDING` gate |
| 30 | Scheduled orders | IMPLEMENTED (same-day) | `scheduled_collection_time` must be future today + before cafeteria closing; reserve at preparation start |
| 31 | Scheduling in hours | **PARTIALLY IMPLEMENTED** | Same-day 30-min slot picker client-side (mobile `getCollectionSlots`); server validates same-day+closing only; **no multi-day scheduling**. Detail §2.6-B2 |
| 32 | Order number generation | IMPLEMENTED | Atomic global sequence (raw SQL `UPDATE order_number_sequence`), unique constraint; pickup by order number or QR `collection_token` |
| 33 | Order history | IMPLEMENTED | `GET /orders` own, `days` 1–90 (default 7); mobile history + pull-to-refresh |
| 34 | Cancellation rules | **PARTIALLY IMPLEMENTED** | Backend: owner cancel = PENDING only, `CANCELLATION_DEADLINE_MINUTES = 30`; manager cancel PENDING/PREPARING; manager reject (reason) — **but no client exposes user cancellation** (mobile has no cancel UI at all; web is admin/staff-only and students are redirected to mobile). Detail §2.6-A3 |
| 35 | No-show rules | **PARTIALLY IMPLEMENTED** | Thresholds (student 3/30 d → +7 d suspension; faculty 5/30 d → +3 d), `NoShow` records, UNCOLLECTED notification, 60 s pickup-expiry worker — **but `check_suspension()` is never called at checkout**: ordering-suspended users can still order; `mark_uncollected` docstring says READY→COMPLETED but code leaves status READY. Detail §2.6-A4 |
| 36 | Delay/ETA behavior | IMPLEMENTED | ETA formula (queue depth, prep time, capacity), `GET /orders/{id}/eta`, staff `mark_delayed` (+1–120 min) extends deadline + emits DELAYED notification; mobile ETA banner |
| 37 | Order lifecycle | IMPLEMENTED | 5 statuses, 19 event types, guarded transitions; online prep requires payment `SUCCEEDED` (6 prep-gate tests) |
| 38 | Pickup/completion | **PARTIALLY IMPLEMENTED** | Backend `POST /orders/collect` (order number or QR, assignment-gated) + mobile QR screen — **but no client wires a staff "collect" action**: `collectOrder` exists only in `apps/web/src/lib/api.ts:292`, never called by any page (verified this phase). Detail §2.6-A5 |
| 39 | Notifications (ordering) | **PARTIALLY IMPLEMENTED** | Backend emits in-app notifications for 11 order + 3 refund events (idempotent, fire-and-forget); web notifications page — **mobile has no inbox UI** (service functions exist, never imported). Detail §2.6-B3 |

### 2.5 Payments (9)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 40 | Cash at counter | IMPLEMENTED | `payment_method cash`; confirmed at collection; works in production (tested) |
| 41 | Online-payment architecture | IMPLEMENTED (provider-less) | Provider ABC + registry (`{"test": TestPaymentProvider}`); initiate → redirect/webhook-driven confirmation; idempotency keys; unknown provider → 503 |
| 42 | Server-authoritative amount | IMPLEMENTED | Total computed from `price_snapshot × qty` at checkout; webhook success validates amount/currency against the order; refunds bounded by refundable balance |
| 43 | Payment verification | **PARTIALLY IMPLEMENTED** | Webhook-driven confirmation is the designed path; `provider.verify_payment()` defined but never called; user polling via `GET /payments/{id}` + `/payments/order/{order_id}`; moot in production (initiation blocked) |
| 44 | Webhook security | **PARTIALLY IMPLEMENTED** | Replay protection + tamper tests + amount validation exist; signature verification delegated to provider; TestPaymentProvider signature = always valid; **`POST /payments/webhook/{provider}` has no production guard** (unlike initiation's 503 block); practical exposure today ≈ nil (no pending online payments can exist while initiation is blocked). Detail §2.6-B4 |
| 45 | Refund boundary | **PARTIALLY IMPLEMENTED** | Request flow + `REFUND_DEADLINE_HOURS` + refundable-balance caps + admin/manager process endpoint (32 tests) — **but refunds router hardcodes `TestRefundProcessor`** (no env selection) → real-money refunds non-functional (fail closed: only `test_pay_*` refs succeed) |
| 46 | Payment failure behavior | IMPLEMENTED | Failed payment → payment `FAILED`, order unchanged; prep blocked until `SUCCEEDED`; mobile surfaces errors without claiming success |
| 47 | Production fail-closed behavior | IMPLEMENTED | Initiation guard `APP_ENV=production + TestPaymentProvider → 503` (exact message), tested + live-verified Phase 33; unknown provider → 503 |
| 48 | JazzCash status | **BLOCKED EXTERNALLY** | No JazzCash code (`providers/` = `base.py`, `test_provider.py`, `__init__.py`); no fake credentials; official technical contract never received (Phases 24–28C gate) — conclusion re-verified at HEAD this phase |

### 2.6 Detailed findings (every non-IMPLEMENTED row — 5-part)

**A1. Production email delivery missing (OTP) — #5** — **Launch-blocking: YES for self-serve onboarding in production**
1. *Current behavior:* registration creates `PENDING_VERIFICATION`; OTP is generated + hashed and `ProductionEmailProvider.send_otp` logs "OTP not delivered" and returns `False`; login raises `EmailNotVerifiedError` for `PENDING_VERIFICATION`; password reset uses the same OTP path. In dev, `DevelopmentEmailProvider` logs the OTP to the API console.
2. *Files:* `apps/api/app/core/email.py` (stub, line ~67), `apps/api/app/modules/auth/service.py` (`register`, `_create_and_send_otp`, `verify_otp`, reset flow), `apps/api/app/core/config.py` (no SMTP fields — `SMTP_*` are commented placeholders, `extra="ignore"`).
3. *Launch-blocking:* Yes — **if** launch includes self-registration/password reset. Not blocking for an admin-provisioned rollout (admin `POST /users` creates ACTIVE + email-verified accounts with temp passwords — implemented and tested).
4. *Why:* no new student/faculty user can complete onboarding in production; every account would have to be manually provisioned.
5. *To complete:* add real `Settings` SMTP/email fields + a real provider implementation in `core/email.py` (provider-agnostic: SMTP/SES/SendGrid), plus tests; the provider **account** itself is an external prerequisite (§4).

**A2. Editable profile fields missing — #8** — **Launch-blocking: No** (admin can manage accounts; users read their data)
1. *Current behavior:* profile screens (web + mobile) are read-only; web save shows a stub toast "Profile editing will be available in a future update"; change-password UI exists nowhere (web) / was removed as a no-op (mobile), though backend `POST /auth/password/change` and PIN endpoints exist.
2. *Files:* backend — no endpoint (searched `profile|update_profile` across `apps/api/app`); web `apps/web/src/app/dashboard/profile/page.tsx` (`saveProfile` stub, ~L41–55); mobile `apps/mobile/app/(app)/(tabs)/profile.tsx`.
3. *Launch-blocking:* No.
4. *Why:* nice-to-have for launch; name/phone edits are not operationally critical and email must stay immutable.
5. *To complete:* backend `PATCH /users/me` (limited editable fields, e.g., name/phone — never email/role/status) + web/mobile wiring; change-password UI wiring to the existing endpoint.

**A3. User-facing cancellation missing — #34** — **Launch-blocking: No** (manager reject/cancel exists as the operational backstop)
1. *Current behavior:* backend cancel rules are complete and tested (owner: PENDING only, 30-min deadline; manager: PENDING/PREPARING; reject manager-only with reason). Mobile has **no cancel button, no cancel call, no rule display** anywhere (searched `cancel|Cancel` across `apps/mobile/**`). Web order queue is staff/manager-facing; students are redirected to `/mobile-required`.
2. *Files:* `apps/api/app/modules/orders/router.py` (`POST /orders/{id}/cancel` L146, manager-cancel, reject), `apps/api/app/modules/orders/service.py` (`CANCELLATION_DEADLINE_MINUTES = 30`); mobile — not found.
3. *Launch-blocking:* No.
4. *Why:* users can still get orders cancelled by telling staff; the requirement "cancellation rules" is enforced server-side but not user-reachable.
5. *To complete:* mobile order-detail cancel action (PENDING only, surface the 30-min deadline + server errors).

**A4. No-show suspension not enforced at checkout — #35** — **Launch-blocking: No for safe operation; Yes for the no-show policy to have any effect**
1. *Current behavior:* pickup-expiry worker (60 s interval) records `NoShow`, emits UNCOLLECTED notification, and the threshold policy sets suspension (`ordering_suspended` until date) — **but `check_suspension()` is never called by cart/checkout**; a suspended-for-no-shows user keeps ordering. Admin reports count `ordering_suspended`. Separately, `mark_uncollected` leaves order status READY (docstring claims READY→COMPLETED — factual discrepancy).
2. *Files:* `apps/api/app/modules/orders/noshow.py` (`check_suspension`, thresholds), `orders/service.py` (`mark_uncollected` L899–941), `main.py` lifespan worker; checkout path has no call site (searched).
3. *Launch-blocking:* No (ordering itself is safe; enforcement gap weakens policy only).
4. *Why:* the no-show policy is currently cosmetic — students can no-show repeatedly with no consequence.
5. *To complete:* call `check_suspension()` in checkout (reject with clear error); decide whether uncollected orders should transition status (and fix the docstring accordingly); add tests.

**A5. Staff pickup completion UI missing — #38** — **Launch-blocking: YES** (physical pickup workflow cannot be completed from the console)
1. *Current behavior:* backend `POST /orders/collect` (by order number or QR `collection_token`, assignment-gated, sets `COMPLETED` + `collected_at`) is implemented and tested; mobile generates the student-side QR. **No client wires the staff action**: `collectOrder` exists only in `apps/web/src/lib/api.ts:292` and is never called by any page (verified by grep this phase). Web orders page has confirm/prepare/ready/reject/delay only.
2. *Files:* `apps/api/app/modules/orders/router.py` (`/collect`), `apps/web/src/lib/api.ts:292` (unused), `apps/web/src/app/dashboard/orders/page.tsx` (no collect button).
3. *Launch-blocking:* **Yes** — without it, orders never reach `completed` via the console; staff would have to call the API manually.
4. *Why:* completion is the terminal step of the core staff workflow.
5. *To complete:* wire a Collect action on the web orders page (scan/type order number or collection token), role-gated to assigned staff/manager/admin.

**B1. Images via URL only — #25** — Launch-blocking: No
1. *Behavior:* `image_url` string field; no upload endpoint (no multipart in `apps/api/app`); static food images served from `app/static/food/`.
2. *Files:* `modules/menus/` models/schemas; `main.py` static mount.
3. *Why it's fine for launch:* operators can host images and set URLs; daily-menu `image_url` works.
4. *To complete (later):* authenticated upload endpoint or a documented image pipeline.

**B2. Multi-day scheduling absent — #31** — Launch-blocking: No (scope decision)
1. *Behavior:* scheduled orders are same-day only (future time today, before closing); mobile generates 30-min slots from operating hours with a client-side `now+30 min` minimum; no server min/max lead-time constants beyond same-day+closing.
2. *Files:* `orders/service.py` `_validate_scheduled_order_time`; mobile `checkout.tsx` `getCollectionSlots()`.
3. *To complete (later):* date+time picker + server-side lead-time constants + day-boundary rules.

**B3. Mobile notification inbox missing — #39** — Launch-blocking: No (web inbox exists; order detail polling covers live status)
1. *Behavior:* backend notification endpoints fully implemented (list/unread-count/read/read-all); mobile `getNotifications`/`getUnreadNotificationCount` exist in `src/services/data.ts` but are **never imported by any screen**; no bell UI, no mark-read.
2. *Files:* `apps/mobile/src/services/data.ts` L206–219 (unused); no notification screen under `apps/mobile/app/**`.
3. *To complete:* notification tab/screen + unread badge wired to existing endpoints.

**B4. Webhook endpoint lacks a production guard — #44** — Launch-blocking: No today; **required before any online payments are enabled**
1. *Behavior:* `POST /payments/webhook/{provider_name}` is unauthenticated by design (signature-verified by the provider); `TestPaymentProvider.verify_webhook_signature` always returns valid; `PAYMENT_PROVIDER` defaults to `"test"` and production validators do not reject it (they reject default secrets/debug/dev-DB-password only). Replay protection and amount/currency validation exist. Practical exposure today ≈ nil because initiation is blocked in production → no pending online payments exist to confirm.
2. *Files:* `apps/api/app/modules/payments/router.py` (webhook route; initiation guard ~L89–95), `providers/test_provider.py`, `core/config.py` validators, `tests/test_payment_provider_config.py`.
3. *To complete:* mirror the initiation guard on the webhook path (reject TestPaymentProvider webhooks when `APP_ENV=production`) and/or reject `PAYMENT_PROVIDER=test` in production validators; tests.

### 2.7 Admin operations (7)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 49 | User management | IMPLEMENTED | Web `/dashboard/admin/users`: list/filter/suspend+reason/activate/role-change; backend `recover` endpoint (API-only, no web UI button) |
| 50 | Staff management | IMPLEMENTED | Web `/dashboard/staff` + role change + assignment rules; backend manager restrictions |
| 51 | Reports | **PARTIALLY IMPLEMENTED** | Backend: 12 report endpoints (sales/daily/by-cafeteria/orders summary/volume/cancellation-rate/performance/popular-items/peak-hours/stock-levels/low-stock/turnover) with date ranges — **web UI uses only `GET /reports/sales` + 3 date presets** (7d/30d/month); no custom range, no export, no charts; `getDailySalesReport` + `getOrderSummaryReport` defined in `api.ts` but unused. Detail §2.6-B5 |
| 52 | Refund handling | **PARTIALLY IMPLEMENTED** | Admin refunds page: **approve-only** — no deny action, no approver-reason input (backend has admin list + process endpoints; rejected filter exists but nothing in UI can reject); real-money refunds externally blocked (see #45). Detail §2.6-B6 |
| 53 | Cafeteria management | IMPLEMENTED | Web `/dashboard/cafeterias`: status toggle (manager+admin), edit name/location/description (admin); backend CRUD admin-only |
| 54 | Operational workload | IMPLEMENTED | `GET /administration/overview` (admin) + web overview stat cards (users/orders/revenue/cafeterias) + refund link; no per-staff workload breakdown (not required) |
| 55 | Audit/security visibility | **PARTIALLY IMPLEMENTED** | `SecurityAuditEvent` rows written (18+ event types incl. `AUTHORIZATION_FAILED`, `RATE_LIMITED`) but **no read endpoint and no admin UI** — events invisible to operators. Detail §2.6-B7 |

**B5. Reports UI minimal — #51** — Launch-blocking: No (API data exists; managers can read sales)
1. *Behavior:* rich backend reporting; web reports page = sales totals only, preset ranges.
2. *Files:* `apps/api/app/modules/reports/router.py`; `apps/web/src/app/dashboard/admin/reports/page.tsx`; `apps/web/src/lib/api.ts` L457–505.
3. *To complete:* wire orders-summary/daily/by-cafeteria endpoints, custom date range, CSV export.

**B6. Refund deny path missing in UI — #52** — Launch-blocking: No
1. *Behavior:* approve-only UI; no deny endpoint exposure in `api.ts` (only `processRefund`); no approver reason. Backend `rejected` status exists in data model/filters.
2. *Files:* `apps/web/src/app/dashboard/admin/refunds/page.tsx` (L141–150); `apps/web/src/lib/api.ts` L509–526.
3. *To complete:* deny/reject action + reason capture (backend decision endpoint may need adding), approver note on approve; real refund processor remains external.

**B7. Audit events unreadable — #55** — Launch-blocking: No
1. *Behavior:* write-only fire-and-forget audit persistence.
2. *Files:* `apps/api/app/core/audit.py`; no router reads `security_audit_events`.
3. *To complete:* admin-only audit read endpoint + optional web viewer page.

### 2.8 Staff operations (10)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 56 | Incoming orders | IMPLEMENTED | `GET /orders/cafeteria/{cid}` + web order queue with 30 s auto-refresh |
| 57 | Pending | IMPLEMENTED | Status tab + confirm action; manager reject |
| 58 | Preparing | IMPLEMENTED | Prepare transition; online orders require payment success first |
| 59 | Ready | IMPLEMENTED | Ready transition; manager-only delay action |
| 60 | Completion/pickup | **PARTIALLY IMPLEMENTED** | See A5 (#38) — backend + student QR complete; staff console lacks the collect action |
| 61 | Inventory adjustment | IMPLEMENTED | Web adjust modal (signed qty + reason); staff/manager/admin allowed |
| 62 | Menu management | **PARTIALLY IMPLEMENTED** | Menu-item CRUD + availability/active toggles on web (manager/staff read) — **but daily-menu creation/publishing has NO UI anywhere**: `getDailyMenus/createDailyMenu/addDailyMenuItem/publishDailyMenu` exist only in `apps/web/src/lib/api.ts` L334–370 and are called by no page (verified this phase). Students only see published daily menus → **operators currently must publish via API/scripts**. Detail §2.6-A6 |
| 63 | Staff management | IMPLEMENTED | See #50 |
| 64 | Staff cannot suspend Staff | IMPLEMENTED | Suspend endpoint gated admin/manager only (staff → 403); managers cannot suspend managers/admins; cross-cafeteria targets denied; tests |
| 65 | Cafeteria isolation | IMPLEMENTED | Scope dependencies + explicit assignment checks + IDOR guard |

**A6. Daily-menu publish/create UI missing — #62** — **Launch-blocking: YES**
1. *Current behavior:* students see only today's *published* daily menu (mobile home + web). Backend daily-menu flow (create draft → add items → publish) is implemented and tested. **No web page or mobile screen calls the daily-menu APIs** (grep verified: matches only in `apps/web/src/lib/api.ts`).
2. *Files:* `apps/api/app/modules/menus/` (daily-menu endpoints); `apps/web/src/lib/api.ts` L334–370 (unused); `apps/web/src/app/dashboard/menu/page.tsx` (menu-items only).
3. *Launch-blocking:* **Yes** — publishing the daily menu is a core daily operation; without UI it requires direct API calls every day.
4. *Why:* the primary student-facing content (what can be ordered today) has no operator workflow.
5. *To complete:* web menu page (or dedicated section): create today's draft, add items with `special_price`/`display_order`/`is_available_today`, publish — wiring the existing endpoints; tests unchanged.

### 2.9 Notifications (6)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 66 | In-app notifications | IMPLEMENTED | Backend rows + endpoints; web `/dashboard/notifications` (list, unread toggle, mark read, read-all) |
| 67 | Order notifications | IMPLEMENTED | 11 order-event templates (created/confirmed/rejected/prep-started/ready/cancelled/delayed/uncollected/cafeteria-closed/payment-confirmed + refund trio); idempotent emission (unique source-event index); 57 tests |
| 68 | Delay notifications | IMPLEMENTED | `mark_delayed` → DELAYED notification; tested |
| 69 | Native push | **NOT IMPLEMENTED** | No `expo-notifications` dependency, no push-token endpoint/storage, no Expo push code anywhere (repo-wide grep empty) |
| 70 | Notification persistence/read state | IMPLEMENTED (backend) | `is_read`/`read_at`, unread-count, read/read-all endpoints; web UI. Mobile read-state UI missing (B3) |
| 71 | Failure behavior | IMPLEMENTED | Fire-and-forget emission swallows exceptions + logs; `DeliveryStatus` model; ordering never blocked by notification failures |

### 2.10 Web (12)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 72 | Admin login | IMPLEMENTED | Unified `/login`; role-based redirect; admin lands on `/dashboard/admin/overview` |
| 73 | Staff login | IMPLEMENTED | Same unified login; staff admitted to `/dashboard` by RoleGuard |
| 74 | Dashboard | IMPLEMENTED | `/dashboard` landing: stat cards, recent orders, recent notifications |
| 75 | Menu | IMPLEMENTED (items) | `/dashboard/menu` CRUD + toggles; **daily-menu publishing missing — A6** |
| 76 | Orders | PARTIALLY IMPLEMENTED | Queue + transitions + reject/delay + 30 s refresh; **collect action missing — A5** |
| 77 | Inventory | IMPLEMENTED | List + low-stock filter + adjust modal |
| 78 | Reports | PARTIALLY IMPLEMENTED | See #51/B5 |
| 79 | User management | IMPLEMENTED | `/dashboard/admin/users` + `/dashboard/staff` |
| 80 | Refunds | PARTIALLY IMPLEMENTED | See #52/B6 |
| 81 | Profile | PARTIALLY IMPLEMENTED | View + stub edit + sign-out-all; no save / change password (see #8/A2) |
| 82 | Responsive behavior | IMPLEMENTED | Tailwind default breakpoints; `MobileSidebar` hamburger nav; `overflow-x-auto` tables; mobile-safe modals (`max-w-sm mx-4`) |
| 83 | Deep links | IMPLEMENTED | Caddy `try_files {path} {path}.html {path}/index.html /index.html`; all 21 routes exported with per-route HTML (verified Phase 34 + re-checked this phase) |

### 2.11 Mobile (11)

| # | Requirement | Class | Evidence |
|---|---|---|---|
| 84 | Student experience | IMPLEMENTED | Onboarding → login/register/verify → tabs (home/orders/favorites/profile) → cart → checkout → order detail + QR |
| 85 | Faculty experience | **PARTIALLY IMPLEMENTED** | Both cafeterias (server-filtered); identical student UI; **no guest ordering flow** (searched `guest|Guest` in mobile + backend auth — none; older evidence docs mentioning "guest ordering" are not backed by current code). Launch-blocking: No — faculty order with their own accounts |
| 86 | Cafeteria selection | IMPLEMENTED | Bottom-sheet selector; auto-select first; closed-cafeteria add-to-cart blocking + warning |
| 87 | Menu | IMPLEMENTED | Today's published menu only; category chips + search; item detail; **favorites heart is local state only** (backend favorites API + tests exist; mobile tab is a static placeholder) |
| 88 | Cart | IMPLEMENTED | Server cart via `CartContext`; qty stepper; unavailable-item warnings |
| 89 | Checkout | IMPLEMENTED | Immediate/scheduled toggle; cash default; online option **always visible** (not gated by provider config; 503 handled honestly — routed to order detail, never claims success); note field; idempotency key |
| 90 | Order detail | IMPLEMENTED | Status timeline, ETA banner, QR banner, **15 s focus-aware polling** (stops at completed/cancelled) |
| 91 | Order history | IMPLEMENTED | List + pull-to-refresh (backend default 7-day window) |
| 92 | Scheduled orders | IMPLEMENTED | 30-min slot picker from cafeteria operating hours; client-side limits only |
| 93 | Polling/realtime behavior | IMPLEMENTED (polling) | Order detail 15 s polling; **no WebSocket/SSE anywhere** — polling only (correctly characterized as polling, not push) |
| 94 | Role rejection for staff/admin | **PARTIALLY IMPLEMENTED** | `RoleGate` in `app/_layout.tsx` silently logs out non-student/faculty roles after login (blank redirect, no message); login screen itself does not reject; no per-route guards below root. Launch-blocking: No |

---

## 3. Application/product blockers (verified from the repository)

| ID | Blocker | Severity class | Evidence |
|---|---|---|---|
| P1 | **A5** Staff pickup "collect" action missing from web orders console — orders cannot be completed via UI | **A** — prevents basic operation | `api.ts:292` unused; grep verified |
| P2 | **A6** Daily-menu create/publish UI missing — core daily operation is API-only | **A** — prevents basic operation | `api.ts` L334–370 unused by any page; grep verified |
| P3 | **A1** Production OTP/email delivery is a stub — self-registration + password reset cannot complete in production | **A** for self-serve onboarding; not blocking for admin-provisioned rollout | `core/email.py` `ProductionEmailProvider` returns False; `config.py` has no SMTP fields |
| P4 | **A4** No-show ordering suspension not enforced at checkout | **B** — policy cosmetic until fixed | `check_suspension()` never called; grep verified |
| P5 | **A3** Mobile cancellation UI missing | **B** | no cancel code in `apps/mobile/**` |
| P6 | **B3** Mobile notification inbox missing (backend + web exist) | **B** | `data.ts` functions unused |
| P7 | **#8/A2** Profile editing unimplemented (backend endpoint absent) | **B** | no endpoint; web stub toast |
| P8 | **#51/B5** Reports UI sales-only; 10 backend report endpoints unused by UI | **B** | `reports/page.tsx` |
| P9 | **#52/B6** Refund deny + approver reason missing in UI | **B** | `refunds/page.tsx` approve-only |
| P10 | **#55/B7** Audit/security events unreadable (write-only) | **B** | no read endpoint |
| P11 | **B4** Payment webhook endpoint lacks production guard (test-provider signature is a no-op; default `PAYMENT_PROVIDER=test` passes prod validators) | **B** — required before enabling online payments; defense-in-depth for launch | `payments/router.py`, `test_provider.py` |
| P12 | `mark_uncollected` docstring/status discrepancy (orders stay READY) | small correction (report-only this phase) | `orders/service.py` L899–941 |
| P13 | No CI/CD — 622 backend tests exist but nothing gates commits automatically | **B** before public launch | no `.github/workflows` or any CI config (grep verified) |
| P14 | Zero web/mobile test suites (only 9 shared-types vitest cases); type-checks only | **B/D** | no jest/vitest/playwright configs in web/mobile |
| P15 | Rate limiting is per-account only (login 10/30 min, PIN 5/15 min, OTP resend 60 s ×3, password reset 5/hr); no IP/global limiter | **D** (acceptable at small scale) | no slowapi/limiter middleware (grep verified) |
| P16 | Mobile online-payment option always visible (not gated by provider config) — UX honesty gap | **D** | `checkout.tsx` |
| P17 | Favorites: backend API + tests exist; mobile tab placeholder + heart local-only; web `/dashboard/favorites` dead route | **D** | mobile `favorites.tsx` placeholder |
| P18 | Same-day scheduling only (no multi-day) | **D** (scope decision) | `_validate_scheduled_order_time` |
| P19 | Images URL-only, no upload endpoint | **D** | no multipart in `apps/api/app` |
| P20 | No guest ordering flow (older docs mention it; code has none) | **D** (scope decision) | grep `guest|Guest` empty in mobile + auth |

## 4. Infrastructure/external blockers (not application work)

| ID | Blocker | Source |
|---|---|---|
| E1 | VPS/server, SSH access | `DEPLOYMENT_BLOCKERS.md` B1/B2; `VPS_PROVISIONING_REPORT.md` (BLOCKED) |
| E2 | Production domains + DNS A records | B3 |
| E3 | Real domains in Caddyfile + server-side web build with real `NEXT_PUBLIC_API_URL` | B4/B5 |
| E4 | Mobile production URL + **Expo/EAS account** (plus missing `google-service-account.json`, empty Apple IDs in `eas.json`) | B6; `apps/mobile/eas.json` |
| E5 | Server-side `.env.production` provisioning + real `CORS_ORIGINS` | B7/B8 |
| E6 | Git hosting reachable from the server | B9 |
| E7 | **Payment provider contract** (JazzCash) + credentials — online payments/refunds remain fail-closed | B10; Phase 26/28C gate |
| E8 | **SMTP/email provider account** (for P3 integration) | `.env` templates (commented placeholders) |
| E9 | Monitoring/alerting service (none exists in code — metrics/alerting NOT FOUND) | audit §9 |
| E10 | Offsite backup storage destination | runbook notes (cron + local retention only) |

---

## 5. Payment status (§5 verification)

| Check | Result |
|---|---|
| Invented JazzCash API? | **No.** `providers/` contains only `base.py`, `test_provider.py`, `__init__.py`; JazzCash appears only in docs + one docstring example in `base.py` (grep verified at HEAD) |
| Fake credentials? | **No.** Payment vars are commented placeholders in env templates only |
| Undocumented endpoints? | **No.** initiate / webhook / verify-polling / refund endpoints match the documented architecture |
| Test provider silently succeeding in production? | **At initiation: NO** — hard 503 guard (`APP_ENV=production + TestPaymentProvider`), tested + live-verified Phase 33. **At the webhook path: guard ABSENT** (P11/B4) — practical exposure ≈ nil today because initiation is blocked so no pending online payments exist; amount/currency validation + replay protection still apply |
| Production online payment fails closed? | **Yes** — HTTP 503 `Online payments are unavailable: no production payment provider is configured` |
| Cash ordering functional in production? | **Yes** — confirmed at collection; `test_cash_payment_works_in_production` |
| Provider abstraction intact? | **Yes** — ABC + registry + unknown-provider → 503 (no silent fallback) |
| **JazzCash classification** | **BLOCKED EXTERNALLY** — conclusion re-verified at HEAD: no implementation, no contract response (Phases 26→28C), no credentials |

Refunds: architecture + admin/manager process boundary + 32 tests exist; processor hardcoded `TestRefundProcessor` → real-money refunds non-functional (fail closed at processor). Same external blocker as online payments.

## 6. Notification status (§6 verification)

| Channel | What actually exists |
|---|---|
| Backend-generated in-app notifications | **Yes** — 13 event types, templates for 11 order + 3 refund events, idempotent emission (unique source-event index), fire-and-forget with logged failures, `DeliveryStatus` model, user-scoped endpoints (list/unread-count/read/read-all); 57 tests |
| Mobile notification inbox | **No UI** — service functions exist (`src/services/data.ts` L206–219) but are never imported by any screen; no bell, no mark-read |
| Polling | Order detail screen only: 15 s focus-aware (`ORDER_POLL_INTERVAL_MS`); web staff orders queue: 30 s auto-refresh. **Polling — not push** |
| Native push | **Nothing.** No `expo-notifications` dependency, no push-token endpoint, no Expo push code anywhere (repo-wide grep empty) |
| Email notifications | **Not implemented** — the only email path is OTP (auth), and its production provider is a stub (§8) |

## 7. Mobile status (§7 verification)

| Item | Fact |
|---|---|
| Expo SDK / RN | `expo ~51.0.0` / `react-native 0.74.5`, expo-router `~3.5.0`, React 18.2 |
| State | React Context only (Auth/Cart/Theme); no react-query/redux |
| EAS config | `eas.json`: development/staging/production profiles; production `{channel: "production", autoIncrement: true}`; submit profile references **missing** `./google-service-account.json`; Apple IDs empty strings |
| Bundle IDs | iOS `com.uniserve.mobile`, Android `com.uniserve.mobile` |
| Production API URL | `src/config.ts`: `"https://api.uniserve.app/api/v1"` — placeholder domain; must become the real API domain (blocker E3/B5 interplay: set at EAS build time via channel → `extra.eas.channel` selection) |
| Channel selection | `Constants.expoConfig?.extra?.eas?.channel` → production/staging/development; `app.json` has no `extra` section (EAS injects at build) |
| Native projects | No `android/`/`ios/` dirs → no local prebuild; `apps/mobile/dist/` empty |
| `expo-updates` | **Not a dependency** — channels only affect build-time API URL selection, not OTA updates |
| Tests | None (no jest config, no test script) |
| Locally completable now | Real API URL in config, app.json permissions/notifications config, lint + type-check (`type-check` exit 0) |
| Requires Expo/EAS account | `eas build --profile production`, `eas submit` (also needs Play service-account key + filled Apple IDs), any EAS Update usage |

## 8. SMTP status (§8 verification)

| Question | Answer |
|---|---|
| SMTP implemented? | **No.** `apps/api/app/core/email.py` is a stub: `DevelopmentEmailProvider` logs OTPs to console; `ProductionEmailProvider.send_otp` logs "Production email provider not yet configured — OTP not delivered" and returns `False`. No `smtplib`/SendGrid/Resend/Mailgun imports anywhere |
| Settings fields? | **None.** `Settings` (`core/config.py`) has no SMTP fields; `SMTP_*` lines are commented placeholders in env templates; `extra="ignore"` means the API never reads them |
| Merely documented? | Yes — templates + honest status docs (`PHASE_28B`, `PHASE_31`, deployment checklist) |
| Features that depend on it? | **Yes:** OTP email verification (registration → `PENDING_VERIFICATION` → login blocked with `EmailNotVerifiedError`) and password reset (same OTP path). Admin-created accounts are ACTIVE + email-verified (no dependency) |
| Does lack of SMTP block core ordering? | **Not for already-verified users** (ordering/cash payments have no email dependency). **Yes for onboarding:** no new user can self-register or self-reset a password in production. All verification/seed scripts bypass via direct SQL (dev-only pattern — production rollout must not depend on that) |

## 9. Monitoring/operations status (§9)

| Item | Status | Detail |
|---|---|---|
| Health endpoint | **implemented** | `GET /api/v1/health` liveness — `{"status":"healthy",...}`, no dependencies |
| Readiness endpoint | **implemented** | `GET /api/v1/health/ready` — `SELECT 1` + `SELECT 1 FROM users LIMIT 1` schema probe; `ready`/`degraded` **status field** (always HTTP 200 by design) |
| Structured logging | **implemented** | structlog JSON to stdout (`LOG_FORMAT=json`, `LOG_LEVEL`); sqlalchemy/uvicorn noise tuned per env |
| Backup scripts | **implemented** | `scripts/backup_database.sh`: pg_dump custom → in-container `pg_restore --list` verification → host copy → 30-day retention |
| Restore scripts | **implemented** | `scripts/restore_database.sh`: `CONFIRM=yes` gate, container/file checks, verify-before-touch, `--clean --if-exists --no-owner --no-acl` |
| Failure recovery | **documented + partially automated** | compose healthchecks (prod: api httpx probe 30 s, postgres pg_isready); restart policy per runbook; payment/email integrations fail closed; migration rollback policy documented (restore-over-downgrade) |
| Backup cron | **documented, operator-installed** | `0 2 * * *` template in 4 docs — not automatic out of the box |
| Monitoring integration | **requires external service** | No metrics endpoint, no Prometheus client (grep verified); no dashboard |
| Alerting | **requires external service** | No webhook/Slack/email alert code anywhere (grep verified); runbook lists "configure email notifications for critical alerts" as future work |
| CI/CD | **not found** | No workflow files of any kind |

## 10. Current security status (launch-relevant, verified at HEAD)

| Area | Verified fact |
|---|---|
| Authentication | Password login (email + password), PIN login (`/pin/login`), OTP verification; university-email classification enforced at registration |
| Password/PIN/OTP handling | Argon2 (m=64 MiB, t=3, p=4) + bcrypt fallback; PIN PBKDF2-HMAC-SHA256 100k + `hmac.compare_digest`; OTP argon2-hashed, 10-min expiry, max 5 attempts, resend 60 s ×3 |
| Session security | HS256 JWT 30 min/30 d; `sid`-bound; refresh rotation + reuse detection (mismatch revokes session); per-request session-active + account-status checks; suspension revokes all sessions; password reset revokes all sessions |
| RBAC | `RequireRole` + cafeteria scope dependencies + `verify_resource_cafeteria` IDOR guard; audit event on authorization failure; 71 auth/scope tests + live role-matrix script |
| Cafeteria isolation | Enforced in dependencies and per-query; students hard-blocked from faculty cafeteria (favorites/search too) |
| Object-level access | Order/payment/refund/notification reads owner-scoped (or admin/assigned-staff); IDOR tests embedded across hardening/scope/security suites |
| Payment safety | Production initiation fail-closed (503); server-authoritative amounts; idempotency keys; webhook replay protection; **webhook endpoint lacks production guard (P11 — defense-in-depth gap, no practical exposure today)**; refunds admin/manager-only, balance-capped |
| Secret handling | Production config guards reject default/empty secrets + debug + dev DB password; `.env.production` gitignored; only `.example` templates tracked; prod image contains no `.env` (verified Phase 34); secrets never logged |
| Production debug behavior | `APP_DEBUG=false` enforced by validator; `/api/docs|redoc|openapi.json` → 404 in production (live-verified Phase 33) |
| CORS | Origin list from env (`CORS_ORIGINS`), operator-set (placeholder until real domain) |
| API docs exposure | Gated on `APP_DEBUG` (closed in production) |
| Rate limiting | Per-account only: login lockout 10/30 min, PIN lockout 5/15 min, OTP resend cooldown, password-reset 5/hr → 429s; **no IP/global middleware limiter** |
| Database safety | ORM throughout; raw SQL only for the atomic order-number sequence + readiness probe; migrations versioned (Alembic head `0009`); backup/restore verified live |
| Audit trail | `SecurityAuditEvent` write-only (18+ types) — collected but not operator-visible (P10) |

## 11. Testing status (§11)

| Suite | Count / status |
|---|---|
| Backend (`apps/api/tests`, 28 files) | **622 collected** (this phase); last full run **622 passed** at `70ae399` (docs-only commits since) |
| — payments | 71 (40 payments + 6 prep-gate + 10 provider-config + 15 security-payments) |
| — orders | 124 (53 orders + 31 operations + 33 pickup-expiry + 7 regression) |
| — auth/RBAC | 162 (incl. 46 hardening + 25 scope-enforcement) |
| — refunds | 32 (+ IDOR cases inside security/hardening files) |
| — notifications/expiry | 90 |
| — config guards / health / alembic metadata | 15 / 5 / 4 |
| E2E | Backend workflow coverage via suites; **13 manual live scripts** (localhost, hardcoded creds, direct-SQL OTP bypass — rehearsal evidence, not gates); `tests/integration/` = placeholder (README: "will be added in later phases") |
| Web | **No test setup** (scripts: dev/build/start/lint/type-check); type-check + static build verified |
| Mobile | **No test setup** (scripts: start/android/ios/web/lint/type-check) |
| shared-types | 9 vitest cases (ApiClient session restore/refresh behavior) |
| CI/CD | **None** — all verification manual |
| Backup/restore validation | Live-rehearsed (Phase 28A/33) — not automated tests |

## 12. Final gap table

| Area | Current status | Launch blocker? | Evidence | Required next action |
|---|---|---|---|---|
| Authentication | Complete sessions/RBAC; production OTP delivery stubbed | **Yes** (self-serve onboarding) | `core/email.py`, `config.py` | Real email provider integration (P3) |
| Ordering core | Cart→order→lifecycle→ETA→QR pickup complete | **Yes** (staff collect UI) | `api.ts:292` unused | Wire Collect action (P1) |
| Daily menu ops | Backend flow complete; **no publish UI** | **Yes** | `api.ts` L334–370 unused | Daily-menu console UI (P2) |
| Payments (cash) | Production-functional | No | tested | — |
| Payments (online/refunds) | Fail-closed; JazzCash externally blocked; webhook guard gap | No (cash launch OK) / **Yes before online** | providers dir; Phase 28C | Provider contract (E7) + webhook guard (P11) |
| Notifications | Backend + web complete; mobile inbox missing; no push | No | `data.ts` unused | Mobile inbox (P6); push = later (D) |
| Web console | Full ops surface; responsive; deep links OK; reports/refunds minimal | No | audit §2.10 | Reports + refund-deny UI (P8/P9) |
| Mobile app | Student/faculty flows complete; no cancel UI; silent staff rejection | No | audit §2.11 | Cancel UI (P5); rejection UX (D) |
| Admin/audit | User/staff/cafeteria mgmt + overview; audit unreadable | No | audit §2.7 | Audit read endpoint (P10) |
| Testing/CI | 622 backend tests; zero frontend tests; no CI | No for private deploy / **Yes before public** | audit §11 | CI pipeline (P13) |
| Monitoring/alerting | Health/readiness/logging/backup implemented; metrics+alerting absent | No | audit §9 | External monitoring (E9) |
| Infrastructure | Everything deployment-side externally blocked | **Yes** | `DEPLOYMENT_BLOCKERS.md` | E1–E6 (Phase 34 package) |

## 13. Recommended next work categories

**A — Must be completed before first real user (application code):**
1. **P1** Staff pickup Collect action on the web orders console (wire existing `collectOrder`).
2. **P2** Daily-menu create/add-items/publish UI (wire existing daily-menu endpoints).
3. **P3** Production email delivery integration (Settings fields + real provider in `core/email.py` + tests). External half: provider account (E8). Fallback for a cash-only, staff-provisioned pilot: documented admin-provisioning path (already implemented) — but self-registration/password reset stay broken until P3 lands.
4. **P11** (recommended inclusion — small, security-defect class) Webhook production guard mirroring the initiation guard + production validator for `PAYMENT_PROVIDER=test`.

**B — Required before public launch, not before internal deployment:**
P4 no-show checkout enforcement · P5 mobile cancel UI · P6 mobile notification inbox · P7 profile editing (+ change-password UI) · P8 reports UI completion · P9 refund deny + approver reason · P10 audit read endpoint · P13 CI pipeline (pytest + type-checks + web build as gating checks) · P14 baseline frontend tests (at least critical flows) · P12 `mark_uncollected` docstring/status decision.

**C — External prerequisite:** E1 VPS/SSH · E2 domains/DNS · E3 Caddyfile + server-side web build · E4 Expo/EAS + store accounts + Play key + Apple IDs · E5 server `.env.production` + real CORS · E6 git hosting · E7 JazzCash contract · E8 email provider account · E9 monitoring/alerting service · E10 offsite backup storage.

**D — Post-launch improvement:** multi-day scheduling (P18) · image upload (P19) · favorites wiring (P17) · native push · web ordering for students/faculty · guest ordering (P20) · IP/global rate limiting (P15) · mobile online-option gating (P16) · staff-rejection UX polish · charts/exports for reports · metrics/alerting code.

## 14. Exact suggested next phase

**Phase 36 — Launch-Blocker Remediation (application).** Scope: P1 staff Collect action · P2 daily-menu publish UI · P3 production email delivery integration (code + tests; account provisioning stays external) · P11 webhook production guard. Deliverables: implementation + targeted tests + evidence doc + commit. Explicitly out of scope: any deployment, external accounts, JazzCash, frontend redesigns, B/C/D items, dependency upgrades.

---

*Prepared by code inspection at `5d381d4`. No code changes were made in this phase. No deployment claims. No fabricated infrastructure.*
