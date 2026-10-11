# Phase 58 — Customer Self-Service Completion & Default-Path Correctness

**Status:** COMPLETE — all workstreams implemented, 853 backend tests passing, live E2E probes 51/51.
**Date:** 2026-10-07
**Verifications:** backend suite 853 passed · web `tsc` 0 errors · mobile `tsc` 0 errors · live probes A–J (51 checks) all green · admin Sidebar Inventory browser-verified.

---

## 1. Executive Summary

Phase 58 closed the highest-priority gaps left open by the Phase 57 audit: customers can now request refunds and cancel individual pending items from mobile; students and faculty can change their passwords and manage a PIN login entirely self-service; the four previously unwired admin reports (stock levels, low stock, inventory turnover, peak hours) are live in the web admin Reports page; managers get close-day and order-ETA in the web console; the admin console gains an Inventory nav entry; students/faculty no longer see inactive cafeterias by default; and the order-reject enum mismatch between web UI and backend is fixed. Every claim below is backed by code evidence, automated tests, or live API probes against the running stack.

**Non-goals (verbatim, honored):** "Do not start another broad audit. Do not redo completed phases. Do not redesign the product. Implement only the scope defined below."
**Other constraints honored:** "Do not claim unimplemented features work. Preserve all existing functionality. No commits, no pushes, no deploys." "Do not weaken any backend authorization to make the UI work."

## 2. Scope Delivered (Workstreams A–H)

| # | Workstream | Outcome |
|---|------------|---------|
| A | Inactive cafeteria P1 default fix | Student/faculty `GET /cafeterias` defaults to active-only; explicit `?is_active=` always honored; admin/manager/staff unchanged. Mobile `getCafeterias()` pins `is_active=true`. |
| B | Customer refund request + partial-cancel UI (mobile) | Order detail shows refund history + "Request refund" form for terminal orders, and per-item Cancel for pending multi-item orders (last item cancels the whole order). |
| C | 4 reports wired into web admin Reports | Stock Levels, Low Stock, Turnover, Peak Hours — independent load/fail states; "All Cafeterias" core report never blanks when a per-cafeteria report fails. |
| D | Admin Inventory nav | "Inventory" entry in admin Sidebar between Menu and Staff. |
| E | Manager close-day (web) | Close-day danger action + confirm modal with optional notes on the Orders page; toast reports cancelled count; cafeteria restored to open via status control. |
| E2 | Partial-cancel + ETA (web & mobile) | ETA banner in the web order-details modal (pending/preparing/ready; fetch failure never blocks the modal); mobile partial-cancel in workstream B. |
| F | Student/faculty password self-service (mobile) | "Change Password" sheet in Profile with strength rules and server-message surfacing. |
| G | Student/faculty PIN self-service (mobile) | PIN sheet with Enable/Change/Disable modes + PIN quick-login mode on the login screen (stored-user aware). |
| H | Refund/order-reject enum mismatch | `OrderRejectionReason` aligned to the backend enum in shared-types; web reject modal uses the enum dropdown. (Phase 57 P2-8 refund-rejection was a **false positive** — see §14.) |

## 3. Repository / Git Baseline

