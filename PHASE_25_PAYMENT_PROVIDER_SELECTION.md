# Phase 25 — Real Payment Provider Selection & Implementation Specification

**Status:** PASS — SPECIFICATION COMPLETE (documentation-only phase; no provider selected)
**Date:** 2026-10-01 · **Baseline:** `d3a8a37` `feat: prepare online payment provider integration` (tree clean)
**Scope:** Provider research, evidence-graded comparison, and a concrete Phase 26 implementation specification. **No provider was chosen** — selection is an explicit project-owner decision. No code changed, no credentials requested or stored, nothing deployed.

---

## 1. Executive Summary

UniServe's payment backend is complete and provider-neutral (Phase 24): a `PaymentProvider` ABC, server-authoritative amounts, signature-first webhook verification keyed on the verified event ID, idempotent processing, a fail-closed provider factory, and a hard production guard — production returns HTTP 503 until a **real** provider is registered. Online payments therefore cannot go live until (a) a provider is selected, (b) its merchant account + credentials exist, and (c) its adapter is implemented (Phase 26).

This phase researched currently available Pakistani online-payment options against UniServe's exact requirements (PKR, Pakistani customers, mobile ordering, backend-side initiation, secure webhook + signature verification, idempotency, server-authoritative amount, status confirmation, refunds, sandbox, mobile redirect/deep-link, merchant onboarding) using official provider sources wherever reachable. The dominant finding: **no candidate exposes fully public, machine-retrievable API/webhook documentation from this environment** — the two operating Pakistani gateways (JazzCash, Easypaisa) document their *products* publicly but gate technical API details behind merchant onboarding; PayFast's developer site exists but is a JavaScript app that could not be read here; Safepay is officially offline. Consequently the matrix is deliberately heavy on `UNCLEAR — verify with provider`, and the Phase 26 plan begins with obtaining official API documentation for the chosen provider.

---

## 2. Provider Candidates (Official Evidence, Accessed 2026-10-01)

### 2.1 JazzCash (JazzCash — Mobile Account / Jazz)
- **Official page retrieved:** `jazzcash.com.pk/business/accept-payments/payment-gateway`
- **Documented products:** Hosted **Payment Gateway** for online/app checkout — customer selects JazzCash at merchant checkout, enters mobile number (+ CNIC last-6 optional), approves via **MPIN prompt (USSD/app)**, receives real-time confirmation; **Voucher** payment (12-digit SMS voucher); **Raast QR** (interoperable — pay from any participating bank app/wallet, real-time settlement to merchant wallet); **Tap on Phone** (NFC card acceptance, no POS hardware). Marketed as "5+ Payment Methods Supported", "Real-time payment confirmation".
- **Onboarding evidence:** Business merchant registration offered digitally via the JazzCash Business app (official page image/alt text); "Register your account" business flow exists on-site.
- **Fees:** Official "Schedule of Charges" page hosts `SOC-Q3-2026-Final.pdf` (dated 01 July 2026); Payment Gateway FAQ states "MDR may apply as per agreement", fees "disclosed within the app" → gateway rates are **NOT PUBLICLY SPECIFIED** in HTML sources.
- **Technical API:** **No public developer portal linked.** Initiation API, webhook/callback contract, signature scheme, sandbox/test credentials, refund API → **UNCLEAR — verify with provider** (industry-typical: provided post-onboarding; must be confirmed, not assumed).

### 2.2 Easypaisa (Easypaisa Bank Ltd — Telenor Microfinance Bank successor)
- **Official pages retrieved:** `easypaisa.com.pk/business`, `easypaisa.com.pk/merchant/`, `easypaisa.com.pk/schedule-of-charges/`
- **Documented products:** **Easypaisa Merchant** — "sign up for **instant QR onboarding** and join Pakistan's most trusted cashless payment network" (merchant QR acceptance); corporate account + e-banking portal for businesses; retailer network. Consumer side: wallet transfers, bill payments, Raast merchant payments.
- **Onboarding evidence:** QR merchant onboarding is documented as instant/digital; **online e-commerce payment-gateway onboarding** is not documented on the retrieved pages → UNCLEAR.
- **Fees:** Official Schedule of Charges PDFs exist (Branchless Banking + Retail Banking, EN/UR); e-commerce/merchant gateway rates are not stated in HTML → **NOT PUBLICLY SPECIFIED** (verify PDFs/provider).
- **Technical API:** **No public developer portal found** on official site. API/webhook/signature/sandbox/refund details → **UNCLEAR — verify with provider**.

