# Phase 22 — Product Readiness Gap Matrix

**Date:** 2026-10-01
**Audited from:** Phase 21 acceptance report (`ORDER_WORKFLOW_ACCEPTANCE_REPORT.md`), commit `3419308`
**Decision basis:** Original UniServe requirements in-repo — `docs/architecture/phases.md`, `docs/decisions/001-technology-stack.md` (ADR-001), `docs/architecture/overview.md`, `docs/UI_MOBILE_REDESIGN.md` — plus implementation evidence from the payments, notifications, and orders modules.

**Rules applied:** No new product requirements invented. No redesign. Two-surface model preserved (Web = admin/manager/staff, Mobile = student/faculty). Backend RBAC unchanged.

---

## Matrix

| Gap | Original Requirement? | Current Implementation | Evidence | Required Action | Priority |
|-----|----------------------|------------------------|----------|-----------------|----------|
| Notifications screen (mobile inbox) | **No** — a dedicated mobile notification inbox was explicitly deferred. `docs/UI_MOBILE_REDESIGN.md` §6.2 states "Notification icon navigates to notifications (future slice)"; §18 Non-Goals lists "Push notifications — Future slice". The Phase 6 spec deliverable was "Order status push notifications" (native push), which ADR-001 lists under deferred future decisions. The in-app notification system (database + API) was the implementable portion and **is complete**. | Backend: full notification module — models, `NotificationService`, 4 API endpoints, fire-and-forget emission from 17 order/payment/refund integration points; 64 unit tests + 15 live-verification checks pass. Web: `/dashboard/notifications` inbox renders correctly. Mobile: API clients exist (`getNotifications`, `getUnreadNotificationCount` in `src/services/data.ts`) but no screen consumes them; the header bell was decorative (now a profile icon after the UI refinement, commit `5d519ff`). Native push: not implemented on any surface — external provider/credentials required and explicitly deferred. | `EVIDENCE_NOTIFICATIONS.md` (64/64 tests, 15/15 live checks, migration `0008`); `apps/api/app/modules/notifications/`; `docs/UI_MOBILE_REDESIGN.md` §6.2/§18; ADR-001 "Future Decisions (Deferred)" | **KEEP AS-IS** + **DOCUMENT LIMITATION** — intentionally deferred per spec; backend + web inbox satisfy the in-app notification requirement. Native push remains an external-dependency item. | Not required — explicit deferral |
| Online payment / "Pay Now" button | **Partially** — "Online payment gateway integration" is a Phase 5 deliverable and **is implemented** as architecture. A "Pay Now" retry button on order detail is **not** an explicit spec requirement; the specified flow (initiate at checkout → provider confirmation → staff prepare gated on payment success) exists end-to-end. Real provider integration is listed in `PRODUCTION_INTEGRATION_AUDIT.md` as OPTIONAL / not yet configured, and `EVIDENCE_DEPLOYMENT_PREPARATION.md` lists Stripe configuration as a pre-deployment action for a future production rollout. | Backend: complete payment architecture — `PaymentProvider` abstraction, `TestPaymentProvider` (mock, explicitly "NOT a production provider"), `POST /payments/initiate/{order_id}` with full server-side validation (ownership, order type, payment-eligible state, duplicate-payment and idempotency checks), webhook endpoint with replay protection, refund processor; order `prepare` requires `PaymentStatus.SUCCEEDED` for online orders. Mobile checkout: online payment option initiates payment via the real API. Order detail: displays `Online · pending` status but has no retry button. No real sandbox or credentials are available locally; the router instantiates `TestPaymentProvider` by design. | `EVIDENCE_ONLINE_PAYMENTS.md` (91/91 assertions); `apps/api/app/modules/payments/` (service/router/providers); `apps/mobile/app/(app)/checkout.tsx`; `PRODUCTION_INTEGRATION_AUDIT.md` §Stripe; ADR-001 "Payment gateway selection" deferred | **KEEP AS-IS** + **DOCUMENT LIMITATION** — implemented architecture verified; real payment-provider transaction not verifiable because no sandbox credentials/provider configuration are available. The order-detail retry button is a UX enhancement dependent on a real provider lifecycle, not a spec requirement. | Required — external dependency blocks real provider integration |
| Real-time order updates (mobile polling) | **Yes, but refined by ADR** — "Real-time order updates (WebSockets)" is listed as a Phase 6 deliverable in `docs/architecture/phases.md`. ADR-001 refined the decision: "Use REST for normal operations. Real-time (WebSockets) only where genuinely valuable (order status tracking)" and "only introduce when user experience requires it"; `docs/architecture/overview.md` states "REST for normal operations, real-time only where genuinely needed". The implementable requirement is therefore real-time order-status updates on the customer surface — satisfied on web via REST polling, **not** satisfied on mobile order detail. No WebSockets/SSE exist anywhere and none are required. | Web: REST polling — orders page refreshes every 30 s (`setInterval(loadOrders, 30000)`), header notification count polls every 30 s. Mobile: order detail loads once via `useEffect([id])` and never auto-refreshes; orders tab has pull-to-refresh only. Manual refresh/navigation reloads status correctly. Backend order-status endpoints already correct and RBAC-enforced. | `docs/architecture/phases.md` Phase 6; ADR-001 Communication section; `apps/web/src/app/dashboard/orders/page.tsx:72`; `apps/mobile/app/(app)/order/[id].tsx`; `apps/mobile/app/(app)/(tabs)/orders.tsx` | **FIX** — complete the partially implemented requirement with the smallest architecture-compatible change: add REST polling to mobile order detail using the existing web pattern (15 s interval, terminal-state stop, focus-aware, single timer, cleanup on blur/unmount). No WebSockets, no new infrastructure. | Required — partially implemented; smallest completion |

