# PHASE 51 — Admin Refund Management & Resolution

**Status:** COMPLETE — all objectives met; regression green; no deployment performed.
**Date:** 2026-10-05
**Runtime:** uvicorn Phase 51 code on `:8001` (live DB `uniserve_prod`, migration head `0013`), web dev on `:3000`.

---

## 1. Objective

Extend the existing refunds module with an admin-facing resolution workflow:

1. Admin/manager review of refund requests with full decision context (student, order, payment).
2. **Approval** path that processes a refund through the configured refund processor — with UI copy that states the sandbox semantics honestly (no real money movement is claimed anywhere).
3. **Rejection** path with a **persisted, validated rejection reason** (min 10 / max 500 chars) surfaced in admin list + detail.
4. Backend-authoritative authorization; confirmation dialogs with accurate approval semantics; clearly-marked "Phase 51 E2E" test data; zero regressions.

## 2. Existing architecture discovered

- Refunds module (`apps/api/app/modules/refunds/`): `models.py` (Refund + RefundEvent), `service.py` (create_refund, process_refund, refundable computation, 72h deadline), `router.py` (user-facing create/list/refundable).
- Payments: TestPaymentProvider (sandbox) + TestRefundProcessor; webhook `/payments/webhook/test_provider`; provider_reference format `test_pay_{payment_id[:12]}`.
- Notifications: typed notifications with templates; existing `refund_requested` / `refund_succeeded` types; Phase 50 broadcast infra untouched.
- Web admin console: Phase 46+ patterns (ModalShell, StatusBadge, LoadErrorState, getApiErrorInfo, Button variants primary|secondary|gold|ghost|danger), refunds page previously a stub-ish list using user-facing RefundResponse.
- Shared types package (`packages/shared-types`) consumed by web via declarations in `dist/`.

## 3. Existing state machine (before Phase 51)

```
PENDING → PROCESSING → SUCCEEDED | FAILED      (process_refund — sandbox processor)
```
Terminal states had no admin resolution path other than processing; no rejection concept existed.

**Final state machine (after Phase 51):**
```
PENDING → PROCESSING → SUCCEEDED | FAILED      (process_refund — admin/manager approve path)
PENDING → REJECTED                             (reject_refund — admin/manager reject path)
```
- Only PENDING refunds may be processed or rejected. Repeat actions on resolved refunds → **400 VALIDATION_ERROR** ("Cannot process/reject refund in <status> status"); nonexistent refund → **404**.
- `processed_by` / `processed_at` are reused for **both** approve and reject (resolver / resolved-at). No schema change needed.

## 4. ACTUAL approval semantics (sandbox — money-safety critical)

- "Approving" a refund request calls `process_refund`, which invokes the **TestRefundProcessor — a simulated sandbox processor**. It performs **NO real bank transfer and NO real money movement of any kind**.
- Success only occurs when `payment.provider_reference` startswith `test_pay_` (the TestPaymentProvider signature). On success:
  - refund → `SUCCEEDED`, `processed_by`/`processed_at` set, refund `provider_reference = test_ref_{id[:12]}` (sandbox marker),
  - payment → `REFUNDED` (full amount) or `PARTIALLY_REFUNDED` (partial),
  - `refund_succeeded` (refund_processed) notification to the requester; inventory release if reserved.
- If the processor fails, refund → `FAILED`; payment remains `SUCCEEDED`.
- **Every piece of UI copy states this explicitly**: toast "processed through the configured refund processor (sandbox/test mode)"; approve dialog warning box "Sandbox processing — no real money movement … does **not** represent a real bank transfer, and no money is actually returned to the student's account by this action"; resolved detail shows "no real bank transfer is represented by this record."
- No claim of money being returned is made anywhere in UI, API responses, or notifications.

## 5. Actual rejection semantics