### 2.3 PayFast
- **Official site:** `payfast.pk` resolves but is a JavaScript-rendered application; `/developers/`, `/docs/README.md`, `developer.payfast.pk`, and archive.org snapshots were all unreachable or unextractable from this environment (access attempts 2026-10-01).
- **Evidence status:** No official technical content retrievable → **every technical row = UNCLEAR**. PayFast is known in-market as a Pakistani PSP serving online merchants with published developer documentation, but per the evidence rule of this phase that claim **cannot be graded YES here** — it must be verified directly (`payfast.pk/developers`) before any selection.

### 2.4 Safepay — **RULED OUT (not available)**
- **Official site** `www.gosafepay.com` returned: *"We're under construction. Please check back for an update soon."* (retrieved 2026-10-01). `docs.gosafepay.com` is DNS-unresolvable. **Conclusion: Safepay is not currently a viable integration target** based on its own official site state.

### 2.5 NayaPay — **No evidenced merchant gateway API**
- **Official site retrieved:** consumer EMI wallet (SBP-authorised; PCI-DSS + ISO 27001 certified; Visa cards; pays at Raast/Alipay+ merchants as a *consumer*). **No public merchant payment-gateway or developer documentation** found → merchant API integration **UNCLEAR / not evidenced**.

### 2.6 SadaPay — **Not evidenced from official sources**
- `sadepay.com` and `/business/` were JavaScript-blocked/unextractable from this environment (2026-10-01). Business-account products may exist but **no official technical evidence retrievable** → all rows UNCLEAR; not a serious candidate until documentation is obtainable.

### 2.7 1LINK — **Not a direct merchant gateway (and unreachable here)**
- `1link.com.pk` was DNS-unresolvable from this environment on both HTTP and HTTPS (2026-10-01). General market structure ( **not** official-doc evidence, recorded for context only): 1LINK operates shared rails (1Bill, 1QR, PayPak, IBFT) consumed **through member banks** — an app like UniServe would obtain acquiring via a bank, not via a direct 1LINK merchant API. No public merchant API evidence → UNCLEAR; likely out of scope as a *direct* integration.

### 2.8 Other options considered and not evidenced
- Bank gateways (HBL PayPro, UBL, Meezan, Alfalah, etc.): official sites unreachable or JS-blocked from this environment; no retrievable public API docs → UNCLEAR, not graded.
- Global providers (Stripe et al.): **not evidenced as available for a Pakistan-domiciled merchant**; Stripe remains only a commented placeholder in the repo with PKR support unverified (Phase 24). Out of scope until official availability for PK is confirmed.

---

## 3. Comparison Matrix (YES / NO / UNCLEAR — official documentation only)

Legend: ✅ YES (official evidence) · ❌ NO (official evidence) · ❓ UNCLEAR (no official evidence retrievable — verify with provider) · 🚫 N/A (ruled out)

