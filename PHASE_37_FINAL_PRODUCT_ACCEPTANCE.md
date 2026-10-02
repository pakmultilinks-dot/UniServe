# Phase 37 — Final Product Acceptance Test

**Date:** 2026-10-02
**Starting commit:** `f2a68a2` (`feat: close launch-blocking product gaps`)
**Classification used throughout:** PRODUCT BUG / TEST-ENVIRONMENT ISSUE / EXTERNAL PREREQUISITE / EXPECTED BEHAVIOR
**Verdict legend:** PASS / FAIL / BLOCKED / NOT TESTED (no scores or rankings)

---

## 1. Baseline & Scope

- Starting tree: commit `f2a68a2`, clean except the in-tree rehearsal `infrastructure/caddy/Caddyfile` (restored before the final commit).
- This phase did **not** restart Phase 35/36, did **not** run a repository-wide gap inventory, did **not** deploy or configure VPS/DNS/EAS/SMTP/JazzCash, did **not** upgrade dependencies, and did **not** redesign UI.
- Every flow was exercised against the **actual running local production stack** wherever practical (live HTTP against the Caddy-fronted API and live browser sessions against the built web console).
- Fix policy applied: bugs were **recorded, classified, and judged for launch-blocking**; no fixes were implemented because the three discovered defects are not all "small + directly in scope + clearly required," and the instruction for multiple substantial discoveries is to stop implementation and report. **No code changes and no new tests were made in this phase.**

## 2. Environment Used

| Component | State |
|---|---|
| `uniserve_api` | Healthy, internal :8000; **container rebuilt this session from HEAD** (see §11) |
| `uniserve_postgres` | Healthy; used directly for defect evidence queries |
| `uniserve_caddy` | Local rehearsal config on :80/:443 (in-tree file restored pre-commit) |
| API base | `http://localhost/api/v1` (health 200) |
| Web console | `http://app.localhost/` (Next.js static export served by Caddy) |
| Runtime mode | `APP_ENV=production`, `APP_DEBUG=false`; **no** `SMTP_*` or `PAYMENT_PROVIDER` variables → production fail-closed paths active |
| Test accounts | Seeded role accounts (students, faculty customers, staff, managers, admin) per the repository seed scripts; credentials not reproduced here |

## 3. Baseline Data Readiness — **PASS**

Realistic data present and verified live: two cafeterias (Student / Faculty), published daily menus, inventory records, carts, and all role accounts log in successfully (customer, staff, manager, admin). Student/faculty cafeteria visibility rules confirmed at the data level (students only see Student Cafeteria).

## 4. Student Ordering Flow — **PASS (14/14)**

Live API chain with the student account and the Student Cafeteria staff account:

1. Student login → 200.
2. Cafeteria list → student sees **only** Student Cafeteria (documented rule).
3. Menu view → published daily-menu items returned.
4. Add to cart → 201.
5. Cart → quantity 1 and correct unit subtotal.
6. Update cart quantity to 2 → subtotal doubles correctly.
7. Cash checkout → 201, order number + total = 2 × unit price.
8. Order details by number → total and `payment_method=cash` correct.
9. Order history contains the order.
10. Staff queue at Student Cafeteria contains the order.
11a. Staff confirms order (confirmation gate before preparation) → 200.
11b. Staff sets `preparing`; customer poll sees `preparing`.
12. Staff sets `ready`; customer poll sees `ready`.
13. Staff collects by order number → `completed`; customer sees `completed`.

*Note:* step 12 used the generic `PUT /orders/{id}/status` path; see BUG 2 (§18) — it does not affect this flow's outcome but is an API-contract gap.

## 5. Faculty Ordering Flow — **PASS (9/9 effective)**

Faculty **customer** account at the Faculty Cafeteria (the similarly-named manager account is a different user — role confusion in the first harness run was a TEST-ENVIRONMENT ISSUE, corrected):

1. Faculty login → 200.
2. Faculty views **both** cafeterias (documented rule).
3. Faculty-cafeteria menu (published daily menu) visible.
4. Cart add → 201.
5. Cash checkout → 201 with correct total.
6. Order fetch by number → order id + `pending`.
7. Faculty-cafeteria manager sees the order in the faculty queue.
8. Isolation: the faculty order does **not** appear in a student's cafeteria-scoped order list.
9. Manager-driven lifecycle confirm → preparing → ready → collect → `completed`; customer sees `completed`.

## 6. Staff Web Console — **PASS** (live browser)