- `reject_refund` (only on PENDING): sets status `REJECTED`, persists `rejection_reason` (stripped, 10–500 chars — two-layer validated), sets `processed_by`/`processed_at`, records a `refund_rejected` RefundEvent (audit), and emits a `refund_rejected` notification to the student.
- **Rejection moves NO money**: payment stays `SUCCEEDED`; no processor call; no provider_reference change.
- Notification body template uses **only `{order_number}`** — the rejection reason is deliberately NOT included in the notification body (privacy by design; reason remains visible in admin detail and refund records).

## 6. Authorization policy (backend-authoritative)

| Endpoint | Who | Notes |
|---|---|---|
| POST /refunds (create) | any authenticated user | own orders only (existing) |
| POST /refunds/{id}/process | UNIVERSITY_ADMIN (any) + CAFETERIA_MANAGER (assigned cafeteria only) | Phase 51 kept this unchanged |
| POST /refunds/{id}/reject | UNIVERSITY_ADMIN (any) + CAFETERIA_MANAGER (assigned cafeteria only) | **matched to process auth — deliberately NOT broadened** |
| GET /refunds/admin/all | UNIVERSITY_ADMIN only | enriched RefundAdminListResponse {refunds, total} |
| GET /refunds/admin/{id} | UNIVERSITY_ADMIN only | RefundAdminResponse with nested contexts |

Errors: unauth → **401**; unauthorized role/scope → **403**; validation → **400/422**; not found → **404**.

## 7. Cafeteria scoping

- `RequireCafeteriaScope` (core/deps.py): students → Student Cafeteria only (no assignment row needed); Faculty Cafeteria → faculty-category users only; manager/staff → assigned cafeteria only; admin → all.
- Refund process/reject additionally enforce the manager's assignment to the cafeteria that **owns the refund** (`_verify_cafeteria_assignment` in refunds/service.py) → cross-cafeteria manager gets **403 "You are not assigned to this cafeteria"**.
- Ordering of checks: state validation (400) runs before scope validation (403) on already-resolved refunds — the action is denied either way (no mutation); the true scope-403 is observable on PENDING refunds (verified E2E + unit test `test_manager_cannot_reject_other_cafeteria`).

## 8. Files changed

**Backend**
- `apps/api/app/modules/refunds/models.py` — RefundStatus + `REJECTED`; `Refund.rejection_reason` TEXT nullable; RefundEvent refund_rejected.
- `apps/api/app/modules/refunds/schemas.py` — `RefundRejectRequest` (min10/max500), `RefundStudentContext`, `RefundOrderContext`, `RefundPaymentContext` (non-sensitive only: status/provider/provider_reference/amount/currency), `RefundAdminResponse`, `RefundAdminListResponse`; `from __future__ import annotations` removed (ruff TC003).
- `apps/api/app/modules/refunds/service.py` — `reject_refund`, `build_admin_response`, `list_admin_refunds`, `get_admin_refund`, `_get_user`; existing create/process untouched.
- `apps/api/app/modules/refunds/router.py` — GET /admin/all, GET /admin/{refund_id}, POST /{refund_id}/reject (route order preserved: user routes first).
- `apps/api/app/modules/notifications/models.py` — `NotificationType.REFUND_REJECTED`.
- `apps/api/app/modules/notifications/service.py` — template "Refund Rejected" / body `…order #{order_number}…` + type mapping.
- `apps/api/migrations/versions/0013_refund_rejection.py` — add_column refunds.rejection_reason (nullable).
- `apps/api/tests/test_phase51_refund_management.py` — 31 tests (authorization 8, rejection workflow 10, approval workflow 8, data integrity 5).