| Requirement | JazzCash | Easypaisa | PayFast | Safepay | NayaPay |
|---|---|---|---|---|---|
| Pakistan merchant support | ✅ (business merchant program) | ✅ (merchant program) | ❓ | 🚫 offline | ❓ (no merchant gateway evidenced) |
| PKR | ✅ (PK mobile money; SBP-regulated) | ✅ (PK digital bank) | ❓ | 🚫 | ✅ (PK wallet, SBP-regulated) |
| Online card payments (customer-side) | ✅ (gateway "5+ payment methods", voucher, hosted flow) | ❓ (QR-focused public evidence) | ❓ | 🚫 | ✅ (Visa cards — consumer) |
| Mobile wallet payments | ✅ (JazzCash wallet core) | ✅ (Easypaisa wallet core) | ❓ | 🚫 | ✅ |
| Server-side API | ❓ (not public) | ❓ (not public) | ❓ (docs not retrievable) | 🚫 | ❓ |
| Payment initiation (API) | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Webhook/callback | ❓ (real-time confirmation marketed; contract not public) | ❓ | ❓ | 🚫 | ❓ |
| Signature verification | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Idempotency support | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Transaction/reference ID | ❓ (txn IDs exist in wallet domain; API exposure unclear) | ❓ | ❓ | 🚫 | ❓ |
| Refund API | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Sandbox/test environment | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Production API access | ❓ (post-onboarding) | ❓ | ❓ | 🚫 | ❓ |
| Merchant onboarding | ✅ (digital business registration via app) | ✅ (instant QR onboarding; gateway onboarding ❓) | ❓ | 🚫 | ✅ (wallet onboarding; merchant ❓) |
| Public API documentation | ❌ (none linked publicly) | ❌ (none linked publicly) | ❓ (exists per market knowledge; unreadable here) | 🚫 | ❌ (none found) |
| Mobile redirect/deep-link flow | ✅ (hosted checkout + USSD/app MPIN approval flow documented) | ❓ (QR is scan-based; online flow unclear) | ❓ | 🚫 | ❓ |
| Webhook retry behavior | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Test credentials/process | ❓ | ❓ | ❓ | 🚫 | ❓ |
| Fees public? | ❌ (SOC PDF exists; MDR "per agreement") | ❌ (SOC PDFs exist; gateway rates silent) | ❓ | 🚫 | ❌ (consumer "no fees"; merchant rates unknown) |

**Reading of the matrix:** No candidate can be graded on the security-critical rows (signature, idempotency, refund, sandbox) from public sources today. This is a property of the Pakistani market's documentation practice, not of UniServe. The matrix therefore ranks nothing; it identifies **which providers have evidenced operating payment products** (JazzCash, Easypaisa) versus **which are unavailable** (Safepay) versus **which are unverifiable from here** (PayFast, 1LINK, SadaPay, bank gateways).

---

## 4. UniServe Compatibility — Mapping to the Actual Code

UniServe contract (verified against `apps/api/app/modules/payments/` at `d3a8a37`):