Staff login → staff dashboard renders with real API data; Order Queue loads the assigned cafeteria's orders with live status chips; **confirm / preparing / ready / collect actions executed successfully against live orders**; role-aware navigation shows only staff items; unauthorized surfaces (menu management, daily-menu admin, inventory writes, manager-only actions) are absent or denied.

*Observations (EXPECTED BEHAVIOR, not defects):* the cafeteria switcher defaults to the first cafeteria in the list, so a staff member assigned elsewhere sees 403 responses in the console until they switch — correct isolation, slightly noisy default; dashboard "N Cafeterias" counts the cafeteria list, not the user's assignments.

## 7. Manager Daily-Menu Flow — **PASS** (web UI + API 10/10)

Web: manager dashboard, cafeteria switcher, Menu Management page, published daily-menu view with items/prices/status, add-item flow — all live-verified.

API harness (Faculty Cafeteria manager):

1. Create draft daily menu for tomorrow → 201 `draft`.
2. Add item with special price (PKR 110) → entry stored.
3. Add second item → 200.
4. Remove item from draft → removed.
5. Publish draft → 200 `published`.
6. Tomorrow's menu listed as published with the special price.
7. Today's published menu untouched (12 items, published).
8. Staff daily-menu writes denied (create/add/publish → 403).
9. Daily-menu admin list denied to staff and the probing student account (scope/role denial).
10. Cross-cafeteria manager write denied → 403.

## 8. Scheduled Orders — **PASS (9/9)**

1. Student places scheduled order for 22:00 → 201, `scheduled`, time stored, `pending`.
2. Order details carry the collection time.
3. Past collection time rejected (400/422, "past").
4. Malformed time ("25:99") rejected.
5. Scheduled checkout without a time rejected ("requires a collection time").
6. Faculty places scheduled order at faculty cafeteria (cafeteria-local scheduling) → 201.
7. Owner cancels own pending scheduled order before the deadline → 200 `cancelled`.
8. Double-cancel rejected.
9. Scheduled order stays `pending` until preparation (inventory reservation deferred to preparation, by design).

## 9. Inventory — **FAIL (11/12)**

1. Staff lists cafeteria inventory → non-empty.
2. Target inventory item on today's menu identified.
3. Staff adjusts stock to 2 → low-stock state.
4. Low-stock endpoint flags the item.
5. First checkout consumes a portion (2 → 1).
6. Second checkout consumes the last portion (1 → 0).
7. Zero stock blocks ordering (checkout and cart add → 400 "insufficient inventory").
8. Staff restock → item orderable again, decrement verified.
9. **Concurrency:** last-portion race between two simultaneous checkouts → exactly one 201, one 400, stock floors at 0.
10. Other cafeteria's manager denied inventory write → 403.
11. **FAIL — Student denied inventory read:** expected 401/403, received **200** → **BUG 1** (§18).
12. Positive control: faculty manager lists own cafeteria inventory → non-empty.

Stock restored to a healthy value during cleanup.

## 10. Delay / ETA — **PASS (9/9)**

Using a pending scheduled faculty order, with staff actions performed by the Faculty Cafeteria **manager** account (the faculty customer account correctly receives 403 on staff actions — EXPECTED BEHAVIOR):

1. Order loaded (`pending`, scheduled).
2. Manager confirms + sets `preparing` (re-confirm of an already-confirmed order → 400, tolerated).
3. Manager marks delayed +15 min → 200, state stays `preparing`, ETA updated.
4. Customer ETA endpoint returns the fresh estimate.
5. Customer poll shows updated delay/ETA state.
6. Delay notification appears in the customer inbox.
7. Non-staff (student) delay attempt → 403 role error.
8. Bounds enforced: 0 minutes and 300 minutes → 422.
9. Delayed order completes normally via `ready` → `collect` → `completed`.

## 11. Cancellation / No-Show — **PASS (10/10)**

1. Owner cancels own pending immediate order → 200 `cancelled`.
2. Double cancel → 400 "already cancelled".
3. Confirm after cancel → 400.
4. Collect after cancel → 400.
5. Stranger cannot cancel another user's pending order → 400 "Order does not belong to this user" (enforced via 400, not 403 — behavior recorded).
6. Manager cancels a `preparing` order via `manager-cancel` → 200 `cancelled`.
7. Canonical `PUT /orders/{id}/ready` sets `pickup_deadline` (no-show expiry key) — observed live.
8. A `ready` order cannot be cancelled by owner or manager → 400 "Cannot cancel an order that is ready for collection".
9. **Bug evidence (BUG 2):** generic `PUT /orders/{id}/status {status:"ready"}` reaches state `ready` but leaves `ready_at` and `pickup_deadline` unset.
10. Manager rejects a pending order (`reason: item_unavailable`) → 200 `cancelled`; invalid reason values rejected by enum validation.