**Web**
- `packages/shared-types/src/index.ts` — `"rejected"` in RefundStatus; `"refund_rejected"` in NotificationType; `Refund.rejection_reason?`; RefundRejectRequest / contexts / RefundAdminResponse / RefundAdminListResponse. **dist rebuilt via `npm run build --workspace=packages/shared-types` (exit 0).**
- `apps/web/src/lib/api.ts` — getAllRefunds typed to RefundAdminListResponse; new `getAdminRefund`, `rejectRefund`; `processRefund` unchanged.
- `apps/web/src/components/ui/StatusBadge.tsx` — `rejected` red badge.
- `apps/web/src/app/dashboard/notifications/page.tsx` — refund_rejected X-circle icon.
- `apps/web/src/app/dashboard/admin/refunds/page.tsx` — **full console rewrite** (see §10).

## 9. DB migration

- **0013** `refunds.rejection_reason` TEXT, nullable — additive only; applied to live DB (alembic head `0013`, verified `0013_refund_rejection.py` at head).
- `REJECTED` status requires **no migration** (RefundStatus StrEnum with `native_enum=False` → stored as string). `refund_rejected` notification type requires **no migration** (NotificationType `String(50)`).
- No destructive changes; rollback = drop the single nullable column.

## 10. UI implementation (`/dashboard/admin/refunds`)

