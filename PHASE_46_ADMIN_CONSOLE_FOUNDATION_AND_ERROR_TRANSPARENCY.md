# PHASE 46 — Admin Console Foundation & Error Transparency

> **Date:** 2026-10-04
> **Branch:** `main`
> **HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (unchanged — no commit, no push)
> **Type:** Implementation (not audit)
> **Preceded by:** `PHASE_45_ADMIN_PRODUCT_COMPLETENESS_AUDIT.md`
> **Constraint compliance:** No commit / no push / no DB schema change / no dependency change / no lockfile change / no deploy / no fake data / no RBAC weakening / no redesign / unrelated role flows untouched / stop after Phase 46.

---

## 1. Executive Summary

Phase 45's admin-console audit found that the web console could not be trusted to tell the truth about failures: API errors were silently swallowed, request failures masqueraded as empty data, the Administration Overview reported "2 active cafeterias" while the Cafeterias page showed "No cafeterias", and the console gave operators no loading, error, retry, or unauthorized states to reason with.

Phase 46 rebuilds that foundation:

1. **Structured error mapping** — `getApiErrorInfo()` in `apps/web/src/lib/api.ts` classifies every `ApiClientError` (auth / permission / timeout / network / server / client / unknown) with a human-readable, retry-aware message.
2. **A shared error-state component** — `LoadErrorState.tsx` renders "Unable to load X." + reason + an optional **Try again** button, reusing the console's existing EmptyState visual language.
3. **Eleven dashboard pages converted** from bare `catch { setX([]) }` to the state machine: *loading → error (retryable) → empty (only after success) → success with data* (compact retry banner when a refresh fails but stale data is still on screen).
4. **Bugs found and fixed along the way**: the reports page's infinite-skeleton failure mode; the staff page's dead never-rendered cafeteria fetch; two silent `catch {}` action handlers on notifications; unescaped JSX quotes on orders (surfaced by newly-enabled lint).
5. **Authentication investigation concluded** (mission item 6): the in-memory access-token design is **secure-by-design XSS mitigation** and is **deliberately NOT changed**. Page reloads work via silent refresh; failures now surface as an auth error and RouteGuard cleanly redirects to login — verified live.

**Verification:** web type-check **PASS**; web lint **PASS** (0 errors, 3 pre-existing/intentional warnings); production build **compiles + type-checks + generates all 24 static pages**, with one honest caveat (see §7.3) caused by a pre-existing node_modules dual-React condition outside Phase 46's file scope; manual browser verification **PASS** on all five scripted scenarios including simulated API failures, retry, logout, and invalid-session handling.

---

## 2. Findings Addressed (Phase 45 → Phase 46)

| # | Phase 45 finding | Phase 46 implementation | Verified |
|---|---|---|---|
| 1 | Silent error-swallowing behind "Overview says 2 cafeterias / page says none" confusion | Every admin/dashboard page now distinguishes request failure from genuine emptiness; failures render `LoadErrorState`, never fabricated empty states | ✅ live (§8.1) |
| 2 | Bare `catch { setCafeterias([]) }` on the Cafeterias page | Flagship fix: `loadError` state + `getApiErrorInfo` catch + error branch + compact refresh-failure banner + retry | ✅ live 500-simulation (§8.2) |
| 3 | Same bare-catch pattern on Users, Staff, Orders, Menu, Reports, Refunds, Overview, Inventory, Notifications, Dashboard home | All ten remaining pages converted with the same per-page state machine and retry behavior | ✅ live spot-checks (§8.3) |
| 4 | No loading states | Loading skeletons preserved; new rule: **error states are checked before empty states**, so a failure never renders as skeleton→empty | ✅ (§8.2, §8.4) |
| 5 | No retry behavior | Every retryable error offers **Try again** (direct loader call, or a reload-key bump for loaders inside `useEffect`) | ✅ live retry (§8.2) |
| 6 | In-memory access token persistence suspected of breaking sessions | Investigated and documented as secure-by-design; **no change made**; failures now surface and fail closed to login | ✅ live (§8.6, §8.7) |
| 7 | Reports page infinite skeleton when the cafeteria load failed | Cafeteria-load failure now renders `LoadErrorState` and clears `loading`; sales failure renders its own retryable state; "No report data" shows only after a successful response | ✅ live 500-simulation (§8.4) |
| 8 | Notifications mark-read / mark-all-read failures silently no-op | Both `catch {}` blocks now surface failures via toast | ✅ code-verified; toast path shared with all other pages |
| 9 | Staff page fetched cafeterias it never rendered | Dead fetch + dead state + its silent catch removed | ✅ compile/lint clean |
| 10 | "No cafeterias found." wording ambiguity | Genuine-empty title is now exactly **"No cafeterias found."**; failures never reach it | ✅ live (§8.2) |