All test orders cleaned up via cancel/manager-cancel/collect.

## 12. Payments — **PASS (6/6)**, after a TEST-ENVIRONMENT ISSUE was found and resolved

**Test-environment issue (resolved, not a product defect):** the running `uniserve_api` container was built *before* the Phase 36 webhook fail-closed guard landed; the first harness run showed forged webhooks accepted. The container was rebuilt from HEAD (`docker compose -f docker-compose.prod.yml up -d --build api`), the guard was verified present, health re-checked, and the flow re-run.

1. Cash checkout → 201, payment method recorded; no provider involved.
2. Online checkout → order created `pending` with `payment_method=online` — **no fake payment success**.
3. Payment initiation in production mode → **503** "Online payments are unavailable: no production payment provider is configured" (fail-closed, correct).
4. No succeeded payment exists for the online order (status endpoint 404 / non-succeeded).
5. Forged webhook `POST /payments/webhook/jazzcash` → **503**; order remains `pending` (fail-closed guard active).
6. Online order blocked from `preparing` without a succeeded payment → 400 "Payment not found for online order" (fail-closed enforcement).

Cleanup performed. **EXPECTED BEHAVIOR:** real JazzCash is an EXTERNAL PREREQUISITE (not implemented); cash is the complete flow.

## 13. Authentication & OTP — **FAIL (10/11)**

1. Register new university user → 201 + verification challenge, category `student`.
2. Duplicate registration → 409 ALREADY_EXISTS.
3. Non-university email → 400.
4. Login before email verification → 403 EMAIL_NOT_VERIFIED.
5. Wrong OTP → 400 OTP_ERROR.
6. OTP resend inside cooldown → 429 with remaining seconds (rate limit live-verified).
7. **FAIL — OTP attempt limit:** after 7+ consecutive wrong OTPs the API still returns "Invalid OTP" instead of the documented "Maximum OTP attempts reached" → **BUG 3** (§18, security-relevant).
8. Password-reset request anti-enumeration: identical message for known and unknown emails.
9. Password-reset confirm rejects wrong OTP → 400.
10. Session management: `/auth/me` 200, token refresh 200, logout 200 (Bearer access token), refresh-token reuse after logout → 401 (session revoked).
11. Unverified account remains blocked → 403 (live demonstration of the SMTP EXTERNAL PREREQUISITE).

*First harness run's step-10 failure was a TEST-ENVIRONMENT ISSUE (logout requires the Authorization header; corrected and re-verified).*

## 14. Authorization & Isolation — **PASS (10/10)**, consolidated

Live harness plus evidence accumulated in earlier flows of this phase:

| Check | Result |
|---|---|
| Student GET cafeteria-scoped order list (own or foreign cafeteria) | 403 |
| Faculty customer GET cafeteria-scoped order list | 403 |
| Admin GET both cafeteria queues | 200 (by design) |
| Student faculty-cafeteria menu visibility + checkout | denied (403/404) |
| Student own-cafeteria menu | 200 |
| Daily-menu reads: own cafeteria 200 (customer surface), foreign cafeteria denied | pass |
| Manager-cancel: staff role → 403; cross-cafeteria manager → 403; owner cancel → 200 | pass |
| Delay: student → 403; wrong-cafeteria manager → 403 | pass |
| Inventory: student read **200 (BUG 1 evidence)**; student write → 403 | pass (write side) |
| Student daily-menu admin list / staff writes | 403 |
| Staff delay at wrong cafeteria / students denied `/orders/cafeteria` | 403 (earlier flows) |
| Pre-verification login, wrong-OTP, session revocation | enforced (§13) |

**Overall authorization model: backend-enforced and effective** for all write surfaces and customer-facing reads, with the single inventory-read exception recorded as BUG 1.

## 15. Mobile Application — **BLOCKED (device E2E) / PASS (static verification)**

- `npm run type-check:mobile` (Expo SDK 51, TypeScript) → **clean**.
- `app.json` sanity: valid Expo config (name/slug/bundle ids, expo-router plugin).
- **Physical-device / EAS verification: BLOCKED — EXTERNAL PREREQUISITE.** No device or EAS build was configured (explicitly out of scope for this phase). Mobile runtime behavior (push, notifications UI, camera, offline) is therefore NOT TESTED on-device.