- Status filters use **real backend statuses**: all / pending / processing / succeeded / failed / rejected (replaced the previously bogus "approved" filter).
- Table: Order (#), Student (name + university_email), Reason (label + reason_note), Amount (Rs. paisa/100 en-PK), Status badge, Date, Actions — **View** always; **Approve (primary)** + **Reject (danger)** only on pending rows; resolved rows show View only (double-submit guard + backend400s behind it).
- Detail modal (ModalShell max-w-2xl) loads via `getAdminRefund` and shows five sections: **Student** (name/email/university_id/role), **Order** (order_number/status/payment_method/total/cafeteria_name/created_at), **Payment** (status/provider_name/provider_reference mono/amount/currency), **Refund request** (reason/reason_note/created_at/provider_reference), **Resolution** (pending → "Awaiting an admin decision"; resolved → Decision / Resolved by / Resolved at / Rejection reason when rejected; succeeded → sandbox disclaimer paragraph).
- Approve dialog: order+student+amount summary + yellow warning box with the exact sandbox/no-real-transfer copy; Cancel + "Approve request".
- Reject dialog: required textarea (maxLength 500, live `{n}/500` counter), inline "Minimum 10 characters." validation on trim <10 (request NOT sent), note "Rejection records this decision and notifies the student. No money movement occurs.", Cancel + "Reject request".
- Error/loading states follow Phase 46 patterns: compact banner when data exists, full LoadErrorState when empty, skeletons while loading; load failures never render fake success data.

## 11. Backend implementation

- `reject_refund(*, refund_id, rejected_by_user_id, rejected_by_role, rejection_reason)`: only PENDING; reason stripped then re-validated (<10 → 400 ValidationError); sets REJECTED + rejection_reason + processed_by/processed_at; writes RefundEvent `refund_rejected`; emits refund_rejected notification.
- `build_admin_response(refund)`: assembles RefundAdminResponse with nested student/order/payment contexts (payment context limited to non-sensitive fields).
- `list_admin_refunds(*, cafeteria_id, status, limit, offset)`: optional Order join, real total count → {refunds, total}.
- `get_admin_refund(refund_id)`: 404 if missing; enriched response.
- `process_refund` untouched (sandbox processor semantics in §4).

## 12. Validation rules

- `rejection_reason`: pydantic `Field(min_length=10, max_length=500)` → **422** on schema violation; service strips whitespace then re-validates (<10 → **400**); whitespace-only never passes.
- Web mirrors client-side (trim <10 → inline error, nothing sent; maxLength 500).
- Refund amount rules unchanged (≤ payment.amount − succeeded refunds; 72h deadline; own orders only).

## 13. Test results

- **Phase 51 suite: 31/31 PASSED** (`test_phase51_refund_management.py`): TestRejectAuthorization (8) — student/manager-other-cafeteria/admin×reject, unauth, admin list/detail role checks; TestRejectionWorkflow (10) — persisted reason, REJECTED status, resolver fields, event, notification, invalid reasons, repeat rejection400, payment untouched; TestApprovalWorkflow (8) — succeeded path, sandbox ref `test_ref_`, payment refunded/partially_refunded, duplicate process 400; TestDataIntegrity (5) — contexts non-sensitive, list totals, terminal-state immutability.
- Existing `test_refunds.py` (32) untouched and passing.
- **Full regression: `800 passed`** (769 baseline + 31 Phase 51) — first full run this session: `800 passed in 311.16s`; post-E2E re-run green (§18 confirms final count). Zero regressions; `$env:POSTGRES_*` cleared for all runs.

## 14. Live E2E results (A–H) — all PASS

Data creation (real API flows, clearly-marked "Phase 51 E2E"): student login → menu item → cart → checkout (online) → payment initiate → test-provider webhook (`test_pay_*` refs — seeded payments have NULL provider_reference, so flows must go through initiate+webhook) → refund request PENDING. Published today's (2026-10-05) daily menus at Student + Faculty Cafeterias via the real admin API (checkout requires a published menu — "No published menu available for today" otherwise).

| # | Scenario | Result |
|---|---|---|
| **A** | Admin list loads | **PASS** — student name+email, reason labels + "Phase 51 E2E" notes, accurate statuses, Rs. amounts, dates, real status filters |
| **B** | Detail modal | **PASS** — all five sections; cafeteria_name "Student Cafeteria"; payment provider_reference `test_pay_…`; resolution "Awaiting an admin decision" |
| **C** | Approve (bilal #48) | **PASS** — confirmation dialog shows sandbox copy verbatim ("Sandbox processing — no real money movement … does **not** represent a real bank transfer"); after confirm: toast "processed through the configured refund processor (sandbox/test mode)"; refund `SUCCEEDED`; payment `refunded`; refund provider ref `test_ref_df7d9fbd-b35`; Resolved by admin + Resolved at shown; Approve/Reject buttons removed from resolved row |
| **D** | Reject (fatima #49) | **PASS** — dialog with required reason + "No money movement occurs."; after valid reason: toast "Refund request rejected. The decision reason has been recorded."; refund `rejected` badge; detail Resolution shows Decision "Rejected", Resolved by/at, and the persisted rejection reason; **payment still `succeeded`** (no money moved) |
| **E** | Invalid rejection reason | **PASS** — 2-char reason blocked client-side ("A reason of at least 10 characters is required."); request NOT sent; refund stayed `pending` |
| **F** | Already-resolved actions | **PASS** — repeat process on succeeded, process on rejected, reject on rejected, reject on succeeded → all **400** VALIDATION_ERROR with status-specific messages; final state unchanged (no corruption) |
| **G** | Error state | **PASS** — page.route injection of 500 on `/api/v1/refunds/admin/all` → "Unable to load refunds." + "The server encountered a problem. Please try again." + Try again; **no fake data**; unroute + Try again → real data (#49 rejected, #48 succeeded) |
| **H** | Permissions | **PASS** — student (bilal) → 403 on admin list+detail; manager sana (assigned to **Faculty** cafeteria) → 403 on admin list+detail AND 403 "You are not assigned to this cafeteria" on process/reject of a **PENDING** Student-cafeteria refund; on already-resolved refunds the 400 state-validation fires first (still denied); anonymous → 401 everywhere; **no mutations** across all probes (pending refund verified still pending, succeeded/rejected refunds verified intact) |

## 15. Data-integrity results (live DB)

| Table | Baseline | After E2E | Δ / notes |
|---|---|---|---|
| users | 15 | **15** | unchanged |
| cafeterias | 3 | **3** | unchanged |
| menu_items | 32 | **32** | unchanged |
| daily_menus | 10 | **12** | +2 published 2026-10-05 menus (Student + Faculty) — E2E setup data |
| orders | 47 | **50** | +3 "Phase 51 E2E" orders (approve/reject/scope cases) |
| order_items | 46 | **49** | +3 |
| payments | 34 | **37** | +3, all `test_pay_*` refs; approved-case payment `refunded`; others `succeeded` |
| refunds | 0 | **3** | #48 succeeded (processed_by set, no reason), #49 rejected (reason persisted), #52 pending (scope probe) — all reason_notes carry "Phase 51 E2E" |
| notifications | 120 | **131** | +3 refund_requested, +1 refund_processed, +1 refund_rejected (body = order number only), +3 payment_confirmed, +3 order_created; 2 Phase 50 admin_announcements intact |

- No payment secrets exposed anywhere (PaymentResponse + RefundPaymentContext carry only status/provider/reference/amount/currency).
- Accidental duplicate rows from a script import re-run were removed via FK-safe SQL (notifications→refunds→payments→order_items→orders); verified totals match baseline+expected.
- Money-safety invariants held: order totals never altered; payment statuses changed only by existing semantics; no fabricated transaction references (all `test_pay_`/`test_ref_` are the existing sandbox formats); rejection moved no money.

## 16. Known limitations

- **Sandbox processor only**: approval success depends on the TestPaymentProvider `test_pay_` prefix; a real provider integration is explicitly out of scope (Phase 51 does not redesign payments).
- **Notification body lacks the rejection reason by design** ({order_number}-only template) — reason is visible in admin console and refund records.
- Manager cross-cafeteria **403 is only observable on PENDING refunds**; resolved-refund duplicate attempts return 400 state-validation first (still denied, no mutation).
- Live seeded payments have NULL provider_reference → any real-flow refund test must go through initiate+webhook.
- Web `output: export` warnings + lockfile-patch TypeError remain pre-existing dev-server cosmetics.

## 17. Build / type / lint status

- `npm run type-check:web` → **exit 0**.
- ESLint on all changed web files → **exit 0** (cosmetic "Pages directory cannot be found" warning, pre-existing).
- Backend ruff → clean (`--no-fix` check on changed modules; pyproject fix=true baseline).
- `npm run build --workspace=apps/web` → **exit 1 — identical to baseline** (dual React 19 root / React 18 web; styled-jsx crash prerendering stock /404,/500; PageNotFoundError ENOENT in load-components). **Documented, not fixed** — out of scope.
- shared-types dist rebuilt via `npm run build --workspace=packages/shared-types` → exit 0; new declarations verified in `dist/index.d.ts`.

## 18. Git status

- Branch `main`; HEAD **`bc967b35fccaf7bb6c1b3a4b31e356000bd788ee`** — unchanged; **no commits, no pushes, no resets/cleans, no new branches**.
- `package-lock.json` SHA-256 **`2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A`** — unchanged.
- `git diff --check` → exit 0 (only the pre-existing LF→CRLF warning on `apps/mobile/package.json`).
- Working tree: inherited Phases 43–50 dirty state + Phase 51 files (refunds module, notifications, migration 0013, tests, web console files, shared-types) + phase reports (untracked). All Phase 51 temp files (notes, E2E scripts, token files) deleted before this inspection — verified absent.
- Post-E2E full regression: **800 passed** (769 baseline + 31 Phase 51) — final confirmation run green.

## 19. No-deployment confirmation

- **No deployment, Docker production change, or infrastructure change was performed in Phase 51.**
- No new dependencies; lockfile untouched; no CI/CD changes; no real payment provider credentials or bank integrations touched.
- Live verification used the local dev uvicorn (:8001) + local dev web (:3000) + local Postgres container — the same rehearsal environment as prior phases.
- Real money was never moved; all "refunded" outcomes are sandbox/test records explicitly marked as such.

---

**Phase 51 complete. Phase 52 NOT started — awaiting next instruction.**