| UniServe component | Contract any provider must satisfy | Compatibility note |
|---|---|---|
| `PaymentProvider.name` | Unique registry key (`PROVIDER_REGISTRY` in `providers/__init__.py`; selection via `PAYMENT_PROVIDER`, fail-closed 503) | Trivial for any provider — one registry entry. |
| `initiate_payment(payment_id, order_id, amount, currency, idempotency_key, metadata) → PaymentInitiationResult` | Server passes **amount in smallest unit (paisa, int)** + `currency="PKR"`; must return `success`, `provider_reference` (unique txn id), `redirect_url` (hosted page or app-prompt URL if any), `provider_metadata` | Hosted-checkout providers (JazzCash-style) map naturally: `redirect_url` = hosted payment page; wallet-app-prompt flows may return no URL — adapter returns `redirect_url=None` and mobile relies on polling + push. **Adapter must convert paisa→rupees at the provider boundary** (provider APIs conventionally take PKR rupees); conversion stays inside the adapter — server-authoritative amount is preserved end-to-end. |
| `verify_payment(provider_reference, payment_id) → PaymentVerificationResult` | Server-side status query by provider txn id | **Currently unused by `PaymentService`** (no call site) — Phase 26 must add a reconciliation poller for stuck `PROCESSING` payments and as fallback when a provider is poll-confirmed rather than webhook-confirmed. |
| `verify_webhook_signature(payload, headers) → WebhookVerificationResult` | Must return `valid`, **verified** `event_id`, `event_type`, `payment_reference`, `amount`, `currency`, `metadata` | Adapter implements the provider's signature scheme (HMAC/hash per official docs — details TBD post-onboarding). Phase 24 already enforces verify-first + verified-event-id idempotency in `PaymentService.process_webhook`. ⚠ Integration note: today the router passes `headers={"provider": provider_name}` only — Phase 26 will pass the **real request headers** through (minimal, provider-justified change). |
| `process_refund(...) → RefundResult` + `RefundProcessor.create_refund/verify_refund` | Refund by provider txn id; return refund txn id + status | Parallel boundary (`modules/refunds/processors/base.py`) maps 1:1 to provider refund APIs; `PARTIALLY_REFUNDED` state already exists for partial refunds. Provider refund capability **UNCLEAR for all candidates** — if unavailable, refund flow stays manual (documented limitation) and `process_refund` returns a clear failure. |
| `PaymentService.initiate_online_payment` | Ownership, `PaymentMethod.ONLINE`, order PENDING, no existing SUCCEEDED payment, **amount = order.total_amount server-side**, idempotency-key dedupe | Provider-agnostic — unchanged by any selection. |
| `PaymentService.process_webhook` | Signature-first; dedupe on **verified** event id; amount/currency re-validated against the order; success ⇒ `PAYMENT_CONFIRMED` event + notification | Any provider's webhook payload is normalized inside the adapter into `WebhookVerificationResult`; service logic untouched. |
| Payment router (`/initiate/{order_id}`, `/webhook/{provider_name}`, owner-only reads) | Generic endpoints; production + mock ⇒ 503 | No change needed; webhook path becomes live once a real provider is registered and `PAYMENT_CALLBACK_URL` is publicly reachable (deployment phase). |
| Order prepare gate | Online orders require `PaymentStatus.SUCCEEDED` | Provider-agnostic — enforced server-side regardless of provider. |
| Mobile `checkout.tsx` / `order/[id].tsx` | Calls `initiatePayment`; consumes `redirect_url` (**currently unused**); polls payment 15 s on order screen | Phase 26 adds: open `redirect_url` in an in-app browser (`expo-web-browser`) when present, deep-link/return handling, and relies on polling + `PAYMENT_CONFIRMED` push when the provider uses app-prompts instead of redirects. |
| Web console | No payment surface (admin/manager/staff) | Nothing to do. |

**Conclusion:** The existing abstraction is **sufficient for every candidate class** (hosted redirect, app-prompt, or poll-confirmed). No architectural change is required; Phase 26 work is: adapter + registry entry + real header pass-through + reconciliation poller + mobile redirect handling.

---

## 5. Security Analysis (UniServe Model Preserved for Any Provider)

| Control | UniServe enforcement (already implemented) | Provider-dependent input (Phase 26 verify) |
|---|---|---|
| **Amount** | Never client-supplied — `Payment.amount = order.total_amount` (paisa int) at initiation; webhook path re-validates `result.amount == order.total_amount` before success | Provider must accept a merchant-specified amount (all evidenced hosted gateways do) and report the paid amount in callbacks/status queries |
| **Currency** | `PKR` enforced in models; webhook re-validates currency | Provider settles/quotes in PKR (✅ evidenced for JazzCash/Easypaisa wallets; ❓ others) |
| **Signature** | `verify_webhook_signature` is abstract; **service verifies signature FIRST**, before any dedupe or state change | Provider must document an authenticity mechanism (signed payload, HMAC, IP allowlist, or query-hash) — **details UNCLEAR for all candidates until official docs are obtained** |
| **Replay** | Webhook dedupe keyed on **verified** payload event ID (Phase 24 fix); provider txn reference unique index in DB; amount re-checked | Provider must expose a unique event/txn id (❓ all candidates) |
| **Idempotency** | Unique `idempotency_key` on Payment; duplicate webhook ⇒ `ignored`; `handle_payment_success` idempotent on SUCCEEDED | Provider initiation idempotency support (❓) is a convenience, not a requirement — UniServe dedupes locally regardless |
| **Secrets** | `PAYMENT_*` backend-only env; never committed; `reject_default_secrets` validator; **zero** payment secrets in web/mobile configs (verified Phase 24) | Merchant credentials + webhook secret stored only in server env (Phase 26) |
| **Client exposure** | Mobile app only ever sees `payment_id/status/redirect_url/message` (`PaymentInitiationResponse`); webhook route is signature-authenticated, not token-authenticated | Provider must not require any secret in the mobile app — hosted flows satisfy this natively |
| **Independent verification** | Order marked paid **only** after webhook signature passes **or** (Phase 26) a reconciliation poll via `verify_payment` returns verified success with matching amount/currency | Provider must offer a server-side status query by txn id (❓ for all candidates — confirm in official docs) |
| **Fail-closed** | Unknown `PAYMENT_PROVIDER` ⇒ 503; production + mock ⇒ 503 (Phase 23 guard retained) | Unchanged by any selection |