## 16. Web Browser Acceptance (consolidated) — **PASS**

- Staff console and manager console: fully exercised in §6–§7 (login, dashboards, queue actions, menu management, cafeteria switcher, role-aware nav).
- **Customer (student/faculty) web experience — live-verified this session:** after customer login the console redirects to `/mobile-required` ("Use the Mobile App"), correctly displaying the signed-in identity and role; direct navigation to `/dashboard` is also intercepted by the role guard; Sign Out returns to `/login` with the session cleared. **EXPECTED BEHAVIOR:** web is the staff/manager/admin console; customer ordering is intentionally mobile-first — there is no customer menu-browsing surface on web by design.
- Console noise: 401/403 responses during role probing and cafeteria switching are EXPECTED BEHAVIOR (isolation + unauthenticated refresh probes). One CORS error on the notifications polling endpoint was observed during the rehearsal-Caddy window (TEST-ENVIRONMENT ISSUE; production CORS is environment-configured and was not touched this phase).

## 17. Regression Suite & Builds — **PASS (no changes made)**

| Check | Result |
|---|---|
| Backend pytest (`apps/api`, full suite) | **638 passed** (4 m 03 s) |
| `npm run build:shared` (shared-types) | clean |
| `npm run type-check:web` | clean |
| Web production static build (`NEXT_PUBLIC_API_URL=http://localhost/api/v1`) | clean (static export, all routes prerendered) |
| `npm run type-check:mobile` | clean |

No new tests were added: no fixes were implemented, so no regression tests were required by policy.

## 18. Discovered Defects

### PRODUCT BUG 1 — Inventory read exposure to customers (severity: low–medium; **launch-blocking: NO**)

- **Where:** `apps/api/app/modules/inventory/router.py` — `GET /cafeterias/{id}/inventory` and `GET /cafeterias/{id}/low-stock` depend on `RequireCafeteriaScope()` (visibility) instead of the write-scope used by mutations.
- **Live evidence:** student GET → **200** with inventory quantities (isolation harness S9; inventory harness step 11 expected 401/403). Writes correctly → 403.
- **Impact:** stock levels are readable by any authenticated customer with cafeteria visibility; no first-party UI exposes this, and no prices/PII/financial data are exposed. It is an authorization-model inconsistency, not a workflow break.
- **Recommended remediation (hardening phase):** scope inventory GETs to staff/manager/admin; add a regression test asserting customer reads are denied.

### PRODUCT BUG 2 — Generic order-status endpoint's "ready" path omits `ready_at` / `pickup_deadline` (severity: low; **launch-blocking: NO**)

- **Where:** `apps/api/app/modules/orders/service.py` — `update_status` (generic `PUT /orders/{id}/status`) transitions to `ready` without setting the timestamps; only `mark_ready` (canonical `PUT /orders/{id}/ready`) sets `ready_at` + `pickup_deadline`.
- **Live evidence:** cancel/no-show harness step 9 — status `ready` with `pickup_deadline=null`; canonical `/ready` (step 7) sets it.
- **Impact:** no-show expiry keyed on `pickup_deadline` would not fire for orders readied through the generic endpoint. All first-party UIs and verification scripts use the canonical `/ready` path, so the shipped product is unaffected; third-party/API consumers are exposed to the inconsistency.
- **Recommended remediation (hardening phase):** delegate the generic `ready` transition to `mark_ready` (or remove `ready` from the generic status enum); add a regression test asserting `pickup_deadline` is set regardless of entry path.

### PRODUCT BUG 3 — OTP attempt-limit counter never persists (severity: security-relevant, medium–high; **launch-blocking: YES — recommended fix before launch**)

- **Where:** `apps/api/app/modules/auth/service.py` (`verify_otp` increments `challenge.attempts` and flushes, then raises `OTPError`) combined with `apps/api/app/core/database.py` `get_db` (commit on success, **rollback on exception**) — every failed verification rolls the increment back.
- **Live evidence:** after 7+ wrong OTPs the API still answers "Invalid OTP"; direct database inspection shows `otp_challenges.attempts = 0, is_used = false` for both the email-verification and password-reset challenges of the harness users. The documented `OTP_MAX_ATTEMPTS = 5` control is therefore **unreachable via the API in the production runtime**.
- **Test-vs-runtime divergence:** the 638-test suite passes because test fixtures share session state without per-request rollback; the control holds in tests and silently fails in production.
- **Residual risk:** unlimited guessing within each challenge's 10-minute lifetime, plus unlimited fresh challenges via re-registration. Mitigations that *do* work live: OTP expiry, resend cooldown/rate limit (429 verified), resend invalidation of the previous OTP, bcrypt hashing cost, and 6-digit space.
- **Recommended remediation (hardening phase):** persist attempt increments outside the request-transaction rollback path (e.g., a dedicated short-lived commit before raising, or a separate session/update), and add an API-level regression test that asserts the attempt limit **across separate requests**. Changing `get_db` commit semantics globally is *not* a small change and was intentionally not attempted under this phase's fix policy.