---

## 3. Authentication & Session Investigation (Mission Item 6)

**Question:** should the access token be persisted (e.g. localStorage/sessionStorage) so pages survive reloads without a refresh round-trip?

**Investigation result:**

- `apps/web/src/lib/api.ts` keeps the access token in a **module-scope variable** (`inMemoryAccessToken`) — XSS mitigation, deliberate and documented in the file header. The refresh token lives in `sessionStorage` (`uniserve_refresh_token`); the session cookie (`uniserve_session`) is only a routing hint, never auth proof.
- On reload, `AuthContext` performs a **silent refresh** using the sessionStorage refresh token, then fetches `/auth/me`. If that fails, `onAuthFailure → setUser(null)` and `RoleGuard` redirects to `/login` — the user is **never** stuck in an authenticated-looking broken state.
- The Phase 45 "amplifier" was not the token design — it was pages swallowing the resulting errors. That is exactly what Phase 46 fixed.
- **Decision: no change to token persistence.** Persisting the access token in DOM storage would reintroduce XSS token-theft exposure to "save" one refresh round-trip. Refresh-expiry re-login is an acceptable, secure trade-off and is now *visible* (auth-kind error → clean redirect) instead of silent.

---

## 4. Error-State Behavior Model

Every converted page now implements:

```
loading (skeleton)
  → loadError && no data        → full LoadErrorState: "Unable to load {subject}." + message + Try again
  → no error && no data         → EmptyState (genuine empty result only)
  → data                        → real content (+ compact retry banner when a refresh failed but stale data remains)
```

- **Error taxonomy** (`getApiErrorInfo`): 401 → auth ("Your session has expired. Please log in again.", never a retry button — RoleGuard handles redirect); 403 → permission (explicit notice, no retry — RBAC is the security boundary); 408 → timeout (retryable); 0 → network (retryable); ≥500 → server (retryable, generic message on purpose); other 4xx → client (exact backend detail); unknown → generic retryable.
- **Error + data:** previously loaded data stays on screen; a compact red banner with retry sits above it. Request failures never replace real data with fake emptiness.
- **Retry mechanics:** pages whose loaders are `useCallback` call the loader directly; loaders inline in `useEffect` (reports, overview, orders queue) use a `reloadKey`-style state bump added to the effect dependencies.
- **Intentional non-swallowing rule:** no page in scope sets `setX([])` inside a catch anymore. (The one documented exception is `getMyCafeterias()` in `api.ts` and its dashboard-home twin: that call is an assignment-*hint* for selector scoping, not a displayed dataset; scoped endpoints still enforce 403 which pages surface as explicit access notices.)

---

## 5. Implementation Inventory

### Files created (2 + this report)

| File | Purpose |
|---|---|
| `apps/web/src/components/ui/LoadErrorState.tsx` | Shared error-state card (compact variant for banners); props: `error`, `subject`, `onRetry?`, `compact?` |
| `apps/web/.eslintrc.json` | `{"extends": "next/core-web-vitals"}` — **no ESLint config existed anywhere**, so `next lint` could never run non-interactively. This is lint *configuration*, **not** a dependency change (no packages added; no lockfile touched). |
| `PHASE_46_ADMIN_CONSOLE_FOUNDATION_AND_ERROR_TRANSPARENCY.md` | This report |

### Files modified (12)

