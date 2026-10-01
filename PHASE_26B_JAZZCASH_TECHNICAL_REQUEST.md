# PHASE 26B — JazzCash Merchant Technical Access Request

**Phase:** 26B — pre-implementation technical-access request preparation
**Status:** DOCUMENTATION ONLY — no code, no credentials, no provider implementation
**Date:** 2026-10-01
**Baseline commit:** `ed08afa` — `docs: add JazzCash payment readiness specification` (Phase 26A)
**Predecessors:** `PHASE_24_PAYMENT_PROVIDER_READINESS.md`, `PHASE_25_PAYMENT_PROVIDER_SELECTION.md`, `PHASE_26_JAZZCASH_READINESS.md`
**Code changes:** None. Documentation only.
**Commit message:** `docs: prepare JazzCash technical access request`

---

## 1. Baseline & Purpose

**Baseline verified at phase start:** `main`, HEAD `ed08afa`, working tree clean.

**Context (Phase 26A outcome):** JazzCash implementation is **BLOCKED**. The official JazzCash website documents the Payment Gateway *product* (hosted checkout UX, voucher, Raast QR, Tap on Phone) and merchant *onboarding* (Business App, CNIC, biometric), but publishes **no technical API documentation**. Developer-portal paths 404 or are unreachable; the only official channel is the sales "GET IN TOUCH" form and business helplines. Every implementation-critical contract element — initiation parameters, base URLs, request signing, callback authenticity, server-side status inquiry, refund API, sandbox credentials, whitelisting — is UNVERIFIED (full classification in `PHASE_26_JAZZCASH_READINESS.md` §19).

**Purpose of this phase:** prepare a precise, professional technical-access request that can be sent to JazzCash merchant/business support so that the **official documentation pack** and **sandbox/merchant credentials** can be obtained. This document *is* that request (two send-ready versions, §6 and §7) plus the complete information checklist (§3), product-identification questions (§4), the key architecture question (§5), and the external-response procedure (§8).

**Nothing is assumed about JazzCash.** No third-party tutorial, GitHub repository, blog, or old SDK is treated as authoritative. Circulating `pp_*` / "SecureHash" vocabulary (recorded in Phase 26A §3) appears here only as optional confirmation vocabulary for the checklist — never as the contract.

---

## 2. Request Constraints

While waiting for an official JazzCash response, the following remain in force:

- **No implementation.** No JazzCash provider code, endpoints, service changes, or mobile checkout changes.
- **No guessing.** No API behavior inferred from third-party sources.
- **No fake credentials.** No invented merchant IDs, keys, or sandbox claims.
- **No production enablement.** `PAYMENT_PROVIDER` stays `"test"`; the production fail-closed guard (test provider → HTTP 503) and the fail-closed factory (unknown provider → error) stay untouched.
- **No substitution.** No other payment provider is selected or silently swapped in.
- **No deployment changes.** No VPS/DNS/Caddy/HTTPS/.env/Docker modifications.
- **No overclaiming.** The request describes UniServe honestly as a university cafeteria ordering platform in pre-production preparation — not as a large commercial production system.

---

## 3. Technical Information Checklist (Complete)

Everything below must be answered by **official JazzCash documentation or official written confirmation** before any implementation phase begins.

### 3.1 Merchant / API Access

- [ ] Merchant account activation requirements for the **API/e-commerce payment gateway** (distinct from Raast QR merchant activation)
- [ ] Required documents (CNIC, NTN/STRN, bank account, business proof, commercial agreement)
- [ ] Merchant ID issuance process and format
- [ ] API credential types (API key, secret, hash/signature key) and issuance
- [ ] **Sandbox / test merchant credentials** provisioning process
- [ ] Production credentials provisioning process
- [ ] Sandbox base URL
- [ ] Production base URL

### 3.2 Payment Initiation