**Non-negotiable for Phase 26 regardless of provider:** if official docs cannot demonstrate (a) server-side verification and (b) an authenticity mechanism for callbacks, that provider **cannot** be enabled for production — polling-only confirmation is acceptable only via `verify_payment` reconciliation, never via client claims.

---

## 6. Mobile UX Flow (Expected Implementation — No SDK, No Architecture Change)

Per candidate flow class:

1. **Hosted checkout (redirect) — JazzCash-class:** backend `initiate_payment` returns `redirect_url` → mobile opens it with `expo-web-browser` (`openAuthSessionAsync`/`openBrowserAsync`) → user completes payment on provider page (JazzCash number + MPIN/USSD approval per official "How It Works") → provider redirects back to `PAYMENT_CALLBACK_URL` (user-visible return URL) or simply closes → app polls `getOrderPayment` (existing 15 s poller) and/or receives `PAYMENT_CONFIRMED` push → order screen transitions on `SUCCEEDED`. Deep-link return (custom scheme/universal link) is the clean completion path; until configured, polling alone already completes the UX safely.
2. **App-prompt / USSD flow:** no browser needed — user approves in their wallet app; mobile relies on polling + push; `redirect_url=None`.
3. **QR flow (Raast/Easypaisa QR):** not suitable for pure online checkout (user must scan a merchant QR); relevant only if UniServe later adds counter pickup payments. **Out of scope for online checkout.**

Constraints honored: no provider SDK added to Expo now; no Expo architecture change; the existing poller + typed `initiatePayment` response (`redirect_url?` already modeled in `data.ts`) already cover the contract.

---

## 7. Refund Requirements vs. `RefundProcessor`

- UniServe boundary: `RefundProcessor.create_refund(refund_id, payment_provider_reference, amount, currency, idempotency_key, reason) → RefundProcessingResult{success, provider_reference, provider_metadata, error_message}` and `verify_refund(provider_reference)`; service transitions `REFUND_PENDING → REFUNDED / PARTIALLY_REFUNDED / FAILED`; `REFUND_DEADLINE_HOURS=72`.
- **This boundary is directly compatible with any provider refund API** returning a refund txn id + final status (full or partial). No redesign needed.
- Provider-side refund capability is **UNCLEAR for every candidate** from public sources (JazzCash/Easypaisa pages document acceptance, not refunds; PayFast unreadable). Phase 26 must confirm refund API + whether refund callbacks exist; if a provider offers no API refunds, UniServe keeps refunds manual/back-office and `process_refund` fails explicitly — orders still gate correctly (a refunded payment cannot un-hold an already-prepared order; that is an operational policy question for the owner).

---

## 8. Merchant Onboarding Requirements (Officially Documented vs. UNCLEAR)