| File | Change |
|---|---|
| `apps/web/src/lib/api.ts` | Appended `ApiErrorKind`, `ApiErrorInfo`, `getApiErrorInfo()`; fixed `ApiClientError` to be imported locally then re-exported (the previous `export … from` form left no local binding) |
| `apps/web/src/app/dashboard/page.tsx` | Per-source error states (cafeterias/orders/notifications); failed stats render "—" instead of fake zeros; all-rejected cafeteria-order aggregation surfaces as an error; error branches + banners in Recent Orders / Notifications / Cafeterias sections; student/faculty paths untouched |
| `apps/web/src/app/dashboard/cafeterias/page.tsx` | Flagship: error state, error branch, compact banner, retry, empty title → "No cafeterias found." |
| `apps/web/src/app/dashboard/admin/users/page.tsx` | Error state + branches + banner + retry (client-filtered empty still shows "No users found. Try adjusting your filters.") |
| `apps/web/src/app/dashboard/staff/page.tsx` | Same + removed dead `cafeterias` state and never-rendered `getCafeterias()` fetch |
| `apps/web/src/app/dashboard/orders/page.tsx` | `selectorError` (empty selector never silent) + `loadError` (403 keeps existing accessError; other failures retryable, data kept) + `ordersReloadKey`; JSX quote escape (`&quot;`) fixing 2 lint errors |
| `apps/web/src/app/dashboard/menu/page.tsx` | Three failure states: items (non-403), cafeteria selector, daily menu ("No menu for today yet" now only after a successful response); 403 keeps its amber notice; create-draft button hidden while daily-menu load failed |
| `apps/web/src/app/dashboard/admin/reports/page.tsx` | Fixed silent `.catch(() => {})` **and** the infinite-skeleton bug; `cafeteriasError` renders before the skeleton; `loadError` renders before "No report data"; `cafReloadKey`/`salesReloadKey` retries |
| `apps/web/src/app/dashboard/admin/refunds/page.tsx` | Error state + branches + banner + retry ("No refunds" only after success) |
| `apps/web/src/app/dashboard/admin/overview/page.tsx` | Replaced `catch(() => null / [])` fabricated fallbacks with per-request error states; cafeteria section: compact error / honest "No cafeterias to display." note; `reloadKey` retry |
| `apps/web/src/app/dashboard/inventory/page.tsx` | `loadError` + `cafeteriasError`; 403 keeps access notice; other failures retryable; best-effort menu-name fallback catch kept (documented) |
| `apps/web/src/app/dashboard/notifications/page.tsx` | Error state + branches + banner + retry; mark-read / mark-all-read failures now surface via toast |

### Files deliberately NOT changed

- `apps/web/src/app/dashboard/profile/page.tsx` — read-only display; "save" is a placeholder toast with no API call, hence no silent-swallow and no error-state need (profile editing remains a later phase item).
- Mobile app, student/faculty/staff-portal flows, all backend code, DB schema — out of scope per constraints.
- `changeUserRole` on the users page — broken role-change (missing `cafeteria_id`) is a **P0 Phase 47** item, intentionally not patched here.

---

## 6. Root Cause of the Phase 45 "2 vs 0" Confusion

The backend had cafeterias all along (`GET /cafeterias` returns 2 for admin). The console's failure modes created the contradiction:

1. Overview's `catch(() => [])` fabricated data differently than the Cafeterias page's `catch { setCafeterias([]) }`, so one surface could show a stale/loaded count while the other silently rendered an empty list after a failed (or token-expired) request.
2. With errors swallowed, "request failed", "no permission", "no cafeterias", and "session expired" all looked identical: an empty page.

Phase 46 removes the ambiguity at the presentation layer: **failure, emptiness, and success are now visually and semantically distinct on every page**, and the backend authorization boundary is unchanged.

---

## 7. Validation

### 7.1 Type-check — PASS

`npm run type-check:web` → `tsc --noEmit` **exit 0** (after fixing the local `ApiClientError` binding in `api.ts`).

### 7.2 Lint — PASS (0 errors)

No ESLint configuration existed in the repository, so `next lint` had never run and would prompt interactively. `apps/web/.eslintrc.json` enables `next/core-web-vitals`.

- First run surfaced **2 errors** in `orders/page.tsx` (`react/no-unescaped-entities` on a pre-existing `"{order.note}"` JSX text) → fixed with `&quot;` (identical rendering). All other findings are warnings.
- Final run: **exit 0** — warnings only:
  - `orders/page.tsx` — `ordersReloadKey` flagged as an "unnecessary" useCallback dependency. **Intentional**: the key is the retry mechanism for the orders queue (bumped → loader re-runs). Left as-is with this note.
  - `Avatar.tsx` (`no-img-element`) and `useFetch.ts` (exhaustive-deps) — pre-existing, unrelated to Phase 46 files, not modified.
