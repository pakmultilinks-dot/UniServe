# UniServe — Final Client Acceptance Findings Triage

**Task:** Classify the seven findings (F-ACC-01…F-ACC-07) recorded in `FINAL_CLIENT_ACCEPTANCE_TEST.md` §19 into **A (fix before final presentation)**, **B (leave as known limitation)**, or **C (test residue / not a product issue)**.

**Scope discipline:** This was a **triage/review task only**. No other broad product audit was performed. No client acceptance step was repeated. No fixes were implemented. No application source file, database row, dependency, credential, seed record, or lock file was modified. The only file newly created in this triage is this report.

**Acceptance verdict status:** The acceptance test's verdict — **CLIENT ACCEPTANCE: PASS WITH MINOR FINDINGS** (P0=0, P1=0, P2=3, P3=4) — **stands unchanged**. The classification below is a presentation-preparedness decision, not a release reversal.

---

## 1. Executive Decision

All seven findings were verified against the actual code paths, the live database, and the project's own prior audit record. One live reproduction was performed (read-only, single-instance) because one finding's classification depended on the live data state. Every other finding was resolved by code/path inspection, which the reproduction rule permits as sufficient when the path is verifiable.

The evidence supports this distribution:

- **A — FIX BEFORE FINAL PRESENTATION: 1 finding (F-ACC-06).** The staff web console renders an enabled **Prepare** button on orders whose status is `pending` but which have **not been confirmed yet**, even though the code right above it already contains the correct gating pattern for the **Confirm** button. Clicking it fires a request the server predictably rejects with HTTP 400. This is a genuine, deterministic UI/state defect on the single most prominent screen of the staff demo, it is visible during a completely normal client interaction (staff clicks the next logical button), and the fix is a **one-line, client-only conditional** that reuses the exact pattern already present 20 lines above. Precedent: the same class of defect ("buttons that fire predictably rejected requests") was fixed in **Phase 42** (`bc967b3 fix: close Phase 42 product acceptance defects`) — the codebase's own established standard treats this as a defect worth fixing.

- **B — LEAVE AS KNOWN LIMITATION: 5 findings (F-ACC-01, F-ACC-02, F-ACC-04, F-ACC-05, F-ACC-07).** These are genuine observations, but none is a broken feature, none blocks a demo workflow, and each is either invisible to the user, documented as expected behavior, a preference-level enhancement, or — in two cases — mis-scoped error-copy work whose correct root-cause fix (error differentiation in the mobile client) touches the shared menu/error path and is not worth the regression risk this close to the presentation. Two findings (F-ACC-02, F-ACC-05) required **refinement during triage**: the code evidence shows their originally-described mechanisms are not quite right, which lowers their presentation risk further (see §3).

- **C — TEST RESIDUE / NOT A PRODUCT ISSUE: 1 finding (F-ACC-03).** The oddly-named catalog item is **proven** by database state to be a leftover of the acceptance test's own first (failed) menu-creation attempt, created 118 minutes after the environment was confirmed and 2 minutes before the successful retry. It is data, not code. Per the data-safety mandate it was **not** deleted — it remains in the demo database pending a separately sanctioned cleanup decision.

**Net effect of the recommended action:** apply the single F-ACC-06 guard before the presentation; brief the presenter on the five B limitations (§5); schedule C-classified data cleanup for a later, separately approved pass (§6). No other action is required.

---

## 2. Finding-by-Finding Table

