# Phase 24 — Online Payment Provider Integration Readiness

**Status:** PASS — READY FOR PROVIDER IMPLEMENTATION
**Date:** Phase 24 (post Phase 23, commit `52b49fb` baseline)
**Scope:** Determine exactly what is required to make online payments production-ready **without weakening the existing security model**. No provider was chosen, no credentials integrated, no deployment performed.

---

## 1. Current Online Payment Architecture

Fully traced and verified in this phase (read-only audit of every payment path):

| Layer | Location | Finding |
|---|---|---|
| Provider abstraction | `apps/api/app/modules/payments/providers/base.py` | `PaymentProvider` ABC: `initiate_payment`, `verify_payment`, `verify_webhook_signature`, `process_refund`; result dataclasses carry `provider_reference`, `redirect_url`, verified `event_id`/`amount`/`currency`. Docstring mandates business logic depends only on the interface. |
| Provider registry | `apps/api/app/modules/payments/providers/__init__.py` | NEW: `PROVIDER_REGISTRY` + `create_payment_provider()` factory (this phase, see §7). |
| Mock provider | `providers/test_provider.py` | `TestPaymentProvider` — all flows succeed, signatures always valid, `test_pay_`/`test_ref_` prefixes. |
| Refund abstraction | `providers/refunds/base.py` | Separate `RefundProcessor` ABC (`create_refund`, `verify_refund`) + mock processor; `RefundService` takes it via constructor. Real refund flows need a real processor alongside the provider. |
| Service | `payments/service.py` | `initiate_online_payment` (ownership, `PaymentMethod.ONLINE` only, order PENDING, server-derived amount, idempotency-key dedupe); `handle_payment_success` called **only** from `process_webhook` — no client-reachable paid path (verified: sole callers at `service.py` webhook section). |
| Webhook | `payments/router.py` → `POST /webhooks/{provider}` style route | Signature-based (no auth); always returns generic `{"status": "ok"/"ignored"}` — no information leak. |
| Order gate | order preparation workflow | Online orders cannot start preparation unless `PaymentStatus.SUCCEEDED`. |
| States | `payments/models.py` | `PaymentStatus`: PENDING, PROCESSING, SUCCEEDED, FAILED, CANCELLED, REFUND_PENDING, PARTIALLY_REFUNDED, REFUNDED. `PaymentAttemptStatus`: PENDING, PROCESSING, SUCCEEDED, FAILED. **No states added or removed in this phase.** |
| DB invariants | `payments/models.py` | Amount always server-derived (smallest currency unit, Integer), currency `PKR` default, unique `idempotency_key`, partial unique `provider_reference`, no credentials stored on Payment, `WebhookEvent` unique `provider_event_id` + `processed` flag. |
| Frontend (mobile) | `apps/mobile/app/(app)/checkout.tsx`, `order/[id].tsx`, `data.ts` | `checkoutCart(...)` → `initiatePayment(order_id, key)`; `status === "failed"` surfaces an error; order screen polls payment (15 s) for online orders. `redirect_url` is received but **not yet consumed** (see §9). |
| Frontend (web) | `apps/web` console | Admin/manager/staff only — no payment initiation surface; **zero** payment/secret/merchant references in `next.config.js`, `api.ts` (verified by grep). |

**Security invariants confirmed unchanged:** amount never client-supplied; webhook success never directly client-triggered; RBAC/audit boundaries untouched; Phase 23 production guard intact.

## 2. Current Provider Status

- The **only** registered provider is the mock: `TestPaymentProvider`.
- **No real provider exists anywhere in the repo.** Evidence: providers directory contains only `base.py`, `test_provider.py`, `__init__.py`; zero JazzCash/Easypaisa/PayFast/SadaPay/NayaPay references in real code or docs; Stripe appears only as commented placeholder keys in `.env.production.example` and an "OPTIONAL / not yet configured" line in `PRODUCTION_INTEGRATION_AUDIT.md`; the only ADR (`docs/decisions/001-technology-stack.md`) makes no payment-provider decision; `config.py` had **no** payment settings before this phase.
- **Production guard (Phase 23, retained):** with `APP_ENV=production` and the test provider configured, `initiate_payment_for_order` raises `ServiceUnavailableError` → HTTP 503 `SERVICE_UNAVAILABLE`. Cash payments are unaffected (no provider involved).