- Caveat: lint required `NODE_PATH` pointed at `apps/web/node_modules` because the hoisted `eslint-config-next` at the repo root references a parser (`next/dist/compiled/babel/eslint-parser`) that only exists under the workspace's own `next` install. This is a node_modules layout gap from earlier dependency work; fixing it would require dependency changes, which Phase 46 forbids. Lint itself ran fully and passed.

### 7.3 Production build — compiled + type-checked + 24/24 pages generated; one pre-existing environment caveat (honest result)

`npm run build --workspace=apps/web`:

- ✅ **Compiled successfully**; ✅ **lint step (types) valid**; ✅ **"Generating static pages (24/24)"**; `apps/web/out/` regenerated with 22 HTML pages from Phase 46 source (gitignored, as always).
- ⚠️ Exit code 1 from two **pre-existing environment conditions**, both in areas Phase 46 is forbidden to touch:
  1. **Dual React in node_modules** — root `node_modules/react` is **19.2.3** (Expo SDK 57 requirement) while `apps/web/node_modules/react(-dom)` is **18.3.1**. Next's default `/404` and `/500` prerender pulls `styled-jsx` from the root tree and crashes with `Cannot read properties of null (reading 'useContext')`. These are Next's stock error pages — no Phase 46 file participates in their prerender, and every *application* page (including all 11 modified pages) generated successfully.
  2. Next's lockfile auto-patcher fails (`ENOWORKSPACES`) — same pre-existing lockfile/node_modules condition seen by `next dev`; no lockfile bytes were changed (hash verified unchanged, §9).
- The last recorded clean `next build` (`EVIDENCE_FINAL_PRODUCTION_RUNTIME.md`, 2026-09-29, "web build clean / 21 routes") predates the SDK 57 dependency install that created the dual-React layout. Remedying this requires a dependency/node_modules re-layout decision — **explicitly out of Phase 46 scope**; flagged for the roadmap instead.

### 7.4 Manual browser verification — PASS (dev server, admin role)

Dev server on `localhost:3000` (CORS-allowed origin; a stale leftover dev server on 3000 was identified and stopped first; backend left running untouched). All scenarios below were executed live:

| # | Scenario | Result |
|---|---|---|
| 1 | Login `admin@lgu.edu.pk` → dashboard | ✅ Stats 2 / 1 / 0, Recent Orders, Cafeterias quick-view render real data |
| 2 | `/dashboard/cafeterias` success | ✅ Faculty Cafeteria + Student Cafeteria listed |
| 3 | Route-intercept `**/api/v1/cafeterias*` → 500 → reload | ✅ **"Unable to load cafeterias."** + "The server encountered a problem. Please try again." + **Try again** — NOT "No cafeterias found." |
| 4 | Unroute → click **Try again** | ✅ Both cafeterias reload; error state cleared |
| 5 | Spot-check all admin/staff surfaces | ✅ users, staff, orders (selector+queue+tabs), menu (daily menu 2026-10-04 draft), reports (Rs 1,800 revenue stats), refunds (genuine "No refunds"), overview (TOTAL USERS 12, ORDERS 47), inventory (real stock rows), notifications (genuine empty) — all success states with real data |
| 6 | Reports page: intercept `**/api/v1/reports**` → 500 → reload | ✅ "Unable to load sales report." + retry — **infinite-skeleton bug fixed** (no endless skeleton, no fake "No report data") |
| 7 | Dashboard home: intercept notifications → 500 → reload | ✅ Unread stat shows **"—"** (honest) + compact "Unable to load recent notifications." banner + retry, while Recent Orders / Cafeterias sections keep rendering real data (error+data pattern) |
| 8 | Sign out via sidebar | ✅ Redirects to `/login?redirect=%2Fdashboard` |
| 9 | Poison `sessionStorage.uniserve_refresh_token` with garbage → reload `/dashboard` | ✅ Silent refresh fails → clean redirect to login — **no broken authenticated-looking state** (auth investigation conclusion confirmed live) |