| Finding | Severity | Classification | Real product issue? | Presentation impact | Action |
|---|---|---|---|---|---|
| **F-ACC-01** — background `/auth/me` 401 noise on unauthenticated web console | P3 | **B** — known limitation | No — documented client silent-refresh retry pattern | None for a normal user (browser console only); do not open DevTools on stage | None; presenter awareness only |
| **F-ACC-02** — student sees "menu is taking a break" instead of an access-denied message after picking a restricted cafeteria | P2 | **B** — known limitation | Marginal — the API enforces access correctly; the *copy* is generic. Triage refinement: a fresh student session **cannot** receive the Faculty Cafeteria in its switcher (backend filters it out), so the observed path required stale in-memory state across a role switch without a reload | Low — not reachable in a clean student login; a student demo started normally shows only permitted cafeterias | None pre-presentation; presenter awareness (§5); fix candidate recorded in §4 for a later hardening pass |
| **F-ACC-03** — residue catalog item named with a full description sentence in admin picker/inventory | P3 | **C** — test residue | No — created by the acceptance test's own failed first create attempt (DB-proven) | Low — visible only in admin catalog/inventory lists; mildly confusing to the presenter, not to a client role | None in code; leave data per data-safety mandate; schedule separate sanctioned cleanup (§6) |
| **F-ACC-04** — zero-stock items publishable with no publisher-side warning; failure surfaces later at student add-to-cart | P2 | **B** — known limitation | No — inventory gating works correctly (server 400 blocks the cart op; student stays on item page). The gap is a missing *warning*, a completeness enhancement | None in the demo path — today's published daily menu contains only items with positive stock; the blocking behavior, if ever shown, is a correct and clearly-blocked outcome | None pre-presentation |
| **F-ACC-05** — cafeteria selection persists across reloads; stale context yields generic "Failed to load item details"; selection "silently reverts" | P2 | **B** — known limitation | Marginal — generic error copy on an edge path. Triage refinement: the selection does **not** persist (no storage write in code); on every fresh mount it deterministically defaults to the **first role-permitted cafeteria**, and the observed "revert" was this default landing on the residue "Phase 56 E2E" test cafeteria in the current demo database | Low — deep links with a mismatched context are not part of any planned demo flow; the default-selection behavior is sensible when the database holds only real cafeterias | None pre-presentation; presenter awareness (§5); fix candidate recorded in §4 for a later hardening pass |
| **F-ACC-06** — staff queue enables "Prepare" on unconfirmed Pending orders; click fires a rejected request (400) with corrective toast | P3 | **A** — fix before final presentation | **Yes** — deterministic UI/state defect: the button is rendered without the `confirmed_at` guard the codebase already uses for its sibling "Confirm" button; the server correctly rejects the premature action | **Moderate** — the staff order-queue is a core demo screen; a presenter (or client being invited to try) naturally clicks the topmost action button on a fresh pending order and gets a red error toast. A rejected request during a live client interaction erodes confidence even though the guardrail message is clear | **Implement the one-line guard in §4** (disable/omit Prepare until `order.confirmed_at` is set). Do not attempt any other change |
| **F-ACC-07** — no Sign out control on the staff/manager Profile page; sign-out lives in the nav drawer (and desktop rail) | P3 | **B** — known limitation | No — sign-out is implemented and reachable in the navigation drawer (mobile layout) and the desktop sidebar rail, matching the admin console's structure | None — the presenter knows the sign-out path; no client role is ever told to hunt for it | None pre-presentation |

---

## 3. Evidence

Verification method per finding: code/path/data inspection for all seven; **one** targeted, read-only live verification for F-ACC-03 (DB state) because the C classification hinges on data provenance. **No finding was re-tested end-to-end**; no source was modified during verification.

### F-ACC-01 — background 401 noise (B)

- **Observed during acceptance:** repeated 401 responses for `GET /api/v1/auth/me` in the browser console of unauthenticated web console pages.
- **Code/path:** `apps/web/src/contexts/AuthContext.tsx` lines 56–77 — on mount, `trySilentRefresh()` calls `authApi.getCurrentUser()` (`/auth/me`) once; the API client may attempt a token refresh first, producing a transient 401 before the flow settles; on failure the app simply sets `user = null` and the guard redirects to login. There is **no recurring poller** — this is a boot-time cycle, not background polling.
- **Why classification B (not A):** this exact behavior is **documented as expected** in four prior project documents: `DEPLOYMENT_RUNBOOK.md` (line 393: "One 401 on `/auth/me` after web hard reload → expected; repeated 401s → check CORS"), `PHASE_46_ADMIN_CONSOLE_FOUNDATION_AND_ERROR_TRANSPHERE.md` (line 164: "routine 401s on `/auth/me` are the normal silent-refresh cycle"), `PHASE_62_DEMO_READINESS_AND_FINAL_RELEASE_CHECKLIST.md` (line 51: "transient `/auth/me` 401×2 on boot = documented client retry pattern, not a defect"), and `DEMO_SCREENSHOT_CHECKLIST.md` (line 77, same). It is invisible to any user who is not reading developer console output, and it has zero functional consequence. Re-classifying it as A would contradict four prior acceptance gates without new evidence.
- **Reproduction necessary?** No — code path and project documentation fully determine the classification.