| Candidate | Officially documented | UNCLEAR — verify with provider |
|---|---|---|
| JazzCash | Business merchant registration (digital, via JazzCash Business app); helpline/UAN for business; SBP-regulated wallet; Schedule of Charges published | NTN/STRN, bank-account, CNIC, business-registration document lists; callback/domain whitelisting; sandbox issuance; production approval timeline; API credential issuance |
| Easypaisa | Merchant program with **instant QR onboarding**; corporate account + e-banking portal; official SOC PDFs | Whether an **online e-commerce gateway** (vs QR-only) is offered directly; API credential process; callback/domain requirements; sandbox; approval timeline |
| PayFast | (nothing retrievable) — all items UNCLEAR | Everything: onboarding docs, KYC list, sandbox process, fees |
| NayaPay | Consumer wallet onboarding; SBP-regulated | Any merchant gateway program at all |
| Safepay | 🚫 unavailable (official site under construction) | — |

**Do not guess legal requirements.** Typical Pakistani merchant KYC (business registration, NTN/STRN, bank mandate, CNIC of directors) is *common knowledge* but is deliberately **not asserted as a requirement** of any specific provider here — each must be confirmed from the provider's own onboarding pack.

---

## 9. Pricing / Fees

| Candidate | Official evidence | Grade |
|---|---|---|
| JazzCash | Schedule of Charges PDF published (`SOC-Q3-2026-Final.pdf`, 01 Jul 2026); gateway MDR "may apply as per agreement"; app-disclosed | **NOT PUBLICLY SPECIFIED** for the Payment Gateway MDR (PDF exists — read it during onboarding) |
| Easypaisa | SOC PDFs (Branchless Banking / Retail Banking) published; e-commerce merchant rates absent from HTML | **NOT PUBLICLY SPECIFIED** (verify PDFs/provider) |
| PayFast | Nothing retrievable | **NOT PUBLICLY SPECIFIED** |
| NayaPay | Consumer "no fees" positioning; merchant rates unknown | **NOT PUBLICLY SPECIFIED** (merchant program itself unevidenced) |

No fee estimates are made anywhere in this document; providers are **not** ranked on price.

---

## 10. Selection Framework (Trade-offs Made Explicit — Decision Remains with the Owner)