Console noise during tests: routine 401s on `/auth/me` are the normal silent-refresh cycle before token refresh; they resolve automatically after login.

---

## 8. Git / Dependency / Database Status

| Item | Status |
|---|---|
| **HEAD unchanged** | **YES** — `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` on `main` |
| **Commit created** | **NO** |
| **Push performed** | **NO** |
| Staged files | **0** |
| `git diff --check` | exit 0 (only a pre-existing CRLF notice on `apps/mobile/package.json`) |
| `package-lock.json` sha256 | `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A` — **identical to the Phase 45 baseline**; `package-lock.json.sdk51-backup` present. (The file shows `M` vs HEAD — that is the pre-existing baseline state from earlier SDK-57-era phases; Phase 46 did not write it.) |
| **Dependency changes** | **NONE** — no package.json edits, no installs. `apps/web/.eslintrc.json` is lint configuration only. |
| **Database changes** | **NONE** — no schema, migration, or data changes. |
| Historical reports | Pre-existing deletions of PHASE_22–41 files are the unchanged Phase 45 baseline (20 `D`); PHASE_43/44/45 reports remain untracked and unmodified; no historical report content touched by Phase 46. |
| Build artifacts | `apps/web/out/` + `.next/` regenerated locally; both gitignored (`.gitignore` lines 56–57) — never appear in git status. |
| Deployment | **NOT performed** (build artifacts are local only; Caddy/Docker untouched). |

### Phase 46 source-change summary (vs Phase 45 baseline porcelain 62 → now 70)

- New: `apps/web/src/components/ui/LoadErrorState.tsx`, `apps/web/.eslintrc.json` (+ this report when written).
- Modified: `apps/web/src/lib/api.ts` and 11 dashboard pages listed in §5. All other `M`/`??`/`D` entries are the pre-existing baseline from earlier phases (mobile SDK 57 work, backend Phase 43/44 work, historical report deletions) — untouched this phase.

---

## 9. Intentional Non-Changes (documented, not defects)

1. **Access-token persistence** — unchanged (§3): secure-by-design XSS mitigation.
2. **`getMyCafeterias()` catch → `[]`** in `api.ts` and dashboard home — assignment-*hint* fallback for selector scoping, not a displayed dataset; scoped endpoints still enforce 403, which pages surface explicitly.
3. **`changeUserRole` missing `cafeteria_id`** — P0 **Phase 47** scope; not patched in a foundation phase.
4. **Middleware dead in static export** — pre-existing Next `output: export` limitation (visible in dev logs); routing is enforced client-side by `RoleGuard`; out of scope.
5. **`ordersReloadKey` lint warning** — intentional retry dependency (§7.2).
6. **Build-time dual-React prerender failure on `/404`,`/500`** — pre-existing node_modules condition from the SDK 57 install; flagged, not fixed (dependency changes forbidden).
7. **`apps/web/out` regeneration** — local gitignored artifact refresh required by the mission's build check; not a deployment.

---

## 10. Remaining Phase 45 Gaps — NOT Solved Here (carry forward)

P0 (Phase 47+): no create-member UI; role-change broken (missing `cafeteria_id`); no assignment display/reassign UI; no cafeteria-create UI; image upload workflow absent end-to-end.
P1: reports 1/12 wired; refund reject endpoint+UI missing; no admin broadcast; settings placeholder; profile edit; menu-item delete UI; copy-previous-day; web UI test suite; audit-log surface; staff page manager listing/add-staff; inventory low-stock surfacing.
P2: admin home order-aggregation semantics (admin has no assignment → windowed GET /orders); pagination; orphan favorites route; hardcoded version; test-data hygiene.

**Roadmap unchanged:** Phase 46 (this) → **Phase 47 — Member & Staff Management (P0)** → 48 Cafeterias → 49 Menu+Image → … Phase 47 not started; this phase stops here per instruction.

---

## 11. Sign-off

Phase 46 complete: the admin console now fails loudly and honestly — every request failure renders an explicit, retry-aware error state; genuine emptiness is only ever claimed after a successful response; authentication failures fail closed to login; and all of it was verified against the live system, not just the compiler. The foundation the remaining product gaps will be built on is in place.