- HEAD: `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` — **unchanged before and after Phase 58. Zero commits, zero pushes, zero deploys.**
- Dirty working tree = pre-existing Phase 43–57 baseline (never reverted) + the 15 Phase 58 files below + `live_verify_phase58.py` + this report.
- Root `package-lock.json` untouched (SHA256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A`).
- Phase 58 changed files: `apps/api/app/modules/cafeterias/router.py`, `apps/api/tests/test_cafeterias.py`, `apps/mobile/src/services/data.ts`, `apps/mobile/src/services/auth.ts`, `apps/mobile/src/contexts/AuthContext.tsx`, `apps/mobile/app/(app)/order/[id].tsx`, `apps/mobile/app/(app)/(tabs)/profile.tsx`, `apps/mobile/app/(auth)/login.tsx`, `packages/shared-types/src/index.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/app/dashboard/admin/reports/page.tsx`, `apps/web/src/app/dashboard/orders/page.tsx`, `apps/web/src/components/Sidebar.tsx`, `live_verify_phase58.py` (new), this report (new). `apps/web/src/app/dashboard/admin/refunds/page.tsx` was inspected and found already correct — not modified.

## 4. Environment & Live Stack (incl. DB-identity resolution)

- **Live DB identity — resolved.** Container `uniserve_postgres` holds only `postgres` + **`uniserve_prod`** (there is no `uniserve_dev`). `apps/api/.env` is **stale** (claims `uniserve_dev` / `uniserve_dev_password`); pydantic `SettingsConfigDict(env_file=".env")` gives **real environment variables precedence over `.env`**. Working uvicorn: started from `apps\api` with explicit `$env:POSTGRES_HOST=localhost`, `POSTGRES_PORT=5433`, `POSTGRES_USER=uniserve`, `POSTGRES_PASSWORD=0scZH…`, `POSTGRES_DB=uniserve_prod` → healthy on `:8001` serving current code.
- **Health ≠ DB.** The health endpoint does not query the database — it returned 200 while DB credentials were wrong (worker ticks logged `InvalidPasswordError`). Never infer DB connectivity from `/health`.
- **Ports:** API `:8001` (uvicorn, live probes), Postgres `:5433`, web `:3000` (Next dev, Probe D), n8n `:5678`.
- **Test environment:** repo-root venv `.\.venv\Scripts\python.exe`; from `apps\api`: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`. Docker `uniserve_api` container holds stale baked code — **never** used for tests.
- **Web dev API base:** `apps/web/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` (docker-compose default port). The Phase 58 probe API ran on `:8001`, so dashboard data cards rendered 0 in the browser probe — a pre-existing local port mismatch, not a Phase 58 defect; sidebar/nav rendering is client-side and independent of the API.

## 5. Workstream A — Inactive Cafeteria Default Fix (P1)

- **Router** (`cafeterias/router.py`): after student type-filtering, `if is_active is None and auth.user.role in (Role.STUDENT, Role.FACULTY): is_active = True`. Explicit `?is_active=` is always honored for every role; admin/manager/staff keep the all-records default. Students still never see FACULTY-type cafeterias (pre-existing rule preserved).
- **Mobile** (`services/data.ts`): `getCafeterias()` → `/cafeterias?is_active=true` (defense in depth on the default path).
- **Tests:** 4 new tests in `test_cafeterias.py` (student/faculty default excludes inactive; admin/manager default includes) — **21/21 pass**.
- **Live:** Probe A — student default sees 2 active (inactive IDs absent); faculty sees 3 active; admin sees all 5 incl. both inactive probe cafeterias; manager sees all 5; student explicit `?is_active=false` still returns the inactive cafeterias; active STUDENT cafeteria visible; FACULTY cafeteria hidden from student (type rule intact).

## 6. Workstream B — Customer Refund Request (Mobile)

- `services/data.ts`: `getRefundableAmount(orderId)` → `GET /refunds/refundable/{id}`; `requestRefund(orderId, {amount, reason, reason_note?, idempotency_key})` → `POST /refunds?order_id=…`; `getOrderRefunds(orderId)` → `GET /refunds/order/{id}` → `.refunds ?? []`. `RefundableAmount`/`OrderRefund` interfaces mirror the backend payloads exactly.
- `order/[id].tsx`: Refunds section on terminal orders (completed/cancelled) — history rows with honest status badges (pending → "Pending review", processing → "Processing", succeeded → "Approved — returned", failed → "Rejected"); request form with the 6-value `RefundReason` enum, decimal-pad amount validated `> 0` and `≤ refundable`, note ≤ 500, deterministic `idempotency_key` `refund-req-{orderId}`; non-terminal orders get a disabled "Request refund" hint. Success message: "Refund request submitted for review. The money will be returned to your account after admin approval."
- **Honesty constraint:** the owner endpoint `GET /refunds/order/{id}` omits `rejection_reason`, so refund history shows **status only** — the UI never invents a rejection reason.
- **Live:** Probe B — refundable info 200 (paid 32000 PKR, refundable 32000); exact mobile body → **201** refund created (`pending`); idempotent replay → same refund ID; owner history lists it; non-owner → 403.

## 7. Workstream B — Customer Partial-Item Cancel (Mobile)

- `services/data.ts`: `partialCancelItem(orderId, itemId, reason?)` → `POST /orders/{id}/partial-cancel` with `{item_id, reason: reason || null}`.
- `order/[id].tsx`: per-item Cancel pressable when `status === "pending" && items.length > 1`, with the backend's **last-item-cancels-the-whole-order** rule stated in the UI. Single-item pending orders keep the existing whole-order cancel (backend rejects partial-cancel on the last item by design).
- **Backend scope honored:** partial-cancel is OWNER-ONLY on the backend, so it is wired **only** in mobile. The manager console keeps the existing full manager-cancel — no backend authorization was weakened to force a manager partial-cancel.
- **Live:** Probe E2 — pending order #6 had 2 items / 34000 paisa → owner partial-cancel 200 → 1 item remains / total recalculated to **10000**; non-owner → 403.

## 8. Workstream C — Admin Reports Wiring (4 Reports)

- `apps/web/src/lib/api.ts`: `getInventoryStockLevelsReport`, `getInventoryLowStockReport`, `getInventoryTurnoverReport(cafeteriaId, params?)`, `getCafeteriaPeakHoursReport(cafeteriaId, params?)` with a shared `reportQuery` helper.
- `dashboard/admin/reports/page.tsx`: four new sections — Stock Levels (summary tiles + item table with status badges), Low Stock (table), Turnover (tiles + signed Δ adjustments table), Peak Hours (timezone note + hourly strip). Design rules: each report loads in its own try/catch so one failure never blanks the core report; "All Cafeterias" keeps the core report loaded with a per-section hint when a cafeteria-scoped report is unavailable; `LoadErrorState` per section.
- **Live:** Probe C — all four endpoints 200 with correct shapes against the Faculty Cafeteria (peak-hours carries `timezone: "Asia/Karachi"`; stock-levels `total_items=13`; turnover `total_adjustments=1`); assigned manager 200; staff of another cafeteria **403**; manager of another cafeteria **403** (assignment guards intact — admin remains exempt by design).

## 9. Workstream D — Admin Inventory Nav

- `Sidebar.tsx`: "Inventory" entry in `adminNavItems` after Menu, before Staff; `href /dashboard/inventory`; `roles ["university_admin"]`.
- **Live (browser-verified):** logged into the web app as `admin@lgu.edu.pk`; the sidebar navigation shows **Inventory → `/dashboard/inventory`** positioned between Menu and Staff. Verification level: navigation rendering confirmed in a real browser session; per-section data tiles require the API at the port in `.env.local` (see §4) and were verified through the live API probes instead.

## 10. Workstream E — Manager Close-Day (Web)

- `api.ts`: `closeCafeteriaDay(cafeteriaId, notes?)` → `POST /orders/cafeteria/{id}/close` with `{notes: notes || null}`.
- Orders page: Close-Day danger button + confirm modal (notes ≤ 500); `handleCloseDay` toasts `"{cafeteriaLabel} closed — {n} open order(s) cancelled"`. Manager-only + assignment enforced by the backend — unchanged.
- **Live:** Probe E1 — assigned manager (sana.malik) closed the Faculty day → 200, **3 open orders cancelled** (pending + preparing per backend rule); `operational_status` became `closed`; student close attempt → 403; cafeteria **restored to `open`** via `PATCH /cafeterias/{id}/status` (probe cleanup).

## 11. Workstream E2 — Order ETA (Web) + Mobile Partial-Cancel

- `api.ts`: `getOrderEta(orderId)` → `GET /orders/{id}/eta` → `{order_id, eta_minutes, pickup_deadline?}`.
- Orders page details modal: ETA banner for pending/preparing/ready orders; if the ETA fetch fails the modal still opens with `eta = null` — ETA can never block order details.
- **Live:** Probe E3 — owner gets 200 with `eta_minutes: 5`; non-owner → 403. (Mobile partial-cancel covered in §7.)

## 12. Workstream F — Password Self-Service (Mobile)

- `services/auth.ts`: `changePassword(current, next)` → `POST /auth/password/change` → `{message}`.
- Profile sheet: three password inputs, live strength rules (8–128, upper+lower+digit), server message surfaced verbatim on success and errors inline on failure.
- **Live:** Probe F — disposable student `phase58.probe35c8c7b4@student.lgu.edu.pk` (dev-only registration + email-verified via the established probe convention): original-password login 200 → change 200 ("Password changed successfully") → login with new password works → old password 401 → wrong current password 401 → weak new password 422. Password restored to `TempPass123!` after the probe.

## 13. Workstream G — PIN Self-Service (Mobile)

- `services/auth.ts`: `enablePin` / `changePin` / `disablePin` → `/auth/pin/enable|change|disable` (backend-exact bodies: `{current_password, pin, confirm_pin}`, `{current_pin, new_pin, confirm_pin}`, `{current_password}`).
- `AuthContext.pinLogin(userId, pin)` mirrors `login()`: `POST /auth/pin/login` → tokens + user persisted in SecureStorage → session restored.
- Profile sheet: Enable/Change/Disable mode chips with per-mode forms; honest helper text — "The server decides whether a PIN is active — if a change fails, the server message appears below." (the backend exposes **no** `pin_enabled` state, so the UI never claims PIN is active).
- Login screen: stored-user-aware "Use PIN instead" quick-login mode ("Sign in as {email} with your PIN."); password flow untouched.
- **Live:** Probe G (10/10) — enable 200 → PIN login 200 with tokens → wrong PIN 400 → change 200 → new PIN works, old PIN 400 → mismatched confirm 422 → disable 200 → PIN login 400 after disable → disable with wrong password 401. Disposable user left with password restored and **PIN disabled**.

## 14. Workstream H — Reject-Order Enum Fix (+ Phase 57 P2-8 false positive)

- **Real mismatch fixed:** `packages/shared-types` `OrderRejectionReason = "capacity" | "item_unavailable" | "cafeteria_issue" | "operational_issue" | "other"` — now identical to the backend enum; the web Orders-page reject modal uses an enum dropdown + humanized stored values.
- **Phase 57 P2-8 was a false positive:** `dashboard/admin/refunds/page.tsx` was re-inspected — it uses a free-text `rejection_reason` field **matching the refunds backend contract** (reject min 10 / max 500 chars). The file was already correct and was not modified. The actual enum mismatch was the **order-reject** modal, now fixed.
- **Live:** Probe H — valid enum `capacity` accepted and stored (order response shows `rejection_reason: "capacity"`); bogus enum → **400** with guidance `"Invalid rejection reason. Must be one of: capacity, item_unavailable, cafeteria_issue, operational_issue, other"`.

## 15. Shared Types & Contract Alignment

- `packages/shared-types/src/index.ts`: `OrderRejectionReason` enum aligned (H); PIN contracts replaced with backend-exact `PINSetupRequest` / `PINChangeRequest` / `PINDisableRequest`; `PINLoginRequest {user_id, pin}` unchanged.
- All new mobile service functions (`data.ts`, `auth.ts`) and web API wrappers (`api.ts`) were written against the verified backend schemas — no optimistic assumptions; probe bodies in `live_verify_phase58.py` use the **exact** request shapes the UIs send.

## 16. Automated Tests, Type Checks & Lint

| Gate | Result |
|------|--------|
| Backend suite (full) | **853 passed** in 384.57s |
| Workstream A tests (`test_cafeterias.py`) | **21/21 passed** (17 existing + 4 new) |
| Web `tsc --noEmit` (run from `apps\web`) | **0 errors** |
| Mobile `tsc --noEmit` (run from `apps\mobile`) | **0 errors** |
| Web lint | EXIT=1 — **known baseline** (`next/dist/compiled/babel/eslint-parser` missing from eslint-config-next). Unchanged from before Phase 58; not fixed per instructions. |

## 17. Live E2E Verification — Probe Harness & Results

**Harness:** `live_verify_phase58.py` (repo root, httpx, `BASE_URL=http://127.0.0.1:8001/api/v1`, **no trailing slashes** — FastAPI's 307 redirect drops POST bodies). Logins: admin, manager (Faculty-assigned), staff (Student-assigned), student, faculty. Probe order is destructive-last: logins → A → C → E3 → E2 → H → E1 → B → F/G → J; cleanup restores the Faculty cafeteria to `open`, restores the disposable user's password, and disables the PIN.

**Result: 51/51 checks PASS** (49/50 on the first full run + corrected A6/A6b re-run; the single first-run failure was a *probe-script assertion error*, not a product defect — see §21).

| Probe | Checks | Highlights (live responses) |
|-------|--------|------------------------------|
| A — inactive default | 7 | student default 2 active, inactive absent; faculty 3; admin/manager all 5 incl. 2 inactive; explicit `is_active=false` honored; FACULTY type still hidden from students |
| C — admin reports | 7 | all 4 endpoints 200 with correct shapes (timezone, totals, adjustments); manager 200; cross-cafeteria staff **403**, cross-cafeteria manager **403** |
| E3 — ETA | 2 | owner 200 `eta_minutes=5`; non-owner 403 |
| E2 — partial cancel | 3 | 2 items/34000 → 1 item/**10000** after owner cancel; non-owner 403 |
| H — reject enum | 2 | `capacity` stored; bogus enum 400 + "Must be one of: …" guidance |
| E1 — close-day | 4 | manager close 200, **3 orders cancelled**; status `closed`; student 403; restored `open` |
| B — refunds | 5 | refundable 200 (32000 PKR); request **201**; idempotent replay same ID; owner history lists it; non-owner 403 |
| F — password | 7 | change 200; new password works; old 401; wrong current 401; weak 422 |
| G — PIN | 10 | enable/login/change/disable full lifecycle 200; wrong PIN 400; mismatch 422; wrong-password disable 401 |
| J — regression guards | 4 | staff cross-cafeteria orders 403; manager unassigned-cafeteria orders 403; admin refunds console 200 intact; student → refunds console 403 |

## 18. Live Data Effects & Restoration (`uniserve_prod` — dev DB)

| Object | Effect | Restored? |
|--------|--------|-----------|
| Faculty Cafeteria `287038a2…` | close-day → `closed`, 3 open orders cancelled; then restored `open` | ✅ |
| Order #6 `35fe0c86…` (ayesha, pending) | 1 of 2 items partial-cancelled; total 34000 → 10000 paisa | n/a (probe target) |
| Order #43 `c6e77b69…` (dr.imran, pending) | rejected with `reason=capacity` | n/a (probe target) |
| Order #46 `18be2aa7…` (ayesha, completed) | refund `a98ad0e9…` created, 32000 paisa, `status=pending` — now visible in the admin Refunds console (J-3 confirmed) | n/a (probe target; pending → admin decision flow) |
| Disposable user `phase58.probe35c8c7b4@student.lgu.edu.pk` | password changed then **restored** to `TempPass123!`; PIN enable→change→disable → **disabled** | ✅ |

## 19. Authorization Preservation

No backend authorization was weakened. All Phase 58 UI wiring calls endpoints that already enforce role + assignment checks, and the probes re-verified them live: cross-cafeteria order listing 403 (staff & manager), cross-cafeteria report reads 403, non-manager close-day 403, non-owner partial-cancel 403, non-owner ETA 403, non-owner refund endpoints 403, student → admin refunds console 403, wrong-password PIN disable 401. Partial-cancel was wired **only** to the owner-facing mobile surface because that is the backend contract — the manager console keeps full manager-cancel instead.

## 20. Limitations & Honest Verification Boundaries

1. **No `pin_enabled` state** is exposed by the backend anywhere — the PIN sheet surfaces server messages verbatim and never claims a PIN is active.
2. **Owner refund history omits `rejection_reason`** — refund history shows status only (mapped to honest labels); the full rejection detail lives in the admin console.
3. **Phase 57 P2-8 (refund-rejection free text) was a false positive** — the refunds console already matches the backend contract; the real enum mismatch (order reject) is what H fixed.
4. **Partial-cancel is mobile-only** (owner-only backend); no manager partial-cancel exists in either UI by design.
5. **Mobile UI verification level:** type-checked (0 tsc errors) + contract-aligned + every request body exercised live through the probe harness — **not** run on a physical device this phase.
6. **Probe D browser verification** covers nav rendering; the data tiles on per-section reports are verified at the API level (Probe C) because the web dev `.env.local` points at `:8000` while the probe API runs on `:8001` (pre-existing local port mismatch).
7. **Web lint baseline** (EXIT=1, missing `next/dist/compiled/babel/eslint-parser`) is untouched — fixing it is out of scope and was explicitly not attempted.
8. **Refund deadline:** probe B ran with ~2h left on the 72h window for order #46 — it succeeded; the deadline gate itself is enforced by `test_refunds.py` in the automated suite.

## 21. Deviations From Plan (probe-harness corrections, not product defects)

1. **A6 first-run failure:** the initial assertion required students to see the FACULTY cafeteria — that contradicts the pre-existing router rule (students never see FACULTY-type cafeterias, independent of the Phase 58 is_active fix). The assertion was split into A6 (active STUDENT cafeteria visible ✅) and A6b (FACULTY hidden from student ✅) — both pass; product behavior was correct all along.
2. **C7 reframe:** the original "unknown cafeteria → 404" check was replaced with the more meaningful "manager of a *different* cafeteria → 403" assignment-guard probe (admin is exempt from the cafeteria assignment check by design, so unknown-ID behavior is not a meaningful 404 probe for admins).
3. **Trailing-slash lesson (harness only):** FastAPI 307-redirects `/path/` → `/path` and httpx drops the POST body on redirect → 422 "Field required". The harness uses exact non-slash paths, matching the proven `live_verify.py` convention.

## 22. Final Acceptance & Artifacts

**ACCEPTED.** All eight workstreams (A–H) are implemented, tested (853 backend tests green; both apps compile clean), and live-verified (51/51 probe checks against the real stack on `uniserve_prod`). Existing functionality was preserved (regression probes J-1…J-4 re-verified the authorization boundaries Phase 58 must not disturb), no backend authorization was weakened, no unimplemented feature is claimed to work, and **no commits, pushes, or deploys were performed** — HEAD remains `bc967b35…`.

**Artifacts:**
- `PHASE_58_CUSTOMER_SELF_SERVICE_AND_DEFAULT_PATH_CORRECTNESS.md` — this report.
- `live_verify_phase58.py` — reproducible A–J probe harness (logins, 51 checks, cleanup).
- Code: 13 modified files + 2 new files (full list in §3).
- Prior context: `PHASE_57_POST_PHASE_56_PRODUCT_COMPLETENESS_AUDIT.md` (gap source), Phase 56 acceptance report (P2-1 reopened → now fixed).