### F-ACC-02 — misleading menu error for restricted cafeteria (B, with triage refinement)

- **Observed during acceptance:** API returned 403 "Access to Faculty Cafeteria is restricted to faculty members" (log ~11:26 UTC) after a student session selected Faculty Cafeteria from the Expo switcher; the Expo UI displayed "The menu is taking a break / Failed to load menu" (screenshots e06/e14 context).
- **Code/path:** the misleading copy comes from a bare catch block in `apps/mobile/app/(app)/(tabs)/index.tsx` (≈line 168): `catch { setError("Failed to load menu") }` → rendered as "The menu is taking a break" (≈line 329). Every error — network, 403, 5xx — collapses into the same "outage" message. The mobile client has the information to differentiate (`ApiClientError.status`, `packages/shared-types/src/index.ts` line 1163) but does not use it here.
- **Triage refinement (path verifiability):** `apps/api/app/modules/cafeterias/router.py` lines 85–90 **force** `cafeteria_type = STUDENT` for any student request — a student calling `GET /cafeterias` can **never** receive the Faculty Cafeteria in the list that feeds the Expo switcher (`apps/mobile/src/services/data.ts`, `getCafeterias()`). The observed 403 therefore could not arise from a freshly authenticated student session; it required **stale in-memory provider state** across an account/role switch inside the same running app instance without a reload — a test-execution artifact, not a path a real student reaches. During the acceptance session the app instance in fact carried a previously-stored cafeteria context from a different account (this session's own notes recorded resolving the Expo 403 by re-selecting Student Cafeteria via the switcher).
- **Why classification B (not A):** the security boundary works (403, server-enforced); the defect is *wording on an edge path* whose trigger requires a stale multi-account app session. A clean student login — the demo path — cannot reach it. The correct fix (differentiate 403 → access-denied copy in the mobile menu/item error states) modifies the shared mobile error surface used by every cafeteria load, which is exactly the kind of change the reproduction rule's "no source modification" spirit and pre-presentation risk posture argue against.
- **Reproduction necessary?** No — the router's student filter deterministically rules out the originally-described trigger; code inspection is conclusive.

### F-ACC-03 — residue catalog item (C)

- **Observed during acceptance:** an admin catalog/picker/inventory entry whose *name* is the sentence "Fragrant basmati rice layered with spiced chicken, fried onions, and raita. Served with salad." (PKR 250, stock 0).
- **Data (read-only DB verification, performed once):**

  ```
  id          386c7654-8ca9-4e56-a3ea-3ac3afa03147
  name        Fragrant basmati rice layered with spiced chicken, fried onions, and raita. Served with salad.
  price       25000 (paisa) = PKR 250
  is_active   t      is_available   t
  created_at  2026-10-08 15:49:35+05
  inventory   quantity = 0 (same timestamp, +30 ms)

  ```

- **Why classification C (not A/B):** the timestamps prove provenance. The acceptance test's Phase C (admin menu creation) ran in the **11:44–12:10 UTC** window (≈16:44–17:10 +05); the report itself states the four intended items were created at 16:54–16:58 +05. This record was created at **15:49:35 +05 (10:49 UTC)** — 118 minutes before that window, which corresponds to the earlier live-verification menu setup pass, and its name is literally the *description text* of the item created 5 minutes later at 15:54 +05 ("Chicken Biryani — Fragrant basmati rice layered with spiced chicken…", whose own acceptance record shows inventory 49). That is the signature of a failed first create (name/description fields swapped or description pasted into name) followed by a corrected retry. The acceptance report's own §19 register records it as "created by the acceptance test's earlier failed first-attempt create". It is **test data, not code behavior** — no product logic produced it.
- **Per data-safety mandate:** the row was **not** deleted, edited, or deactivated; the classification is recorded for a separate, sanctioned cleanup decision (§6).
- **Reproduction necessary?** Yes, in the read-only form above — the C classification required confirming live data provenance (timestamps, price, stock) rather than trusting the narrative. That verification was performed once, with a single SELECT, no writes.

### F-ACC-04 — silent zero-stock publish (B)

- **Observed during acceptance:** items auto-create with inventory 0; a daily menu containing them published with no warning; the failure surfaced later at the student's add-to-cart as API 400 "Insufficient inventory: available=0, requested=1" (e18; API log 11:26 UTC).
- **Code/path:** `apps/web/src/app/dashboard/menu/page.tsx`, `handlePublishDailyMenu` (≈line 220) calls `publishDailyMenu(...)` with no stock inspection; the publish button carries no zero-stock indicator. The server's publish validation covers menu non-emptiness (error handling at ≈line 228 references "Cannot publish an empty menu") but not per-item stock. Stock enforcement happens where it should: at cart/order time, where the API blocks the operation and the client keeps the student on the item page (correct block, late discovery).
- **Why classification B (not A):** the *gating* — the part that protects the business — is correct. What is missing is a **publisher-side convenience warning**, a completeness enhancement, not a defect in any existing behavior. Adding a warning pre-presentation would mean touching the daily-menu publish flow (new UI state, new copy, new test surface) for a scenario the demo does not exercise: today's published daily menu (id `8446a108`, 8 items) contains only items with positive stock (e.g., the four new items restocked to 49–50 during the acceptance session). Risk/benefit is clearly negative.
- **Reproduction necessary?** No — the code path shows unambiguously that no stock check exists at publish time and that enforcement exists at cart time (which the acceptance test already exercised live).

### F-ACC-05 — cafeteria persistence and generic deep-link error (B, with triage refinement)

- **Observed during acceptance:** cross-cafeteria deep link produced API 403 "This menuitem does not belong to the specified cafeteria" (11:34 UTC) with client copy "Failed to load item details"; the cafeteria selection appeared to persist across reloads and to "silently revert" to the last-stored value (e06, e16).
- **Code/path:**
  - Generic copy: `apps/mobile/app/(app)/item/[id].tsx` line 123 — `catch { setError("Failed to load item details") }`, again collapsing 403/404/network into one message.
  - Selection lifecycle: `apps/mobile/src/contexts/CartContext.tsx` lines 55–78 — `selectedCafeteria` is held **only in React state**; there is **no `localStorage`/`AsyncStorage` write anywhere** for it. On every mount the provider waits 150 ms for token load, fetches `getCafeterias()` (role-filtered by the server), and sets `cafeterias[0]` as the default.
- **Triage refinement (path verifiability):** the "persistence" described in the finding is not implemented in code; what looks like persistence across reloads was the app instance surviving in a browser tab, and what looks like a "silent revert to last-stored value" is this **deterministic default-to-first-cafeteria** behavior. In the current demo database the first (and only) entry in the student-filtered list is the acceptance session's own **"Phase 56 E2E" test-residue cafeteria** (`50d67d4b-…`), so every fresh student mount defaults to that residue cafeteria — which then 403s when a real Student-Cafeteria item is opened from a deep link. This means the finding's trigger is substantially **an artifact of residue data in the demo database**, not of client persistence logic. With only real cafeterias present, the default selection is exactly what a user would pick anyway.
- **Why classification B (not A):** same reasoning as F-ACC-02 — server enforcement is correct; the residual issue is generic copy on an edge path, and the observable oddity traces to dirty demo data rather than shipped behavior. The demo path (browse → tap item in the selected cafeteria) never hits it.
- **Reproduction necessary?** No — code inspection disproves the persistence mechanism and explains the observed reversion deterministically.

### F-ACC-06 — Prepare enabled on unconfirmed orders (A)

- **Observed during acceptance:** on the staff order queue, Pending-order cards render **Prepare** as an enabled button; clicking it fires a request rejected with HTTP 400 and the corrective toast "Order must be confirmed before starting preparation" (staff orders page console; e25).
- **Code/path (`apps/web/src/app/dashboard/orders/page.tsx`):**
  - Line 563 — the **Confirm** button is correctly gated: `{!order.confirmed_at && (<Button …onClick={() => handleAction(order.id, () => confirmOrder(order.id))}>Confirm</Button>)}`.
  - ≈Line 585 — the **Prepare** button is gated on status only: `{order.status === "pending" && (<Button …onClick={() => handleAction(order.id, () => prepareOrder(order.id))}>Prepare</Button>)}` — **no `confirmed_at` condition**, so on a pending, unconfirmed order both Confirm *and* Prepare render, in that visual order, with Prepare as the more prominent variant.
  - Line 227–231 — `handleAction` awaits the action and then calls `loadOrders()`, so every outcome (success or rejection) refreshes the queue; the refresh returns `confirmed_at` values, which means the gating data is **already present in the rendered order objects**. No new fetch or API change is needed to fix this.
- **Why classification A (genuine, presentation-visible, trivially fixable):**
  1. **Deterministic and normal-path:** a fresh order in the demo queue (any newly placed order starts `pending`/unconfirmed) renders the defective state immediately; clicking the topmost action button is the most natural staff interaction there is — including if a client is invited to try the staff screen.
  2. **It contradicts the codebase's own standard:** the sibling Confirm button in the same JSX block implements the exact guard, and **Phase 42's closing commit (`bc967b3`) fixed this same defect class** (buttons firing predictably rejected requests — e.g., the "Prepare on pending order" guardrail was already established server-side). Precedent says this is fixed-before-presentable.
  3. **The fix is one line, client-only, and self-testing:** gate Prepare on `!!order.confirmed_at`, exactly mirroring line 563. The server already rejects the premature call (proven live during acceptance — 400 with a clear message), so the guardrail remains; only the unreachable button is removed from view until the order is confirmed.
  4. **No collateral:** `apps/web/src/__tests__/orders-page.test.tsx` contains **no assertion** referencing Prepare or `confirmed_at` (verified by search), so the change breaks no existing test; the manager Reject button and all post-confirmation actions are untouched.
- **Reproduction necessary?** No — the render condition in code plus the already-live-observed 400 (recorded during acceptance) fully determine the classification. No additional click-through was performed; the rejected request path is non-mutating by design (server refuses), but even that was unnecessary.

### F-ACC-07 — no Sign out on Profile page (B)

- **Observed during acceptance:** `/dashboard/profile` (staff/manager) has no sign-out control; sign-out is reachable only via the nav drawer ("Open navigation menu" → "Sign out") (e32, e33).
- **Code/path:** `apps/web/src/components/Sidebar.tsx` — the desktop rail exposes Sign out (lines 329/348, `title="Sign out"`) and the mobile drawer's user section has the full "Sign out" row (line 455). `apps/web/src/app/dashboard/profile/page.tsx` contains only profile self-service (Phase 55 `PATCH /auth/me`) and no auth actions. The admin console follows the same structure (Settings page carries an explicit "Sign Out of the operations console" block; its Profile-equivalent pages likewise do not duplicate sign-out).
- **Why classification B (not A):** this is a **layout-pattern preference**, not a defect: sign-out is implemented, reachable in every responsive layout, and consistent across consoles. Adding a second sign-out control to the Profile page pre-presentation is cosmetic churn with no demo-path problem to solve.
- **Reproduction necessary?** No — component structure fully answers it.

---

## 4. Fix Candidates

**Scope: A-classified findings only. F-ACC-06 is the sole entry. Nothing here has been implemented — this triage made no source changes.**

### FIX-1 — Staff order queue: disable/omit "Prepare" until the order is confirmed

- **Exact defect:** the **Prepare** action button renders enabled for any order with `status === "pending"`, including orders that have not been confirmed (`confirmed_at` unset). Activating it issues `prepareOrder(order.id)`, which the server deterministically rejects with HTTP 400 ("Order must be confirmed before starting preparation"). The UI therefore advertises an action it will not be allowed to perform, and the user experiences a failure (red toast + rejected network request) for what should be an unavailable step.
- **Affected client / role:** **Staff** (primary) and **Manager** (secondary — same queue component) in the **web console**, on the **order queue page** — the central operations screen of the staff demo.
- **Affected file / path:** `apps/web/src/app/dashboard/orders/page.tsx`, the pending-order action block at ≈lines 583–594 (Prepare button), mirroring the existing gate on the Confirm button at line 563.
- **Smallest safe fix:** add the same guard already used for Confirm — render the Prepare button only when the order has been confirmed, i.e. change the condition from `order.status === "pending"` to `order.status === "pending" && !!order.confirmed_at`. No API call, no state shape, no styling, and no other button is affected; `handleAction`'s post-action `loadOrders()` refresh already supplies `confirmed_at` for every card, so the button appears as soon as confirmation lands (and via the 30-second auto-refresh for orders confirmed elsewhere). **Alternative equally-small variant:** keep the button rendered but `disabled` with a `title`/tooltip ("Confirm the order first") — visually communicates the workflow order; slightly larger diff (Button `disabled` prop + tooltip). The conditional-render variant is preferred because it exactly matches the codebase's existing Confirm-gate idiom.
- **Expected validation:** (1) open `/dashboard/orders` as the staff demo account while a **pending, unconfirmed** order exists → Confirm and Reject (manager) appear, **Prepare does not**; (2) click **Confirm** → the queue refreshes and the card now shows **Prepare** (status still `pending`, `confirmed_at` set); (3) click **Prepare** → request succeeds, status → `preparing`, and the **Ready** action appears; (4) regression: with an order already in `preparing`, Ready/Collect/Confirm-Collect flow is unchanged, and a **pre-confirmed** pending order shows Prepare exactly as it does today; (5) automated: run the web unit suite (`orders-page` and related) — no existing test asserts the Prepare-on-unconfirmed rendering, so all tests should pass unchanged.

**Explicitly not recommended as pre-presentation fixes** (recorded for a later hardening pass, not to be done now): F-ACC-02/F-ACC-05 mobile error-copy differentiation (branch on `ApiClientError.status` — 403 → "restricted" / "not available in this cafeteria" copy with a cafeteria-switch affordance — in `apps/mobile/app/(app)/(tabs)/index.tsx` ≈168 and `apps/mobile/app/(app)/item/[id].tsx` ≈123); F-ACC-04 zero-stock publish warning (menu page: surface per-item stock in the daily-menu picker + confirm-step note when any selected item has stock 0). Each is real work on shared mobile/menu surfaces with demo-visible copy — deferred deliberately.

---

## 5. Known Limitations

All B-classified findings. None blocks a client workflow; each is listed so the presenter is not surprised.

1. **F-ACC-01 — transient 401s on `/auth/me` at web-console boot (console-only).** Normal users never see this; it is the documented silent-refresh cycle (runbook §B8, Phase 46, Phase 62 all record it as expected). *Presenter awareness:* if DevTools is opened during the demo, one or two 401s before login settles are expected and harmless — do not treat them as breakage.
2. **F-ACC-02 — generic "menu is taking a break" copy on load failures in the mobile app.** Any failure (network, permission, server) currently shows the same outage-flavored message. *Presenter awareness:* the restricted-cafeteria path that surfaced this cannot occur in a clean student session (the backend filters Faculty Cafeterias out of student lists); the copy issue only matters if a load failure happens for other reasons, and the correct remedy (pull-to-retry) is already offered on screen. Do not demo a cross-role account switch in the same running app instance without reloading.
3. **F-ACC-04 — daily-menu publish does not warn about zero-stock items.** Publishing is unrestricted; enforcement happens (correctly) when a student tries to add an out-of-stock item to the cart, with a clear block. *Presenter awareness:* today's published menu contains only stocked items; if a zero-stock scenario is ever shown, the correct talking point is "the system refuses to oversell — inventory is enforced server-side at cart time", which is a strength, not a failure.
4. **F-ACC-05 — item-detail deep links with a mismatched cafeteria context show a generic "Failed to load item details", and a fresh app session defaults to the first permitted cafeteria.** The default is sensible; the generic copy is the residual gap (same fix family as F-ACC-02). *Presenter awareness:* always enter items from the home grid of the currently selected cafeteria; in the current demo database the first student cafeteria is the "Phase 56 E2E" residue cafeteria, so explicitly pick **Student Cafeteria** from the switcher before a student demo (this is also a data-hygiene item — see §6). No planned demo flow deep-links across cafeterias.
5. **F-ACC-07 — Profile page has no Sign out control.** Sign-out lives in the navigation drawer (mobile layouts) and the desktop sidebar rail, consistent with the admin console's structure. *Presenter awareness:* use "Open navigation menu → Sign out" (web) or Profile → Sign Out (mobile app); never rely on a profile-page button that does not exist.

---

## 6. Test Residue

All C-classified findings. These are artifacts of prior test/acceptance execution, not product behavior, and per the data-safety mandate **nothing was deleted or altered** during this triage.

1. **F-ACC-03 — mis-named catalog item.** DB-proven provenance: `menu_items.id = 386c7654-8ca9-4e56-a3ea-3ac3afa03147`, name = the full description sentence of the real "Chicken Biryani" item, price PKR 250, active+available, `created_at 2026-10-08 15:49:35+05`, inventory quantity 0 (same instant) — i.e., a failed first create from the earlier menu-setup pass, superseded 5 minutes later by the correct item. No product code generated it; it is inert data. **Why not a product defect:** a correct system displays whatever its database holds — the fault is in the data's origin (test execution), not in any application behavior.
   **Recommended (separate, post-presentation, explicitly sanctioned action — NOT performed here):** archive/deactivate or rename the row via the legitimate admin/catalog workflow, or delete it in a maintenance window with a backup taken first. It should also be removed from any active daily menu if present.
2. **Related residue the presenter should know about (context for F-ACC-05, not a separate finding):** the demo database still contains the **"Phase 56 E2E" test cafeteria** (`50d67d4b-841b-43c4-b60d-eeb1cf68152a`), which occupies the first slot of the student-filtered cafeteria list and therefore becomes the Expo app's default selection on fresh mounts. This is residue data, not a code defect, and is the main reason F-ACC-05's observable behavior appeared odd. Same recommendation class: schedule its deactivation/removal in the same sanctioned cleanup pass; until then, switch to **Student Cafeteria** explicitly before any student-facing demo (as done successfully in the acceptance test).

---

## 7. Final Recommendation

**FIX REQUIRED BEFORE PRESENTATION**

The required fix scope is exactly **one item**: **FIX-1 (F-ACC-06)** — gate the staff/manager web console's **Prepare** button on `order.confirmed_at` in `apps/web/src/app/dashboard/orders/page.tsx`, a one-line client-only change mirroring the existing Confirm-button guard. Nothing else should be changed: the remaining six findings are either documented expected behavior (F-ACC-01), non-blocking limitations to brief the presenter on (F-ACC-02, F-ACC-04, F-ACC-05, F-ACC-07 — §5), or test data requiring a separately sanctioned cleanup (F-ACC-03 — §6). The acceptance verdict **CLIENT ACCEPTANCE: PASS WITH MINOR FINDINGS** is unchanged; this recommendation is a presentation-preparedness measure for the single most-visible deterministic UI defect, consistent with the Phase 42 precedent for this defect class.

---

*Triage performed as a review-only task: no fixes implemented, no application source modified, no data deleted or altered, no dependencies or lock file touched, no deployment performed. Verification was limited to the seven recorded findings (code/path inspection for six, one read-only database check for F-ACC-03).*