## 3. Is the Architecture Ready for a Real Provider?

**YES — READY FOR PROVIDER IMPLEMENTATION.** The `PaymentProvider` ABC is provider-neutral and sufficient as-is (server-documented amounts, signature verification contract, redirect-URL passthrough, refund hook). No redesign is required. The only things missing are provider-specific: a merchant account, credentials, and one class implementing the ABC plus its registry entry. This phase added the provider-selection boundary (factory + settings) so that implementation is a drop-in, and hardened one webhook defect that would have broken real-provider behavior (§6.1).

## 4. Provider Requirements Matrix

For any real candidate, the following are **needed** and **not present** (nothing was fabricated):

| Requirement | Status | Notes |
|---|---|---|
| Merchant/business account | Not present | No account evidence for any provider. |
| Sandbox/test credentials | Not present | No API keys/secrets anywhere in repo or env files. |
| API credentials (live) | Not present | `.env.production.example` ships blank placeholders only. |
| Documented signature scheme | Not present | Required for `verify_webhook_signature` implementation. |
| Webhook endpoint contract | Partial | Our route exists; provider-side URL registration needs DNS/deployment (explicitly out of scope this phase). |
| Refund API | Not present | `RefundProcessor` boundary exists; real processor needed. |
| PKR support | Unverified | No provider PKR capability confirmed. |
| Server-to-server initiation API | Unverified | Required by `initiate_payment` contract. |
| Mobile redirect/deeplink UX | Not implemented | `redirect_url` returned but unused in mobile app. |

**Candidate position:** Stripe is the *only* repo-evidenced name (commented placeholders) — PKR support unverified, no credentials, no decision. JazzCash/Easypaisa/PayFast/SadaPay/NayaPay are **not** evidenced in the repo and are **not** chosen here. **Provider selection remains an explicit human/product decision.**

## 5. Configuration Safety

- New backend-only settings (`config.py`): `PAYMENT_PROVIDER` (default `"test"`), `PAYMENT_ENVIRONMENT` (`sandbox`), `PAYMENT_MERCHANT_ID`, `PAYMENT_API_KEY`, `PAYMENT_API_SECRET`, `PAYMENT_WEBHOOK_SECRET`, `PAYMENT_CALLBACK_URL` — all blank defaults, never frontend-exposed.
- `.env.example` / `.env.production.example`: provider-neutral commented `PAYMENT_*` entries (replaced stale Stripe-only placeholders); production template states payments stay disabled (503) until a registered real provider + credentials are configured; secrets never committed.
- Verified: **zero** payment/secret/merchant references in web/mobile frontend configs — no client-side exposure path.

## 6. Justified Fixes Made (Security-Relevant)

### 6.1 Webhook idempotency keyed on the verified event ID (HIGH)
**Defect:** `process_webhook` deduplicated on the **unverified** `x-event-id` header (default `"unknown"`) looked up **before** signature verification; `result.event_id` from the verified payload was never used. Consequences: (a) providers without the header collapse all events to `"unknown"` → first processed, all later valid events falsely ignored; (b) spoofed-header suppression — an attacker could set the header to a processed ID to suppress a NEW valid signed event.
**Fix:** verify signature **first**; `event_id = (result.event_id or "").strip() or provider_event_id`; all idempotency/audit/storage keyed by that verified ID. Behavior-identical for every existing test (all webhook fixtures carry matching body/header IDs). Regression-proven: header-less duplicates now correctly ignored; forged headers cannot suppress new verified events (§8).