- [ ] Payment initiation endpoint (full URL/paths for sandbox and production)
- [ ] HTTP method, content type, encoding
- [ ] Required headers
- [ ] Complete request parameter table (required/optional, formats, constraints)
- [ ] **Amount format and unit** (paisa vs rupees; integer vs decimal) — UniServe holds amounts as integer paisa and converts at the provider boundary
- [ ] Currency requirements (is the gateway PKR-only?)
- [ ] Merchant/order reference requirements (format, uniqueness, length, reuse rules)
- [ ] Transaction/reference ID rules (how JazzCash IDs map to merchant references)
- [ ] Supported payment methods for the API gateway (wallet, cards, Raast, voucher, others)
- [ ] Redirect/hosted-checkout URL behavior (how the customer is sent to JazzCash; session lifetime; abandonment behavior)

### 3.3 Authentication / Security

- [ ] Authentication mechanism (credentials vs signature vs both)
- [ ] Request signing mechanism (which fields, canonicalization/ordering, encoding)
- [ ] Hash/signature algorithm (e.g., HMAC-SHA256 — confirm exact algorithm)
- [ ] Secret/key format and where the signing secret is provisioned
- [ ] Required headers for authenticated calls
- [ ] Response verification mechanism (how to verify a response/initiation result is genuine)
- [ ] **Callback/webhook signature verification** (how the merchant proves a callback came from JazzCash — critical)
- [ ] Certificate requirements, if any
- [ ] IP allowlisting requirements, if any (and how to register server IPs)
- [ ] Secret rotation procedure

> Note for checklist use: third-party guides circulate terms such as `pp_MerchantID`, `pp_Amount`, `pp_TxnRefNo`, `pp_SecureHash`, `pp_ResponseURL`, `pp_MPGResponseURL`, `pp_TxnStatus`, hosted redirect at `jazzcashmerchantapi.jazzcash.pk`. **Ask JazzCash to confirm or refute each term explicitly** — these are unverified vocabulary, not the contract.

### 3.4 Callback / Webhook

- [ ] Callback URL requirements (HTTPS? public domain? registration process)
- [ ] Callback HTTP method (POST/GET), content type (form-encoded/JSON)
- [ ] Complete callback payload (every field, type, meaning)
- [ ] Success / failure / pending state representation (status codes and values)
- [ ] Transaction ID field(s) in the callback
- [ ] Merchant/order reference field in the callback
- [ ] Amount and currency fields in the callback
- [ ] Authenticity/signature fields in the callback (and headers, if any)
- [ ] Duplicate callback behavior (can the same event arrive twice?)
- [ ] Retry behavior (does JazzCash retry a failed/timed-out callback? how many times? backoff?)
- [ ] Timeout behavior (how long JazzCash waits for a merchant response)
- [ ] Replay protection (timestamp/expiry guidance)
- [ ] Push webhooks vs merchant response URLs (does JazzCash notify server-to-server independently of the customer redirect?)
- [ ] Callback/domain **whitelisting** process (merchant portal steps)

### 3.5 Transaction Verification (Mandatory)

Independent server-side confirmation is **required by UniServe** before an online order can enter preparation. Client-redirected confirmation alone is not acceptable.

- [ ] Transaction **status inquiry** API (server-to-server lookup by merchant reference and/or transaction ID)
- [ ] Lookup endpoint, method, parameters, response fields
- [ ] Handling of pending transactions (when to re-check; any documented guidance)
- [ ] Handling of failed transactions
- [ ] Handling of successful transactions
- [ ] Amount verification fields (so the merchant can compare the confirmed amount against the server-derived amount)
- [ ] Currency and merchant-reference fields available in the inquiry response
- [ ] Expected latency between customer approval (USSD/MPIN) and status availability

### 3.6 Refund / Reversal

- [ ] Full refund API (endpoint, parameters, response)
- [ ] Partial refund support and API (if available)
- [ ] Reversal support and semantics (vs refund)
- [ ] Refund status lifecycle and inquiry
- [ ] Refund callback/notification (if any) and its authenticity mechanism
- [ ] Refund timing (same-day vs T+N)
- [ ] Refund identifiers (how refund IDs map to original transaction IDs)
- [ ] Refund idempotency rules (repeated requests with the same reference)
- [ ] **Manual refund process** (Business App or portal) if API refunds are unavailable — steps, roles, audit trail