### TEST-ENVIRONMENT ISSUES (resolved during the phase; no product impact)

1. **Stale API container image** missing the Phase 36 webhook guard → rebuilt from HEAD and re-verified (§12).
2. **Harness defects** corrected between runs: logout requires a Bearer access token; order creation is cart→checkout (not `POST /orders`); menu-items responses are `{items: [...]}`; `daily-menus/today` is a visibility-scoped read (200 on the user's own cafeteria is EXPECTED BEHAVIOR); `cancel` requires a JSON body; `delay` is a PUT.
3. **Role-account confusion** (faculty *customer* vs cafeteria *manager* with near-identical names) — corrected harness identity selection; server behavior was correct throughout.
4. **Rehearsal Caddyfile** left modified in-tree — restored before the final commit.

### UX OBSERVATIONS (record only; not defects)

- Staff Order Queue switcher defaults to the first cafeteria → isolation-correct 403 console noise until switched; default could respect the user's assignment.
- Dashboard "N Cafeterias" counts the cafeteria list, not the user's assignments.
- Updates are poll-based (no real-time push) on web; mobile push depends on EAS/credentials (external prerequisite).
- Customer web intentionally hands off to the mobile app (`/mobile-required`) — working as designed.

## 19. External Prerequisites & Launch-Readiness

### Remaining external prerequisites (not engineering defects)

1. **Real SMTP delivery + `SMTP_HOST` / `SMTP_FROM_EMAIL` (and credentials) environment variables.** Without them the production email provider fails closed; registration completes but verification emails are never delivered, so accounts stay unverified and login stays 403 (live-verified). Password-reset emails are likewise undelivered (the request endpoint itself is correctly anti-enumeration-safe).
2. **Real online payment provider (JazzCash) implementation + merchant credentials.** Online initiation and webhooks fail closed with 503 by design; online orders cannot progress to preparation without a succeeded payment. Cash flow is complete.
3. **Production deployment targets:** VPS provisioning, domain/DNS, production Caddy config, EAS builds/accounts, and environment configuration were explicitly untouched this phase (local rehearsal only).
4. **Physical mobile devices** for on-device E2E (type-check only so far).

### Remaining application bugs

1. **BUG 3 — OTP attempt-limit rollback (security-relevant)** — the only defect judged **launch-blocking**.
2. BUG 1 — inventory read exposure (low–medium, non-blocking).
3. BUG 2 — generic status "ready" path missing `ready_at`/`pickup_deadline` (low, non-blocking; first-party UIs unaffected).

### Is another engineering phase actually necessary?

**Yes — but a small, focused hardening phase, not a full product phase.** The product workflows (ordering, staff/manager operations, scheduling, delay/ETA, cancellation/no-show, cash payments, isolation, auth sessions) are launch-functional end to end on the running stack. One security control (BUG 3) does not hold in the production runtime and should be fixed and regression-tested before launch; BUG 1 and BUG 2 are small consistency fixes worth including in the same pass. Everything else that blocks a *production* launch is external provisioning (SMTP, payment provider, deployment targets, devices), not engineering scope.

### Final state

- Starting commit: `f2a68a2` → final commit: this report (`docs: add final product acceptance report`).
- Tree at commit: clean (rehearsal Caddyfile restored; build artifacts and `.env.production` are gitignored).
- Regression: 638 backend tests passing; shared build, web type-check, web production build, and mobile type-check all clean.
- Acceptance totals: Student 14/14 · Faculty 9/9 · Staff UI PASS · Manager menu (web PASS + API 10/10) · Scheduled 9/9 · Inventory 11/12 · Delay/ETA 9/9 · Cancellation/no-show 10/10 · Payments 6/6 · Auth/OTP 10/11 · Isolation 10/10 · Mobile type-check PASS (device BLOCKED) · Web acceptance PASS · Regression PASS.
