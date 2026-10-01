# PHASE 26 — JazzCash Payment Provider Technical Readiness Specification

**Phase:** 26A — JazzCash technical readiness (provider-specific assessment)
**Status:** DOCUMENTATION / READINESS ASSESSMENT ONLY — **IMPLEMENTATION BLOCKED**
**Date:** 2026-10-01
**Baseline commit:** `bdb2a2e` — `docs: add payment provider selection specification` (Phase 25)
**Predecessors:** `PHASE_24_PAYMENT_PROVIDER_READINESS.md` (`d3a8a37`), `PHASE_25_PAYMENT_PROVIDER_SELECTION.md` (`bdb2a2e`)
**Code changes:** None. Documentation only.
**Commit message:** `docs: add JazzCash payment readiness specification`

---

## 1. Executive Summary

Phase 26A assessed whether JazzCash can be implemented against an **officially verified technical contract** without inventing API behavior.

**Conclusion: implementation is BLOCKED.** JazzCash publishes official pages for its Payment Gateway *product*, merchant *onboarding*, and business accounts — but **no official technical API documentation is publicly available anywhere on jazzcash.com.pk**. The documented distribution channel for payment solutions is a sales contact form ("GET IN TOUCH") and business helplines; developer portal paths either 404 on JazzCash's own site or are unreachable from this environment. Every element of the implementation contract — initiation parameters, base URLs, signature/SecureHash mechanism, callback payload format, event/transaction ID semantics, server-side status inquiry, refund/reversal API, sandbox credentials, callback whitelisting — is **UNVERIFIED**.

Per the phase constraint ("If official technical documentation is unavailable, explicitly record the missing information instead of guessing"), this document records:

- What **IS** officially verified: the hosted-payment product, the customer payment flow, merchant onboarding requirements, and that individuals with a CNIC operating a business are eligible for a JazzCash Business Account.
- What is **NOT** verified: the complete technical implementation contract (listed exhaustively in §19).
- What must be **obtained from JazzCash merchant support** before a future implementation phase may begin.

Nothing was implemented. The production fail-closed behavior (test provider blocked in production), the fail-closed provider factory, and the `PaymentProvider` architecture remain untouched.

---

## 2. Baseline Verification

Verified immediately before this phase's research:

- Git: `main`, HEAD `bdb2a2e`, working tree clean. Phase 25 report committed documentation-only (292 insertions).
- `apps/api/app/modules/payments/providers/__init__.py`: Phase 24 factory intact — `PROVIDER_REGISTRY = {"test": TestPaymentProvider}`, `DEFAULT_PROVIDER_NAME = "test"`, unknown names raise `ServiceUnavailableError("Payment provider is not configured")` (fail closed, no mock fallback). **Re-read in full this phase.**
- `providers/base.py`: `PaymentProvider` ABC unchanged — `initiate_payment`, `verify_payment`, `verify_webhook_signature`, `process_refund` (full signatures captured in Phase 25 §4 and re-verified this phase).
- `providers/` contains only `__init__.py`, `base.py`, `test_provider.py` — **no real provider implementation exists.**
- `RefundProcessor` ABC (`refunds/processors/base.py`) and mock-only implementation unchanged.
- Production guard in `payments/service.py`: `APP_ENV == "production"` + test provider → `ServiceUnavailableError` → HTTP 503. **Untouched.**
- Payment data model unchanged: `PaymentStatus` (PENDING, PROCESSING, SUCCEEDED, FAILED, CANCELLED, REFUND_PENDING, PARTIALLY_REFUNDED, REFUNDED) and `PaymentAttemptStatus` (PENDING, PROCESSING, SUCCEEDED, FAILED); amounts are integer paisa; currency `PKR`.

---

## 3. JazzCash Merchant Product Identified (Official)

Source: `https://www.jazzcash.com.pk/business/accept-payments/payment-gateway` (JazzCash Payment Gateway page — "JazzCash Online Ecommerce Payment Gateway Solution Pakistan"), retrieved 2026-10-01.

**VERIFIED — official product claims:**