### Candidate A — JazzCash
**Documented strengths relevant to UniServe:** Operating hosted **online Payment Gateway** with an official "How It Works" flow that matches UniServe's redirect design (checkout → wallet number → MPIN/USSD approval → real-time confirmation); broad PK mobile-money reach; Raast QR interoperability (future counter payments); digital merchant onboarding; SBP-regulated; strong student/faculty demographics fit (wallet-first).
**Technical fit:** High *if* API docs (post-onboarding) provide initiation + signed callbacks + status query; all such details currently ❓.
**Onboarding requirements:** Business merchant registration via app (✅ documented); full KYC list ❓.
**Missing information:** API spec, webhook signature scheme, sandbox, refund API, callback whitelisting, MDR.
**Risks:** Docs-gated integration (can't prototype against real API before onboarding); fees opaque; USSD-prompt UX depends on user's phone state (official FAQ acknowledges MPIN prompt requires unlocked phone).
**Open questions:** Sandbox availability? Webhook vs. query confirmation? Raast QR for online orders?

### Candidate B — Easypaisa
**Documented strengths relevant to UniServe:** Massive PK wallet base; **instant QR merchant onboarding**; digital-bank infrastructure (e-banking portal, SOC transparency); SBP-regulated; natural fit for wallet-dominant student users.
**Technical fit:** Unknown — public evidence shows **QR acceptance**, not an e-commerce API gateway. If only QR/POS acquiring is offered directly, it fits **counter** payments but not UniServe's server-initiated online checkout.
**Onboarding requirements:** QR onboarding ✅; online-gateway onboarding ❓.
**Missing information:** Existence and terms of a hosted/online gateway product; API; sandbox; refunds; callbacks.
**Risks:** Selecting a QR-only program would not satisfy "backend/server-side payment initiation + webhook" requirements.
**Open questions:** Does Easypaisa directly offer an e-commerce payment gateway with API + callbacks for merchants like UniServe, and via which entity/partner?

### Candidate C — PayFast
**Documented strengths relevant to UniServe (as known in-market, NOT verified here):** Positioned as an online-merchant PSP with a developer portal; if verified, could offer the most conventional gateway integration (cards + wallets, hosted checkout, webhooks, sandbox) — the shape UniServe's ABC was designed for.
**Technical fit:** Unknown until official docs are read directly (this environment could not render them).
**Onboarding requirements:** UNCLEAR — verify with provider.
**Missing information:** Everything technical — documentation access is the gating step.
**Risks:** Selecting on reputation alone would violate this phase's evidence rules; the provider's current status, PKR settlement, and SBP licensing posture must be confirmed officially.
**Open questions:** Is `payfast.pk/developers` current and accessible to the owner? What are sandbox and refund capabilities?

### Cross-cutting
- **TECHNICAL FIT:** All three *could* fit the existing ABC (hosted-redirect or poll-confirmed); none can be *proven* to fit until official API docs are in hand.
- **ONBOARDING REQUIREMENTS:** Only JazzCash (business registration) and Easypaisa (QR onboarding) have any official onboarding evidence; both are incomplete for an API gateway.
- **MISSING INFORMATION:** Official API documentation (all), webhook signature schemes (all), sandbox access (all), refund APIs (all), MDR (all).
- **RISKS:** Doc-gated development; QR-only dead-ends; USSD/app-prompt UX variance; callback URL requires a deployed public endpoint (out of scope until deployment phase).
- **OPEN QUESTIONS:** Collected in §11.

**No provider is selected here.** The owner should choose based on: (1) which provider's *official* API documentation is actually obtainable, (2) which offers hosted checkout + signed callbacks + server-side status query, (3) onboarding effort vs. timeline, (4) MDR once disclosed. A defensible default shortlist is **JazzCash or Easypaisa (evidenced operating products, PKR-native) with PayFast as a verification-pending alternative** — but this is explicitly **not** a decision.

---

## 11. Open Questions (Cannot Be Verified from Public Documentation)

1. **JazzCash:** Merchant API spec (initiation, callbacks, signature), sandbox/test credentials, refund API, callback/domain whitelisting, MDR, production approval process.
2. **Easypaisa:** Does a direct e-commerce gateway (API + webhook) exist for merchants, or is the offering QR-centric? Entity/partner for online acquiring; API; sandbox; refunds.
3. **PayFast:** Current accessibility of official developer docs; licensing/SBP posture for the owner's entity; PKR settlement; sandbox; refund API; webhook signing.
4. **All:** Webhook retry/backoff behavior; event ID uniqueness guarantees; timestamp/replay windows; settlement timelines; chargeback handling.
5. **UniServe-side (owner decision):** Which provider; who owns the merchant account; where the production API will be deployed so `PAYMENT_CALLBACK_URL` is publicly reachable (deployment phase, out of scope now); refund operational policy within the 72-hour window.

---

## 12. Phase 26 Implementation Plan (Provider-Agnostic Sequence — Execute Only After Selection)

```
 1. Obtain official API documentation + sandbox credentials for the SELECTED
    provider (merchant onboarding). Verify: initiation API, amount/currency
    semantics (paisa→rupees conversion), callback/webhook contract, signature
    scheme, event/txn ID semantics, status-query API, refund API, retry behavior.
 2. Configure backend-only PAYMENT_* env (PAYMENT_PROVIDER=<registry key>,
    PAYMENT_ENVIRONMENT=sandbox, credentials blank-committed as placeholders —
    real values live only on the server). Secrets never touch frontend/mobile.
 3. Implement provider adapter: class in
    apps/api/app/modules/payments/providers/<provider>.py implementing
    PaymentProvider (name, initiate_payment, verify_payment,
    verify_webhook_signature incl. constant-time signature check per official
    spec, process_refund). All provider-specific parsing lives here.
 4. Register in PROVIDER_REGISTRY (providers/__init__.py) — fail-closed
    factory already rejects unregistered names.
 5. Minimal router change (provider-justified): pass the real request headers
    into verify_webhook_signature (today only {"provider": name} is passed).
 6. Implement initiation wiring (already generic): hosted-flow providers return
    redirect_url; app-prompt providers return None. Server-derived amount
    passes through unchanged.
 7. Mobile redirect handling: open redirect_url via expo-web-browser on
    checkout; optional deep-link return scheme; existing 15s payment poller +
    PAYMENT_CONFIRMED push complete the state transition. No provider SDK.
 8. Implement webhook verification end-to-end: signature → verified event id →
    (existing Phase 24 idempotency) → amount/currency re-validation →
    SUCCEEDED. Add tamper/replay/duplicate tests against the provider's real
    signature format.
 9. Implement reconciliation poller (new): periodic job calling verify_payment
    for stale PROCESSING/PENDING payments; fixes webhook-loss and supports
    poll-confirmed providers; transition via the same idempotent success path.
10. Implement refunds: provider adapter process_refund + RefundProcessor
    implementation if the provider exposes refunds; else fail explicitly and
    document manual process.
11. Sandbox E2E (scripts + live_verify pattern): initiate → provider sandbox
    → callback → SUCCEEDED → prepare gate opens → refund path; verify
    duplicate webhook ignored, tampered signature rejected, amount mismatch
    rejected, cancellation path, app-closed-mid-payment recovery via poll.
12. Full regression: backend pytest, 31/31 E2E, web tsc+build, mobile tsc
    (existing gates — nothing weakened).
13. Production enablement ONLY after sandbox passes: production credentials,
    PAYMENT_PROVIDER switched from mock, callback URL registered with provider,
    503 guard satisfied by the real registry entry, monitor first live
    transactions. Deployment/DNS/HTTPS remain a separate, explicit phase.
```

---

## 13. Evidence & Access Log (Auditability)

| Source | URL | Result (2026-10-01) |
|---|---|---|
| JazzCash Payment Gateway | `jazzcash.com.pk/business/accept-payments/payment-gateway` | ✅ Retrieved (full marketing + flow + FAQ) |
| JazzCash Schedule of Charges | `jazzcash.com.pk/schedule-of-charges` | ✅ Retrieved (PDF `SOC-Q3-2026-Final.pdf` linked, 01 Jul 2026) |
| Easypaisa Business / Merchant / SOC | `easypaisa.com.pk/business`, `/merchant/`, `/schedule-of-charges/` | ✅ Retrieved (QR onboarding; SOC PDFs linked) |
| Safepay | `gosafepay.com` / `docs.gosafepay.com` | ✅ Retrieved: "under construction"; docs DNS-dead → ruled out |
| NayaPay | `nayapay.com` | ✅ Retrieved (consumer wallet; no merchant API) |
| PayFast | `payfast.pk/developers/`, `developer.payfast.pk`, archive.org | ❌ JS-app/unextractable/rate-limited — no official content obtained |
| 1LINK | `1link.com.pk` (HTTP+HTTPS) | ❌ DNS-unresolvable from environment |
| SadaPay | `sadepay.com`, `/business/` | ❌ JS-blocked/unextractable |
| Wayback availability API | `archive.org/wayback/available` | ❌ Too Many Requests |

Method: official provider domains only; no blogs/tutorials/random repos used for grading. Where official content was unreachable, rows are `UNCLEAR — verify with provider` — never inferred.

---

## 14. Scope Compliance

- ✅ Documentation-only phase; **zero code changes** (git clean except this report).
- ✅ No provider selected on behalf of the owner; no credentials requested or stored; nothing deployed; no VPS/DNS/HTTPS work; no fake provider; no claims of production readiness; no unrelated features touched.
- ✅ Existing architecture left untouched — Phase 24's provider-neutral boundary is confirmed sufficient for all candidate classes; the one future integration note (real header pass-through) is specified for Phase 26, not implemented now.

*Next step: the project owner reads §10–§11, selects a provider (or rejects all pending better documentation), and authorizes Phase 26.*