---

## Gap Detail

### A. Notifications screen — NOT a current requirement

**Original requirement status:** The mobile notification inbox was explicitly scoped out as a "future slice" in the UI redesign specification, and native push notifications are deferred in ADR-001. The Phase 6 deliverable that *was* required — order-status notifications generated from real order events — is implemented and verified: 14 order/payment integration points and 3 refund integration points emit database notifications, with idempotency via `source_event_id`, ownership isolation on all endpoints, and full live verification (order created → notification generated → read state transitions → unread-count decrements → ownership isolation).

**Distinguishing delivery channels (per Phase 22 §22.6):**

| Channel | Status |
|---------|--------|
| Database notification | Implemented and tested (64 unit tests, 15 live checks) |
| In-app notification | Implemented on **web** (`/dashboard/notifications`); **not** on mobile (deferred) |
| Browser notification | Not implemented (not required) |
| Native push notification | Not implemented — external provider/credentials required; deferred in ADR-001. **Not claimed.** |

**Decision:** KEEP AS-IS. Creating a mobile inbox now would implement an explicitly deferred enhancement, which Phase 22 rules prohibit ("If a dedicated screen was NOT required, do not create one just to eliminate the report item").

### B. Online payment / Pay Now — architecture implemented; real provider unavailable

**Three-way distinction (per Phase 22 §22.5):**

| Layer | Status |
|-------|--------|
| Implemented architecture | **Yes** — provider abstraction, initiation endpoint, webhook confirmation, refund processing, idempotency, replay protection, IDOR/ownership checks, inventory reservation on payment success, prepare-gating on `SUCCEEDED`; 91/91 live assertions + payment/refund/security test suites pass |
| Real payment provider integration | **No** — `TestPaymentProvider` mock only; router comment: "In production, this would load the configured provider. For now, uses the test provider." Stripe is listed as OPTIONAL / not configured in `PRODUCTION_INTEGRATION_AUDIT.md`. **No sandbox credentials are available locally.** |
| UI availability | Checkout online-payment selection + initiation: **implemented** (mobile). Order-detail payment status display: **implemented**. Order-detail "Pay Now" retry: **not implemented** — and not an explicit spec requirement. |

**Explicit limitation statement:** *Real payment-provider transaction not verified because no sandbox credentials/provider configuration are available.* No fake provider, no simulated success UI, no unpaid order marked paid, no production credentials used.

**Decision:** KEEP AS-IS + DOCUMENT LIMITATION. The retry button is a UX completion item tied to a real provider's abandonment/retry lifecycle; without a configured provider it would only re-invoke the same mock initiation path that checkout already exercises.

### C. Real-time order updates — partially implemented; mobile completion is the fix

**Current mechanisms:**

| Surface | Mechanism | Interval | Covers |
|---------|-----------|----------|--------|
| Web orders page | REST polling `setInterval` | 30 s | Order list statuses |
| Web header | REST polling `setInterval` | 30 s | Notification unread count |
| Mobile orders tab | Load once + pull-to-refresh | — | Manual |
| Mobile order detail | Load once `useEffect([id])` | — | **Nothing auto-updates** |

Manual refresh already updates status correctly, so the backend and data layer are sound. The gap is purely the mobile detail screen's refresh cadence. WebSockets are explicitly *not* required by ADR-001 ("only introduce when user experience requires it") and no WebSocket infrastructure exists — introducing one would violate "smallest architecture compatible."

**Smallest correct implementation (applied in this phase):** REST polling on mobile order detail —

- 15 s interval (tighter than web's 30 s list polling because this is a single actively-watched order; ≈4 requests/min worst case, only for active orders on a focused screen)
- Polls `getOrder` (+ `getOrderPayment` for online orders) in the background without toggling the initial-loading state
- Stops at terminal statuses (`completed`, `cancelled`)
- Focus-aware: runs only while the screen is focused; cleanup on blur/unmount via `useFocusEffect`
- Single timer guarded by a ref — no duplicate timers
- Auth-expiration handled by the existing global `ApiClient` failure path (tokens cleared → role gate redirects → screen unmounts → interval cleared)

---

## Security / RBAC Impact

None. Phase 22 touches only a mobile read-only polling loop over existing authenticated endpoints (`GET /orders/{id}`, `GET /payments/order/{id}`) that already enforce owner checks. No backend endpoint, permission, order rule, or two-surface boundary was modified. Student → web admin, faculty → admin, student → faculty cafeteria, staff → mobile ordering, and unauthorized refund/administration access remain blocked by unchanged backend RBAC (covered by the existing security test suites re-run in Phase 22 regression).