- Merchants "accept cashless payments through a host of payment methods" via the gateway; customers pay with "their preferred JazzCash or bank account."
- "5+ Payment Methods Supported": **JazzCash Payment** (hosted checkout), **Voucher payment**, **Raast QR**, **Tap on Phone** (NFC debit/credit cards), plus card options referenced on the page.
- "**Real-time payment confirmation**" — merchants receive confirmation "directly in their JazzCash Business account."
- **JazzCash Payment (hosted checkout) — official "How It Works":**
  1. Customer selects JazzCash at merchant checkout.
  2. Customer enters JazzCash mobile number and last six digits of CNIC (optional per page).
  3. Customer confirms the order / places the order.
  4. Customer receives a **USSD prompt** on the registered mobile number.
  5. Customer confirms with **MPIN**.
  6. Customer receives an **SMS confirmation**; payment is completed.
- **Voucher payment:** merchant creates a 12-digit voucher; customer receives it via SMS and redeems at a JazzCash retailer.
- **Raast QR:** customer scans with any participating bank app/wallet; funds credited to the business account in real time; Till ID payments also supported (offline option); only a printed or digital QR is required (source: `https://www.jazzcash.com.pk/business/accept-payments/qr-raast-payments`).
- **Fees:** Schedule of Charges PDF (`SOC-Q3-2026-Final.pdf`, 01 Jul 2026) referenced; page states "**MDR may apply as per agreement**" → pricing is **not publicly specified** and is contract-dependent.
- **Technical documentation:** none on the page. The only documented path to payment solutions is the **"GET IN TOUCH" sales contact form** ("Let's find the right payment solution for you", Head Office location, submit button). No developer portal, API manual, integration guide, or sandbox link exists anywhere on the official site (verified in this phase — see §4).

**UNVERIFIED (terminology hints from circulating third-party guides — NOT a contract, recorded only to frame the documentation request):** widely circulated integration tutorials reference a hosted redirect to `jazzcashmerchantapi.jazzcash.pk` with fields such as `pp_MerchantID`, `pp_Amount` (in paisa), `pp_TxnRefNo`, `pp_SecureHash` (HMAC-SHA256 over a field subset), response/callback URLs `pp_ResponseURL` / `pp_MPGResponseURL`, and `pp_TxnStatus` in the response. **These terms are not confirmed by any official document obtained in this phase and must not be used to write code.** They appear here solely as vocabulary to ask JazzCash merchant support to confirm or refute.

---

## 4. Official Documentation Sources — Access Log (2026-10-01)

| # | Official URL | Outcome |
|---|---|---|
| 1 | `https://www.jazzcash.com.pk/business/accept-payments/payment-gateway` | **RETRIEVED** — product page, hosted-checkout UX flow, payment methods, "GET IN TOUCH" form; no technical docs |
| 2 | `https://www.jazzcash.com.pk/business/account/register-your-account` | **RETRIEVED** — full digital onboarding flow + FAQ (see §5) |
| 3 | `https://www.jazzcash.com.pk/business/account/basic-services` | **RETRIEVED** — onboarding FAQ repeated; business tools list; helplines |
| 4 | `https://www.jazzcash.com.pk/business/accept-payments/qr-raast-payments` | **RETRIEVED** — Raast QR product facts (instant, bank-app, printed QR) |
| 5 | `https://www.jazzcash.com.pk/tc` | **RETRIEVED** — MMBL Terms for Mobile Account (consumer wallet terms only; no merchant API terms); Schedule-A/B compliance & information-security PDFs linked |
| 6 | `https://jazzcash.com.pk/developer-portal/` | **404 PAGE NOT FOUND** on JazzCash's own site |
| 7 | `https://developerportal.jazzcash.com.pk/` | **UNREACHABLE / no extractable content** (cannot confirm existence from this environment) |
| 8 | `https://developer.jazzcash.com.pk/` | **UNREACHABLE / no extractable content** (cannot confirm existence from this environment) |
| 9 | `https://merchants.jazzcash.com.pk/` | **UNREACHABLE / no extractable content** (cannot confirm existence from this environment) |
| 10 | `https://jazzcashmerchantapi.jazzcash.pk/` | **UNREACHABLE / no extractable content** (cannot confirm existence from this environment) |
| 11 | `https://www.jazzcash.com.pk/assets/documents/SOC-Q3-2026-Final.pdf` | **NOT EXTRACTABLE** as text (binary PDF); fee values not verifiable here |
| 12 | Rendered payment-gateway page (browser snapshot) | **REVIEWED** — nav, page body, and footer contain **zero** developer/documentation links |