### 3.7 Sandbox

- [ ] Sandbox URL(s)
- [ ] Sandbox credentials / test merchant issuance
- [ ] Test payment methods available (wallet, cards, USSD simulation)
- [ ] Test cards/wallets, if applicable
- [ ] Test scenarios: success, failure, cancellation, timeout, pending
- [ ] Callback testing procedure (how to point sandbox callbacks at a non-public dev endpoint, or test tooling provided)
- [ ] Webhook testing procedure
- [ ] Differences between sandbox and production behavior (amounts, signing, URLs, limits)
- [ ] Sandbox availability duration and refresh process

### 3.8 Commercial & Onboarding (Gateway-Specific)

- [ ] MDR and fee schedule for the API gateway (per the SOC / merchant agreement)
- [ ] Settlement timeline for gateway transactions
- [ ] Contract duration, exit terms, and change-of-terms process
- [ ] Onboarding documents required for gateway access **beyond** the basic JazzCash Business Account
- [ ] Whether a student/university project entity is eligible for gateway access (eligibility is JazzCash's decision — we ask, we do not assume)

---

## 4. Product Identification Questions (Ask Explicitly)

Do **not** assume the JazzCash Business App / Raast QR product is the same product as an API-based online payment gateway. Ask JazzCash to identify:

1. The **correct merchant product** name for API/e-commerce integration.
2. The **product/API name** and version (e.g., gateway product line, merchant API).
3. Whether it supports **website / mobile-app e-commerce** integration.
4. Whether it supports **hosted checkout** (customer redirected to a JazzCash page).
5. Whether it supports **wallet payments** (JazzCash wallet).
6. Whether it supports **card payments**.
7. Whether it supports **QR payments**.
8. Whether it supports **server-to-server status verification** (status inquiry API).
9. Whether it supports **server-to-server authenticated callbacks** (push webhooks) in addition to redirect response URLs.
10. Which of these capabilities are available in a **sandbox before production onboarding**.

---

## 5. Key Architecture Question (Include Verbatim)

The support request must explicitly ask:

> **Does JazzCash currently provide a merchant e-commerce/payment-gateway API that supports server-side payment initiation, authenticated callback/webhook notification, and server-side transaction-status verification?**

And in the same message:

> **Are these capabilities available in a sandbox environment before production onboarding?**

Rationale: the public product pages alone did not establish the technical contract (Phase 26A). A single clear answer to these two questions determines whether UniServe's backend-controlled payment architecture can be satisfied at all.

---

## 6. Version A — Short Support Message

*Suitable for WhatsApp (0325-4444-786), support chat (helplines 8000 / 051-111-118-000), or the website "GET IN TOUCH" contact form. Concise; requests routing to the technical integration team.*

---

**Subject / opener:** JazzCash Payment Gateway — API integration documentation request

Assalam-o-Alaikum / Hello,

I am preparing online payments for **UniServe**, a university cafeteria ordering platform (mobile app for students and faculty, web console for cafeteria staff). We need **PKR payments** through JazzCash for orders placed in the app.

Our system is **backend-controlled**: our server creates the payment, the customer completes payment through JazzCash (hosted checkout or wallet), JazzCash notifies our backend through an **authenticated callback**, and our backend **independently verifies the transaction with JazzCash** before confirming the order. We also need **refund** capability.

Before integrating, we need three things:

1. The **official Payment Gateway API integration manual** (initiation, callback format, signature verification, transaction status inquiry, refunds).
2. **Sandbox/test merchant access** to validate the integration before production.
3. Confirmation of the merchant product that supports **server-side initiation + authenticated callback + server-side status verification** for mobile-app e-commerce.

Could you please route this request to your **merchant onboarding / technical integration team** and share the API documentation pack and sandbox access process?

Thank you.

---

## 7. Version B — Detailed Technical Request

*Suitable for email to the merchant onboarding / technical integration team. Includes the complete checklist.*

---

**Subject:** JazzCash Payment Gateway — Official API Documentation & Sandbox Access Request (UniServe)

Dear JazzCash Merchant Onboarding / Technical Integration Team,

**About us.** UniServe is a university cafeteria ordering platform. Students and faculty order and pay from a mobile app; cafeteria staff and administration manage orders through a web console. We are preparing the platform for production use and need to accept **online PKR payments** through JazzCash. This is a genuine merchant integration request — we are not seeking documentation for academic mirroring, and we are happy to go through your standard onboarding process.

**How our payment architecture works.** Our backend is fully server-controlled:

1. Our **server** creates the payment (amount derived server-side; currency PKR).
2. Our server initiates the payment with JazzCash and receives a hosted-checkout/redirect URL, which our mobile app presents to the customer.
3. The customer completes payment through **JazzCash** (per your documented flow — e.g., mobile number + CNIC verification + USSD/MPIN approval).
4. JazzCash notifies our backend through an **authenticated callback/webhook**; we verify the callback's authenticity before trusting it.
5. Our backend then performs an **independent server-side transaction-status verification** with JazzCash (amount, currency, merchant reference, final status) before marking the payment successful. Only then is the order released for preparation.
6. We additionally require **refund/reversal** capability with documented status tracking.

Because of points 4 and 5, we cannot integrate on redirect-only confirmation; we need your official callback-authenticity mechanism and your status-inquiry API.

**Key questions (please answer explicitly):**

> **Does JazzCash currently provide a merchant e-commerce/payment-gateway API that supports server-side payment initiation, authenticated callback/webhook notification, and server-side transaction-status verification?**

> **Are these capabilities available in a sandbox environment before production onboarding?**

**Product identification (please clarify):** we do not want to assume that the JazzCash Business App / Raast QR product is the same product as your API-based online payment gateway. Please identify: the correct merchant product and API name for e-commerce integration; whether it supports website/mobile-app e-commerce, hosted checkout, wallet payments, card payments, QR payments, server-to-server status verification, and server-to-server authenticated callbacks; and which capabilities are available in sandbox.

**Technical information checklist** (official documentation or written confirmation for each item):

*Merchant / API access:* activation requirements for the API gateway product; required documents (CNIC, NTN/STRN, bank account, business proof, commercial agreement); merchant ID issuance; API credential types; sandbox/test merchant credentials; production credentials; sandbox base URL; production base URL.

*Payment initiation:* initiation endpoint (sandbox + production); HTTP method, content type, encoding; required headers; complete request parameter table (required/optional, formats); **amount format and unit** (paisa vs rupees; integer vs decimal — our system holds integer paisa); currency requirements (PKR-only?); merchant/order reference rules (format, uniqueness, length); transaction/reference ID rules; supported payment methods for the API gateway; redirect/hosted-checkout behavior (session lifetime, abandonment).

*Authentication / security:* authentication mechanism; request signing mechanism (fields, canonicalization, encoding); hash/signature algorithm; secret/key format and provisioning; required headers; response verification; **callback signature verification**; certificate requirements, if any; IP allowlisting, if any; secret rotation procedure.

*Callback / webhook:* callback URL requirements (HTTPS/public domain/registration); HTTP method and content type; complete payload field list; success/failure/pending state values; transaction ID field; merchant reference field; amount/currency fields; authenticity/signature fields; duplicate callback behavior; retry behavior and backoff; timeout behavior; replay protection guidance; push webhooks vs redirect response URLs; callback/domain whitelisting process.

*Transaction verification (mandatory for us):* status-inquiry API (endpoint, method, parameters, response fields incl. amount, currency, merchant reference, final status); pending/failed/successful transaction handling; expected latency between customer approval and status availability.

*Refund / reversal:* full refund API; partial refund (if supported); reversal semantics; refund status lifecycle and inquiry; refund callbacks (and their authenticity); refund timing; refund identifiers; refund idempotency; **manual refund process** (portal/app steps) if API refunds are unavailable.

*Sandbox:* sandbox URLs; test merchant credentials; test payment methods; test success/failure/cancellation/timeout/pending scenarios; callback/webhook testing procedure; sandbox-vs-production differences; sandbox duration/refresh.

*Commercial & onboarding:* MDR/fee schedule for the API gateway; settlement timeline; contract duration and exit terms; onboarding documents required for gateway access **beyond** the basic business account; eligibility of a university student project for gateway access.

**Sandbox before production.** We intend to validate the full integration — initiation, authenticated callback, independent status verification, and refunds — in your sandbox environment before any production onboarding. We ask that the sandbox access process be included in your response.

Please share the official API integration manual (or point us to the correct documentation channel) and the sandbox provisioning steps. We are glad to complete any merchant onboarding forms you require.

Thank you for your time.

Best regards,
UniServe project team

---

## 8. External Response Procedure

What we will do once JazzCash responds — **in this order, no skipping**:

```text
JazzCash response
        ↓
official documentation received
        ↓
verify API contract
        ↓
verify sandbox access
        ↓
map API to PaymentProvider
        ↓
implement provider adapter
        ↓
sandbox integration tests
        ↓
security/replay/idempotency tests
        ↓
mobile payment-flow testing
        ↓
production approval
```

**Gating rules:**

- The response and documentation pack are archived as the **contract of record** in the repo (new phase, documentation-only).
- **No production activation occurs before sandbox validation** completes (Phase 26A §18 prerequisites all satisfied).
- If JazzCash confirms the API exists → a future implementation phase proceeds strictly against the official spec (Phase 26A §20 steps 1–8).
- If JazzCash confirms **no** server-to-server API / no sandbox / no status verification → the finding is **recorded explicitly**; any change of strategy (including considering another provider) requires its own explicit phase and decision — never a silent substitution.
- If no response arrives → the blocker stands; nothing changes in code.
- **We do not assume JazzCash has provided anything unless an actual official response/documentation has been supplied.**

---

## 9. Evidence Summary (From Phase 26A)

Sources already checked (all official, 2026-10-01) — full log in `PHASE_26_JAZZCASH_READINESS.md` §4:

- Payment Gateway product page — **retrieved** (hosted-checkout UX flow, payment methods, sales-form-only channel).
- Business onboarding pages — **retrieved** (Business App digital flow; CNIC eligibility; Raast QR activation end-point; no API credential narrative).
- `/business/accept-payments/qr-raast-payments` — **retrieved** (Raast QR product facts).
- `/tc` — **retrieved** (consumer wallet terms only; no merchant API terms).
- `jazzcash.com.pk/developer-portal/` — **404**; `developerportal.`, `developer.`, `merchants.jazzcash.com.pk`, `jazzcashmerchantapi.jazzcash.pk` — **unreachable/unextractable**; SOC PDF — **not machine-readable**; rendered gateway page — **zero documentation links**.

Official contact channels identified: "GET IN TOUCH" form on the gateway page; WhatsApp 0325-4444-786; helplines 8000 / 051-111-118-000; Contact Us page on jazzcash.com.pk.

---

## 10. Phase Constraints & Validation

- Application code, endpoints, payment service, mobile checkout, `.env`, Docker, Caddy, deployment, and payment state machine: **untouched**.
- Credentials: **none created**. Provider registry: **unchanged** (test only). Production guard: **unchanged**.
- Validation performed at phase end: `git diff --check` and `git status --short` — expect only `?? PHASE_26B_JAZZCASH_TECHNICAL_REQUEST.md` before commit.
- Single commit: `docs: prepare JazzCash technical access request`.
- **STOP after this phase.** Do not implement JazzCash, do not select another provider, and do not treat any unsupplied material as an official JazzCash response.