### 6.2 Provider factory with fail-closed selection (M)
`create_payment_provider()` resolves `settings.PAYMENT_PROVIDER` against `PROVIDER_REGISTRY`; unknown/unconfigured names raise `ServiceUnavailableError` (503) — **no silent fallback to the mock**. Router wiring now uses the factory; the Phase 23 production isinstance-guard is retained unchanged.

### Explicitly NOT changed (no manufactured work)
No new payment states; no provider chosen; no credentials added; no reconciliation job; no payment-expiry state; refund processor still mock (documented limitation); mobile redirect UX deferred (documented gap).

## 7. Test Evidence

| Suite | Result |
|---|---|
| New `tests/test_payment_provider_config.py` (10 tests: factory default/case-insensitivity/unknown-name fail-closed/unregistered-setting fail-closed/registry content; cash-in-production 201; unknown-provider initiation 503; testing-env mock allowed; header-less webhook idempotency; spoofed-header cannot suppress) | ✅ 10/10 |
| Payment modules (`test_payments`, `test_security_payments`, `test_payment_preparation_gate`, new config tests) | ✅ **71/71** |
| Full backend regression | ✅ **573/573 passed** (563 baseline + 10 new; 0 failures, 0 skipped) |
| E2E (`scripts/phase19_e2e_test.py`, live API :8000) | ✅ **31/31 — 100%** |
| Web `tsc --noEmit` + `next build` | ✅ 0 errors / build success (static export) |
| Mobile `tsc --noEmit` | ✅ 0 errors |

No test was weakened, skipped, or altered to obtain green results. The pre-existing Phase 23 test `test_initiate_online_payment_blocked_in_production` still passes (production + mock → 503).

## 8. Exact Missing Information (Human Decision Required)

1. **Which provider** — product/business decision with PKR support and Pakistan market availability (no repo evidence supports any choice; Stripe placeholders are not a decision).
2. **Merchant account + sandbox credentials** for the chosen provider.
3. **Signature scheme documentation** for the chosen provider's webhooks.
4. **Callback/webhook public URL** — requires DNS/domain/deployment (explicitly out of scope this phase).
5. **Refund policy alignment** with the provider's refund API semantics.

## 9. Smallest Integration Sequence (When Decision + Credentials Exist)

1. Obtain merchant account + sandbox credentials for the chosen PKR-capable provider.
2. Implement `RealProvider(PaymentProvider)` in `providers/` — `initiate_payment` (server-side amount, return `redirect_url`), `verify_webhook_signature` (constant-time per provider docs), `verify_payment`, `process_refund` (+ `RefundProcessor`).
3. Register it in `PROVIDER_REGISTRY` (e.g. `"jazzcash": JazzCashProvider`).
4. Set `PAYMENT_PROVIDER` + `PAYMENT_*` secrets in backend env only (never committed, never frontend).
5. Implement mobile handling of `redirect_url` (WebBrowser/deeplink) and return-path verification.
6. Add a reconciliation job (poll provider for stuck `PROCESSING` payments; the state machine intentionally has no expiry state).
7. Sandbox E2E: initiate → provider sandbox → webhook → SUCCEEDED → preparation gate → refund; verify idempotency/replay/tamper against the provider's real signature format.

## 10. Remaining Limitations (Honest Boundaries)

- **Online payments are NOT production-ready in the executable sense** — no real provider is implemented or tested; production correctly returns 503 until one is registered. This phase certifies *readiness of the architecture*, not live capability.
- No provider was chosen or configured — a deliberate, required human decision.
- Mobile `redirect_url` consumption not implemented (redirect-based providers will need step 5).
- No reconciliation job; no payment expiry/timeout state (states unchanged by design).
- Refund processor remains the mock until a real provider's refund API is integrated.
- Python dependencies remain unpinned (Phase 23 M-1, out of scope here).
- Webhook URL registration/DNS/HTTPS deferred per phase constraints.

---

*Phase 24 scope respected: no restart, no Phase 23 redo, no VPS/DNS/HTTPS, no unrelated features, no fake success UI, no weakened tests, no fabricated provider choices.*