**Finding:** the current official JazzCash website links **no developer portal** anywhere (header nav, mega-menu, page body, footer all checked). Technical documentation appears to be distributed **after merchant onboarding / commercial contact** — consistent with the gateway page's sales-form-only channel.

---

## 5. Merchant Onboarding Requirements (Official)

Sources: register-your-account + basic-services pages, retrieved 2026-10-01.

**VERIFIED — onboarding flow (JazzCash Business App, fully digital):**

1. Download / open JazzCash Business App.
2. Enter mobile number → enter OTP received via SMS.
3. Upload CNIC and personal photo → scan front and back of CNIC → enter CNIC number and issue date.
4. Take a live photo to match with CNIC ("place yourself in the center of the screen").
5. Complete **biometric verification** (BVS).
6. Add business information → enter OTP sent via SMS.
7. Create MPIN → "Account is ready. Accept hassle free payments."

**VERIFIED — official FAQ statements:**

- "Who can open? — **Any eligible Pakistani individual with a valid CNIC operating a business can apply.**"
- "Personal and business accounts can coexist on the same CNIC."
- "Basic onboarding takes only a few minutes. **Final approval may depend on verification checks.**"
- "What documents are required? — **A valid CNIC is mandatory. Additional documents may be required depending on business type.**"
- "When can I start accepting payments? — Once your account is approved and activated, **your Raast QR is generated and ready for use.**"

**UNCLEAR / NOT PUBLIC:**

- **NTN / STRN / bank-account documents:** not listed in public FAQs; "additional documents depending on business type" leaves them undetermined. Whether a gateway merchant account requires them is **UNVERIFIED**.
- **Gateway API credential issuance:** the onboarding narrative ends at **Raast QR activation**. Nothing in the public flow describes receiving Payment Gateway API credentials, merchant IDs for hosted checkout, or callback whitelisting. Gateway integration evidently proceeds through a **commercial agreement** ("MDR may apply as per agreement") — obtainable only via the sales channel.
- **Student-project eligibility:** individuals with a CNIC operating a business are officially eligible for the business account; whether JazzCash approves gateway access for a campus/student project specifically is **UNCLEAR** and decided by JazzCash only. This phase takes no position and creates no credentials.

---

## 6. API Contract

**BLOCKED — no official API specification exists in any publicly accessible official source.**

The following contract elements are **UNVERIFIED** and must be obtained from JazzCash merchant support before implementation:

- Initiation endpoint (method, path, encoding), request parameter list, required/optional flags.
- Amount format at the provider boundary (UniServe holds **integer paisa**; whether `pp_Amount`-style fields expect paisa or rupees is unconfirmed — the adapter must convert at the boundary, but the conversion target is unverified).
- Currency handling (UniServe is PKR-only; confirmation needed that the gateway is PKR-locked).
- Merchant order-reference field semantics and uniqueness constraints (maps to UniServe `idempotency_key` / `payment_id`).
- Response/status codes for initiation success, failure, timeout, and invalid parameter cases.
- Production and sandbox base URLs.
- Session/checkout lifetime, abandonment behavior, and idempotency guarantees.

**Mapping to existing architecture (design constraint, not implementation):** a future `JazzCashProvider` would implement `initiate_payment(...)` returning `PaymentInitiationResult{success, provider_reference, redirect_url, provider_metadata, error_message}`. The hosted-checkout product (§3) fits the existing contract natively: the **redirect URL already exists** in the result schema and the mobile app already receives `redirect_url` (currently unused — mobile redesign is explicitly out of scope for this phase).

---

## 7. Authentication & Signing

**BLOCKED — UNVERIFIED.**

- Whether requests are signed, with which algorithm (third-party guides claim HMAC-SHA256 "SecureHash" over an ordered field subset — **unverified terminology only**), which fields are included/excluded, where the signing secret comes from, and how JazzCash validates requests.
- How **callbacks/responses are authenticated** — this is the critical security question for `verify_webhook_signature`. UniServe's contract requires validating callback authenticity server-side before any state change (Phase 24 pattern: signature verified FIRST, then dedupe/audit keyed by verified event ID). **Without an officially documented callback-authenticity mechanism, no safe webhook implementation is possible.**
- Secret management expectations (per-merchant hash key vs API secret), rotation procedures.

**Consequence:** the existing `WebhookVerificationResult{valid, event_id, event_type, payment_reference, amount, currency, metadata, error_message}` contract cannot be filled with a correct implementation. No guessing is permitted.

---

## 8. Payment Flow (UniServe → JazzCash)

**Partially VERIFIED (customer UX, official) / BLOCKED (server contract).**

Verified customer journey (official §3): select JazzCash → enter mobile + last-6 CNIC digits → confirm order → **USSD prompt** → **MPIN** approval → SMS confirmation. This is a **redirect/hosted flow with out-of-band customer confirmation** — the customer authorizes on the phone line, not inside the merchant app. Timing implications for order-state polling are real but unquantifiable without the API spec (the customer may take minutes to approve the USSD prompt; initiation→callback latency is **UNVERIFIED**).

Intended UniServe sequence (design, pending verification): mobile checkout → `POST /payments/initiate` → `PaymentService.initiate_payment_for_order` → `JazzCashProvider.initiate_payment` (server derives amount in paisa) → return `redirect_url` to client → customer completes hosted checkout → JazzCash notifies server (callback) → `verify_webhook_signature` → transaction verification (status inquiry) → `PaymentStatus.SUCCEEDED` → order eligible for preparation. **Every arrow after "return redirect_url" is BLOCKED on the official contract.**

---

## 9. Callback / Webhook Contract

**BLOCKED — UNVERIFIED.** Specifically unknown:

- Whether JazzCash delivers **push** server-to-server webhooks, only merchant **response URLs** (synchronous redirect targets), or both.
- Payload field list, content type, and how payment status, amounts, merchant references, and provider transaction IDs are conveyed.
- Event/transaction ID semantics (UniServe keys idempotency on the **verified** event ID — the provider's ID field must be identified and trustworthy).
- Retry behavior, duplicate delivery behavior, ordering guarantees, and timeout/retry-backoff expectations for the merchant response URL.
- Callback URL / domain **whitelisting process** (production prerequisite — typically configured in a merchant portal; which portal is unverified, §4 row 9).

**Known integration note (UniServe side, future phase only):** `payments/service.py` currently calls `verify_webhook_signature(payload=..., headers={"provider": provider_name})` — real request headers are **not** passed through. When the official spec shows which headers carry signatures, the router must forward them. **Not changed in this phase** (documentation-only).

---

## 10. Transaction Verification

**BLOCKED — UNVERIFIED — flagged as a production-readiness hard blocker.**

- Whether JazzCash supports **independent server-side transaction status inquiry** (a merchant API call to confirm amount, currency, merchant-order reference, and final status for a provider reference) is **not documented publicly**.
- UniServe's `PaymentProvider` ABC requires `verify_payment(...)` → `PaymentVerificationResult`. Completing payment solely from a client-redirected confirmation is **not acceptable** — the Phase 24 security model requires server-side verification before transitioning a payment to `SUCCEEDED`, which is what unlocks order preparation for online orders.
- **`verify_payment` currently has no call site in `payments/service.py`** — a reconciliation poller is a future implementation-phase deliverable. Whether JazzCash's contract can even satisfy it depends on the status-inquiry API (unverified).

If JazzCash provides no server-side status inquiry, that must be resolved commercially/contractually before production; this phase records it as a blocker, not a workaround.

---

## 11. Refund / Reversal Capabilities

**BLOCKED — UNVERIFIED.**

- No official public documentation of a refund or reversal API exists.
- Unknown: refund initiation endpoint and parameters, partial vs full refund support, refund status lifecycle, refund idempotency, expected processing times, and whether refunds are initiated via API only or also via the JazzCash Business App back-office.
- UniServe mapping (pending verification): `RefundProcessor.create_refund(*, refund_id, payment_provider_reference, amount, currency, idempotency_key, reason)` / `verify_refund(*, provider_reference)` — a future `JazzCashRefundProcessor` would implement these; `RefundResult`/`RefundProcessingResult` schemas already exist.
- Consumer T&C note (official `/tc`): wallet-side instructions are "deemed fixed and finalized... may not subsequently be changed or reversed" from the *bank's* liability perspective — this is consumer-wallet language, **not** a merchant refund policy; merchant refund terms remain governed by the unobtained commercial agreement.

---

## 12. Mobile UX

**No redesign performed (explicitly out of scope). Verified current-state facts:**

- Mobile (`apps/mobile`) serves student/faculty; `checkout.tsx` calls `initiatePayment`; the returned `redirect_url` is currently **not used**; `order/[id].tsx` polls payment status every 15s; `data.ts` returns the typed `{payment_id, status, provider_name?, redirect_url?, message}`.
- **Future hosted-flow consideration (design note, not an implementation):** a hosted JazzCash checkout implies the customer leaves the app context to a web flow, then approves via USSD/MPIN on their handset. Recovery states that must eventually be handled: app backgrounded during redirect, provider timeout, customer cancellation, network interruption, and the window between USSD approval and server callback. Mobile changes are deferred to a dedicated provider-implementation phase after the official contract exists.

---

## 13. UniServe Architecture Mapping (Existing Contract ← JazzCash Reality)

| ABC method | Existing implementation point | JazzCash fit | Status |
|---|---|---|---|
| `initiate_payment` | `service.py` → provider factory → `PaymentInitiationResult` incl. `redirect_url` | Hosted-checkout redirect fits natively; amount server-derived (paisa); redirect URL already returned to client | Contract fit **UNVERIFIED** (params/URLs unconfirmed) |
| `verify_payment` | Defined in ABC; **no service call site yet** (reconciliation poller = future work) | Requires official status-inquiry API | **BLOCKED** |
| `verify_webhook_signature` | `service.py` webhook path (signature-first, verified-ID idempotency, Phase 24) | Requires official callback-authenticity mechanism; router must forward real headers (future fix) | **BLOCKED** |
| `process_refund` | ABC + `RefundProcessor` (mock only) | Requires official refund/reversal API | **BLOCKED** |

**Architecture verdict:** the Phase 24 abstraction accommodates a hosted-checkout provider without replacement. Nothing in the architecture needs redesign; everything blocked is blocked on **missing official contract**, not on design debt. The fail-closed factory (`ServiceUnavailableError` for unknown providers) and the production guard (test provider → 503) remain the correct posture while blocked.

---

## 14. Security Model (Checklist vs Official Evidence)

| Control | Requirement | Official evidence | Status |
|---|---|---|---|
| Callback authenticity | Verify JazzCash-authenticated notifications before state change | No mechanism documented | **BLOCKED (production blocker)** |
| Server-side transaction verification | Independently confirm amount/currency/reference/status via provider API | Not documented publicly | **BLOCKED (production blocker)** |
| Amount integrity | Server-derived amounts; reject mismatched callback amounts | Pattern exists (Phase 24); callback amount field unverified | Blocked on spec |
| Idempotency | Key dedupe on verified provider event ID | Pattern exists (Phase 24); provider ID semantics unverified | Blocked on spec |
| Credential handling | Secrets backend-only env vars; never in repo/mobile/web | Existing convention (7 blank `PAYMENT_*` vars) | **VERIFIED (internal)** |
| Fail-closed defaults | Unknown provider → 503; production test provider → 503 | Code verified this phase | **VERIFIED (internal)** |
| Replay protection | Timestamp/expiry or nonce handling in callbacks | Not documented | Blocked on spec |
| Least privilege | Separate sandbox/production credentials; rotation | Not documented | Blocked on spec |

---

## 15. Environment Variables

**No new variables added.** The existing backend-only contract stands (all blank defaults, no values in repo):

| Setting | Default | Purpose |
|---|---|---|
| `PAYMENT_PROVIDER` | `"test"` | Provider selection; must name a registered real provider to enable payments |
| `PAYMENT_ENVIRONMENT` | `"sandbox"` | Environment selector |
| `PAYMENT_MERCHANT_ID` | `""` | Merchant identifier |
| `PAYMENT_API_KEY` | `""` | API key |
| `PAYMENT_API_SECRET` | `""` | API secret |
| `PAYMENT_WEBHOOK_SECRET` | `""` | Webhook/callback secret |
| `PAYMENT_CALLBACK_URL` | `""` | Merchant callback/response URL (backend) |

**Pending official spec (provisional, NOT implemented):** if JazzCash's contract requires additional distinct values (e.g., separate live/sandbox base URLs, a distinct hash/signing secret, or a status-inquiry path), new backend-only variables will be specified in the implementation phase. No variable may be invented now because the official requirement list does not exist.

---

## 16. Testing Matrix (Planned — Runs Only After Official Docs Exist)

Provider-neutral; the existing suite (573 backend tests + 31 E2E, Phase 24 baseline — unchanged this phase) stays green regardless.

- **Initiation:** correct amount (paisa conversion boundary); incorrect/zero/negative amount; missing credentials; provider unavailable/unreachable; malformed provider response; duplicate initiation with same idempotency key.
- **Callback/Webhook:** valid signature; invalid signature; missing signature; modified amount; modified txn/event ID; duplicate delivery; replay of old payload; unknown payment; already-completed payment; cancelled; failed; wrong currency.
- **Status inquiry (`verify_payment`):** success/failed/pending transactions; mismatched amount; mismatched currency; mismatched merchant-order reference; inquiry for unknown provider reference.
- **Refunds:** successful refund; partial refund (if supported); failed refund; refund idempotency; refund on non-succeeded payment.
- **Mobile recovery:** app open/backgrounded/closed during hosted redirect; user cancels; provider timeout; network interruption; USSD approval delayed beyond poll window.
- **Reconciliation poller:** (to be added) periodic verification of pending payments; safe idempotent transitions; no double-succeed.
- **E2E (test provider path unchanged):** existing 31-checkout E2E remains the regression gate until a real provider lands behind a flag.

---

## 17. Sandbox Requirements

**BLOCKED — availability UNVERIFIED.**

- No official page, portal, or process for obtaining JazzCash **sandbox/test merchant credentials** was found (§4).
- The official site's only stated path is the sales "GET IN TOUCH" form and business helplines (8000 / 051-111-118-000 / WhatsApp 0325-4444-786).
- **No sandbox claim is made. No test credentials exist. No mock provider impersonating JazzCash was created** (explicitly prohibited and architecturally unnecessary — the factory fails closed).

---

## 18. Production Prerequisites (When Unblocked Later)

1. Official API documentation pack obtained and archived (§19 list) — the contract of record.
2. JazzCash merchant account **approved** + gateway commercial agreement signed (MDR/settlement terms known).
3. Real credentials provisioned (sandbox first, then live); stored only in backend env/secrets.
4. Production base URLs + callback URL/domain whitelisting completed with JazzCash.
5. `JazzCashProvider` + `JazzCashRefundProcessor` implemented against the official spec; registered in `PROVIDER_REGISTRY`; reconciliation poller + real-header webhook verification added; full test matrix (§16) passing.
6. `PAYMENT_PROVIDER` switched from `"test"` to `"jazzcash"` in production **only after 1–5** — until then the existing 503 guard stays.
7. No VPS/DNS/Caddy/deployment changes may accompany provider enablement without their own change process (out of scope here).

---

## 19. VERIFIED / UNVERIFIED / BLOCKED / NOT APPLICABLE Classification

| Item | Classification | Evidence / Note |
|---|---|---|
| JazzCash Payment Gateway product exists (hosted checkout, voucher, Raast QR, Tap on Phone) | **VERIFIED** | Official gateway page (§4 row 1) |
| Customer payment UX (mobile no. + CNIC last-6 → USSD → MPIN → SMS) | **VERIFIED** | Official "How It Works" |
| "Real-time payment confirmation" to business account | **VERIFIED (claim)** | Official page; server-side mechanics unverified |
| Merchant onboarding flow (Business App, CNIC, biometric, OTP, MPIN) | **VERIFIED** | Official onboarding pages |
| Individuals with CNIC operating a business can hold business accounts | **VERIFIED** | Official FAQ |
| Onboarding approval may require additional documents per business type | **VERIFIED (vague)** | Official FAQ; NTN/STRN unlisted → **UNCLEAR** |
| Public developer portal / API manual | **NOT FOUND** | `/developer-portal/` = 404; subdomains unreachable (§4) |
| Initiation API (endpoint, params, amount unit, order-ref semantics) | **UNVERIFIED — BLOCKED** | Obtain from JazzCash merchant support |
| Production/sandbox base URLs | **UNVERIFIED — BLOCKED** | Idem |
| Signature/SecureHash mechanism | **UNVERIFIED — BLOCKED** | Third-party guides unconfirmed; must not be implemented |
| Callback payload + authenticity verification | **UNVERIFIED — BLOCKED** | **Production-readiness hard blocker** |
| Event/txn ID semantics, retry/duplicate behavior | **UNVERIFIED — BLOCKED** | Idem |
| Server-side transaction status inquiry (`verify_payment`) | **UNVERIFIED — BLOCKED** | **Production-readiness hard blocker** |
| Refund/reversal API | **UNVERIFIED — BLOCKED** | Idem |
| Sandbox/test merchant provisioning | **UNVERIFIED — BLOCKED** | No public process found |
| Callback/domain whitelisting process | **UNVERIFIED — BLOCKED** | Idem |
| MDR/fees + settlement timeline | **UNVERIFIED** | "MDR may apply as per agreement"; SOC PDF not machine-readable here |
| Gateway access for student/campus project | **UNCLEAR** | Individual CNIC eligibility verified; gateway approval is JazzCash's decision |
| Production fail-closed behavior (test provider → 503) | **VERIFIED (internal)** | Code re-read this phase; untouched |
| Fail-closed factory (unknown provider → error) | **VERIFIED (internal)** | `providers/__init__.py` re-read in full; untouched |
| Existing PAYMENT_* env contract (7 backend-only vars, blank defaults) | **VERIFIED (internal)** | Untouched |
| Mobile redirect handling | **NOT APPLICABLE (this phase)** | Docs-only; redesign deferred |
| Deployment/VPS/DNS/Caddy changes | **NOT APPLICABLE (this phase)** | Explicitly prohibited; none performed |

**Missing information — the exact list to obtain from JazzCash merchant support:**

1. Official Payment Gateway API integration manual (initiation endpoint, full parameter table, required/optional flags, amount unit, currency field, merchant order-reference semantics).
2. Production and sandbox base URLs.
3. Signature/integrity mechanism for requests (algorithm, field subset, canonicalization, secret source) **and** for callbacks (how authenticity of notifications is proven).
4. Callback/response payload format (fields, status codes, content type) and whether push webhooks exist in addition to response URLs; retry/duplicate/ordering semantics.
5. Transaction **status inquiry** API for independent server-side verification.
6. Refund/reversal API specification and lifecycle.
7. Sandbox test-merchant provisioning process and test instruments.
8. Callback URL / domain whitelisting procedure (merchant portal access).
9. Commercial terms: MDR, settlement timeline, contract duration, exit terms.
10. Additional onboarding documents required for gateway access beyond the basic business account (NTN/STRN/bank proof etc.).

---

## 20. Exact Next Implementation Steps (Future Phase — Gated)

**Precondition for any implementation phase: the §19 missing-information list is fully obtained from official JazzCash channels and archived as the contract of record.** Then:

1. Map official spec → `PaymentProvider` ABC; write the `JazzCashProvider` (hosted-checkout initiation, amount paisa→provider-unit conversion at boundary, redirect URL return, provider metadata storage).
2. Implement callback route per spec: forward **real headers/payload**; signature verification first; verified-event-ID idempotency (Phase 24 pattern); never trust client-redirected completion.
3. Implement `verify_payment` via official status inquiry; add the reconciliation poller (no service call site exists today); transitions must be idempotent and must not double-succeed.
4. Implement `JazzCashRefundProcessor` per official refund spec.
5. Add new backend-only env vars **only** as the official spec requires; extend env templates; never commit real values.
6. Register `"jazzcash"` in `PROVIDER_REGISTRY` (no other architecture changes; test provider remains for tests; production guard logic retained until cutover).
7. Run the §16 test matrix + full regression (573 tests, 31 E2E) against sandbox credentials obtained from JazzCash; then a separate, explicit production-enablement change (`PAYMENT_PROVIDER=jazzcash`) with its own runbook.
8. Mobile: dedicated phase to consume `redirect_url` and handle recovery states — only after the backend contract is verified.
9. **Do not** enable JazzCash in production, remove the fail-closed guard, substitute another provider, or deploy — without the verified contract and an explicit phase.

---

## Evidence & Access Log (Summary)

- All official sources accessed 2026-10-01; per-URL outcomes in §4.
- Third-party sources (blogs, GitHub repos, old SDKs, tutorials) were **not** used as authority. Circulating `pp_*` / "SecureHash" terminology is recorded once (§3) strictly as an unverified hint for the documentation request.
- Repo contract evidence: `providers/__init__.py`, `providers/base.py`, `refunds/processors/base.py`, `payments/service.py`, schemas/models — read/re-verified this phase; all unchanged from Phase 24/25 state.
- Code changes this phase: **none**. Tests run this phase: **none beyond baseline** (no code changed; Phase 24 baseline of 573/573 + 31/31 stands). Deployment actions: **none**.
