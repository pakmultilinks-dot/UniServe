# PHASE 61 — Post-Phase-60 Stability & Release Readiness Audit

**Type:** Investigation-only audit (no source, test, dependency, configuration, or product-data changes permitted).
**Date:** 2026-10-07
**Git HEAD (start = end):** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (`main`, "fix: close Phase 42 product acceptance defects")
**Audit question:** *Is UniServe currently stable and coherent enough to proceed toward final presentation/release preparation, and what genuinely blocks that?*

**DECISION: NOT READY**

*(A single P1 defect was found in the deployed runtime — see §21 F-61-01 and §22. All repository-level gates are green; the blocker is deployed-artifact drift, remediable by an operational image rebuild/redeploy — not an implementation phase. After F-61-01 is remediated and re-verified, the system moves to "READY WITH KNOWN LIMITATIONS" territory; no P0 exists.)*

---

## 1. Mission

Phase 61 is a strictly read-only stability and release-readiness audit of the UniServe LGU Cafeteria Platform as it stands after Phase 60 (Operations Hardening & Test-Net Completion). It re-executes every regression gate, probes the live environment, inspects operational tooling and data hygiene, evaluates demo paths, and issues a single release-readiness verdict with an itemised findings table. It does **not** fix anything, does **not** start Phase 62, and does **not** perform a product-feature audit. Per mandate, legitimate retained rows (sessions, audit events, history, intentionally retained fixtures) are not treated as corruption.

## 2. Baseline

| Item | Value |
|---|---|
| Git HEAD | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (branch `main`) |
| Dirty entries at start | **156** (20 deleted / 78 modified / 58 untracked), staged = 0 |
| `package-lock.json` SHA-256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` (snapshot saved pre-audit) |
| Backend `app/**/*.py` mtimes | 80 files snapshotted pre-audit (`$env:TEMP\phase61\mtime_before.txt`) — ruff auto-fix trap detection |
| Live API (container) | `uniserve_api` on host port **8000** (healthy) |
| Live database | `uniserve_postgres` host 5433→5432, PG 16.14, DB `uniserve_prod`, user `uniserve` |
| Duplicate API process | Host `uvicorn` pid **4772** on port **8001** (leftover probe-era process; healthy but unreferenced by any client config) |
| Web dev server | port **3000** (restarted during audit — see §13) |
| Prior baseline (Phase 59) | P0=0 / P1=0 / P2=2 / P3=13; sessions 360/221 active; stale pending payments 19; webhook unprocessed 1; itemless cancelled orders 3; duplicate daily menus 2; E2E cafeteria active; dietary 3/35, allergens 2/35 |

**Safety posture:** zero source/test/dependency/config edits, zero migrations, zero product-data mutations, zero commits/pushes/deployments, zero tree cleanups. All integration testing confined to the disposable `uniserve_test_p60` database with an explicit env gate. All ops scripts executed only in their documented dry-run (default) modes. Secret values are never printed in this report; runtime DB credentials are passed only via transient environment variables.

## 3. Backend regression (§5 of mandate)

| Gate | Command | Result |
|---|---|---|
| Ruff (lint) | `python -m ruff check --no-fix app` (from `apps\api`) | **"All checks passed!" — 0 errors** (exit 0) |
| Full pytest | `python -m pytest tests/ -q --tb=short` | **872 passed, 5 skipped** in 474.35s |
| Independent confirmation rerun | same command | **872 passed, 5 skipped** in 467.66s |

The first background run's final output was lost to terminal cleanup before capture; the suite was re-run to completion twice (both runs green, zero failures). Skip count (5) matches Phase 60 exactly (integration module gated off by default). `ruff check app` (without `--no-fix`, which would auto-fix under `pyproject` `fix=true`) was never executed. The pre-audit mtime snapshot compared byte-identical post-audit (§24) — no file was touched by lint tooling.

## 4. Web regression

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | **0 errors** (exit 0) |
| `npx vitest run` | **8 test files, 40/40 tests passed** |
| `npx eslint . --ext .ts,.tsx` | **0 errors, 95 warnings** (exit 0) |

Warning classification (all pre-existing Phase-59/60 baselines, none release-blocking): legacy `any` usage in the API client (`api.ts`); `set-state-in-effect` / purity suggestions in a small number of components — future hygiene work, not defects. Tests assert user-observable behaviour (error states, retry flows, edit-mode persistence) with fetch mocked at the network boundary.

## 5. Mobile regression

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | **0 errors** (exit 0) |
| `npx jest --runInBand` | **6/6 suites, 34/34 tests passed** (clean rerun) |
| `npx eslint src --ext .ts,.tsx` | **0 errors, 61 warnings** (exit 0) |

Transient observation (not a defect): during one full-suite run executed *concurrently with the backend pytest run*, `auth-context.test.tsx` timed out at 39.0s (vs 6.9s isolated) — a cold-start/resource-contention flake on this 8 GB host. The suite passed 6/6 in isolation, and the full suite passed 34/34 immediately after the backend run finished. Recorded as F-61-14 (P3). Lint warnings are the documented baseline (12 auto-fixable hygiene items).

## 6. Shared-types

`npx vitest run --root packages/shared-types` → **1 test file, 13/13 passed** (refresh/error-semantics coverage intact from Phase 60).

## 7. PostgreSQL integration

| Step | Evidence |
|---|---|
| Identity proof (pre-run) | Live container: `uniserve_prod` / user `uniserve` / PostgreSQL 16.14 |
| Gate env | `UNISERVE_INTEGRATION_PG=1`, `POSTGRES_DB=uniserve_test_p60`, `POSTGRES_PASSWORD=<runtime>` (transient env; never printed) |
| Disposability | conftest (code-read) hard-rejects `uniserve_prod` and any DB not named `uniserve_test*`; creates/drops only the disposable DB |
| Result | **5/5 passed in 14.87s** — disposable-and-migrated, auth-login-refresh-reap, unique-jti, payment-reconciliation, webhook-idempotency |
| Post-run | All three env vars cleared and verified absent |

The first integration test additionally asserts `current_database()` starts with `uniserve_test` and is not `uniserve_prod`/`uniserve_dev` — defense-in-depth inside the test itself, not only in fixtures.

## 8. Operational dry-runs (ops scripts vs live DB)

**First attempt (repo-local `.env` defaults):** all three scripts printed `[mode=DRY-RUN (no changes)]` and their target identity (`localhost:5433 / uniserve_dev / app_env=development`), then **failed closed** with `InvalidPasswordError` — the repo-local `.env` carries a stale dev password that no longer matches the runtime container. No query ran, no mutation possible. This is F-61-12 evidence and demonstrates the scripts' identity-first + fail-closed safety design.

**Second attempt (runtime env overrides: host/port/user/db/password via env vars):** all three scripts printed target `uniserve_prod` correctly:

| Script | Dry-run summary |
|---|---|
| `python -m scripts.reap_sessions` | `revoked_deleted=0, stale_active_deleted=0, total_deleted=0, dry_run=true` — no session rows currently eligible under default grace windows (revoked >7d, dormant-active > refresh+1d) |
| `python -m scripts.reconcile_payments` | `scanned=27` (pending/processing >24h), `order_cancelled_payments_closed=19`, `completed_cash_payments_confirmed=0`, `untouched=8` (online PROCESSING rows awaiting provider — deliberately never auto-succeeded), `dry_run=true` |
| `python -m scripts.fixture_hygiene` | E2E cafeteria rule report-only; duplicate daily-menu groups = **2** (Faculty 287038a2 @2026-10-04 rows=5; E2E 50d67d4b @2026-10-07 rows=2); R6 census `live_prefix_email_count=0`, non-active = pending_verification 4 + suspended 3 (pattern mismatch — F-61-05) |

**No-mutation proof (post-dry-run psql):** sessions **360** total / **221** active, payments pending+processing **27** — byte-identical to pre-dry-run counts.

## 9. Database integrity

Read-only sweep against `uniserve_prod` (10 orphan-FK checks across orders→users/cafeterias, payments→orders/users, notifications→users, user_sessions→users, carts/cart_items, daily_menus, refunds, audit events, etc.): **all 0 orphans**. Completed orders without payment rows: **0**. Refunds exceeding captured amounts: **0**. Security audit events: **798** rows, **0** orphans (retained history — not corruption).

Distribution snapshot: orders **52** (completed 9 / cancelled 32 / pending 10 / ready 1); payments succeeded **11** / refunded **1** / pending+processing **27**; users **18** (active 11 / pending_verification 4 / suspended 3); roles student 10 / staff 3 / manager 2 / faculty 2 / admin 1; notifications **148** by type (order_created 49, order_cancelled 26, order_confirmed 18, **admin_announcement 14**, …); audit 798; email domains only `student.lgu.edu.pk` + `lgu.edu.pk`; cafeterias 3/5 active (incl. retained E2E fixture `50d67d4b…`). **No corruption found.** The only drift vs Phase 59 is the stale-pending-payment count 19→27 (F-61-04).

## 10. Auth/authorization

- **Code inspection (reap safety):** `auth/service.py::reap_sessions` deletes only (a) revoked sessions past the revoked-grace window and (b) dormant-active rows past refresh-expiry+inactive-grace, with `protect_session_id` exclusion and dry-run returning counts only. It **cannot delete active sessions**.
- **Live sanity:** admin login via API succeeded; admin session rendered the full admin dashboard with live data (§22). Unauthenticated access to `/api/v1/notifications` → 401 (correct); `/api/v1/menu-search/` → 401 unauthenticated (auth-gated by design). Backend suite (872) includes the full auth/token/refresh/reap coverage.
- **Web RBAC note (retained design fact):** client-side nav gating with server-enforced data access — data endpoints gate authorisation server-side regardless of UI state.

## 11. Phase 58 regression

No Phase-58 endpoint or behaviour regressions observed. Phase-58-era probe users remain in the DB as active low-privilege student accounts (`phase58.probe…`) — harmless residue, not corruption. The 8001 host uvicorn (F-61-11) originates from that era and is unreferenced. Backend suite covers the Phase-58 acceptance surface.

## 12. Phase 53–56 regression

Order workflow, pickup/no-show, scheduled orders, reporting, and administration surfaces all respond correctly live (dashboard/orders/reports data render with correct statuses; dry-run reconciliation classifies exactly the expected stale populations; duplicate-menu and itemless-order populations match the Phase-59 retained baselines). The Phase-56 E2E cafeteria is still present and active (retained fixture — visible in the admin cafeteria list). Backend + web + mobile suites carry the Phase-53–56 acceptance tests forward.

## 13. Build/export validation

| Build | Result |
|---|---|
| `npx next build` (apps/web) | **Exit 1 — dual-React known baseline reproduced exactly:** compilation succeeds, all 26 static pages generate, then prerender of `/404` and `/500` fails with `TypeError: Cannot read properties of null (reading 'useContext')` (styled-jsx `StyleRegistry` under duplicate React copies: root `node_modules/react` vs `apps/web/node_modules/react-dom`). Secondary non-fatal "Failed to patch lockfile" (ENOWORKSPACES) warning. **Matches the documented pre-existing baseline** — not a Phase 61 regression, but blocks the static-web production build path until React hoisting is deduplicated (F-61-03). |
| `npx expo export --platform web` (apps/mobile) | **Exit 0 — success.** Web bundle 1.9 MB exported to `dist/` (git-ignored artifact, left in place per no-cleanup rule). |

**Side-effect management (documented honestly):** the mandated `next build` overwrote `apps/web/.next` (shared with the running dev server), causing `Cannot find module './997.js'` 500s on port 3000. The dev server was restarted (environmental process restart only — no source/config changes) and the demo environment was **verified restored**: dashboard renders with live admin session and real order/cafeteria data. The dev server's startup warnings (rewrites/middleware vs `output: export`, lockfile patch) are identical to the morning's original dev-server log — pre-existing dev noise.

## 14. Dependency integrity

- `package-lock.json` SHA-256 at audit end: **`3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8`** — **identical** to the pre-audit snapshot. Zero dependency changes this phase. (Differs from Phase 59's hash only because Phase 60 legitimately added devDependencies — expected, documented.)
- `pip check`: **"No broken requirements found"** (exit 0); venv = 72 packages.
- Stack coherence: root `package.json` is workspaces-only; Expo SDK 57 (`expo ^57.0.26`, `expo-router ~57.0.24`, `jest-expo ~57.0.0`, React 19.2.3, RN 0.86.3) internally aligned; shared-types consumed by both apps.

## 15. Environment/configuration

Env files inventoried by **key name only** (no values/secrets printed):

- `apps/api/.env` (dev-local): APP_*, POSTGRES_*, JWT_*, CORS_ORIGINS, LOG_* — **stale**: points at dev DB name with an outdated password; runtime container env is authoritative ("runtime env wins" — F-61-12, demonstrated in §8).
- `.env.production` / `.env.production.example` (root): full production key set incl. no-show/refund/pickup policy keys.
- `apps/web/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` — **coherent** with the container API on 8000 (non-secret public value).
- Container CORS env verified live: `CORS_ORIGINS` includes `http://localhost:3000`; the API echoes `Access-Control-Allow-Origin: http://localhost:3000` + `Allow-Credentials: true` on responses to Origin'd requests (verified empirically — the browser console's "blocked by CORS" messages for notifications are a **misleading symptom of the 500**, not a CORS misconfiguration).
- `docker-compose.yml` dev defaults (`POSTGRES_DB: uniserve_dev`, internal 5432) diverge from the running live container (`uniserve_prod`, host 5433) — runtime env overrides, documented coherence note for release planning (F-61-15).
- Duplicate API listener: host uvicorn on 8001 (F-61-11) — no client references it.

## 16. API sanity

- **Route inventory:** via OpenAPI schema (TestClient, local debug): **99 paths / 111 operations**, spanning all 17 registered routers (health, auth, users, cafeterias, menu-items, daily-menus, inventory, favorites, menu-search, carts, orders, payments, refunds, notifications, reports, administration). No duplicate path+method pairs; naming conventions consistent within each module. (FastAPI ≥0.146 lazy-router internals (`_IncludedRouter`) make static `app.routes` enumeration return wrappers — enumerated through the OpenAPI schema instead; documented tooling note.)
- **Trailing-slash observation:** collection routes under `/cafeterias/…`, `/orders/`, `/payments/`, `/favorites/`, `/menu-search/` carry trailing slashes while `/health`, `/notifications`, `/users/` do not. FastAPI `redirect_slashes` handles both; the known probe-harness gotcha (307 drops POST bodies in some clients) applies to hand-rolled probes only — the web/mobile clients use exact paths and are unaffected (live-verified).
- **Live unauthenticated probes (port 8000):** `/api/v1/health` → 200 `{"status":"healthy"}`; `/api/v1/health/ready` → 200 `{"database":"connected","schema":"present"}`; `/api/v1/notifications?limit=5` authenticated → **500** (F-61-01); `/api/v1/notifications/unread-count` authenticated → **200** (counts work; row hydration does not).

## 17. Test quality

Sampled three representative suites (read-only):

- **Web `web-api-client.test.ts`:** asserts token lifecycle and query-shaping behaviour through a fetch-mocked client; reset via `logout()` finally-block + `sessionStorage.clear()` + `vi.unstubAllGlobals()` — genuine isolation/cleanup discipline.
- **Mobile `auth-context.test.tsx`:** asserts provider-observable behaviour (cold start, password/PIN login persistence, logout clears local state even on server failure, session-expiry hook); mocks at the service boundary with typed `jest.Mocked` — appropriate mocking level, not implementation-coupled.
- **Integration `test_postgres_integration.py`:** gate-guarded (`skipif` off by default), disposable-DB assertions *inside the test body* (`startswith("uniserve_test")`, not in {prod, dev}), alembic-version proof — defense-in-depth.

**Verdict:** the suites assert real behaviour at correct boundaries with proper cleanup. One structural gap enabled F-61-01 to hide behind green suites: gates exercise **repository source**, never the **deployed container image** nor image-vs-database-content compatibility (F-61-02).

## 18. Operational safety

- All three ops scripts: dry-run by default (`--execute` required), print target DB identity first, fail closed on stale credentials (demonstrated live in §8).
- `reap_sessions` service logic: cannot delete active/protected sessions (code-verified).
- `reconcile_payments` service logic: only classifies PENDING/PROCESSING; cancelled-order→CANCELLED; completed+cashing→SUCCEEDED; online PROCESSING deliberately untouched — **never invents online successes**.
- `fixture_hygiene`: E2E cafeteria rule = deactivation-only; orders/daily-menus/users rules report-only — **cannot delete business data**.
- Integration conftest: gate-required, `uniserve_prod` hard-reject, disposable-DB-only lifecycle.
- Audit itself: read-only throughout; `ruff --no-fix` only; integration env cleared; no commits, no deploys, no tree cleanups.

## 19. Data hygiene

No corruption. Retained-by-design populations (documented, not defects): sessions 360/221 (stateless-JWT tolerates; 0 currently reaped-eligible); audit events 798; itemless cancelled orders 3; duplicate daily-menu rows 2 groups; webhook unprocessed 1 (awaiting provider); E2E cafeteria active; dietary 3/35 + allergen 2/35 sparsity (menu-completeness limitation, F-61-10).

Hygiene gaps (all P3, non-destructive): stale pending payments 19→27 (F-61-04); fixture-census pattern mismatch (F-61-05); test-flavour residue accounts visible in the user list — `pending_verification` ×4 (`phase37.*`, `test.student4*`) and `suspended` ×3 (`p47.*`) (F-61-16). Active demo accounts cover all five roles cleanly (students `ayesha.khan`/`bilal.hussain`/`fatima.raza@student.lgu.edu.pk`, faculty `dr.*@lgu.edu.pk`, staff `ahmed.raza@`, manager `sana.malik@`, admin `admin@lgu.edu.pk`).

## 20. Demo readiness

**Verified live in the browser (admin session, localhost:3000):**

- ✅ **Dashboard:** greeting + role identity render; stats (3 cafeterias / 3 active orders); Recent Orders list with **real live data** (#54 cancelled, #53 cancelled, #52/#49/#48 pending — matches DB exactly); cafeteria cards incl. Faculty, Student, and the retained E2E cafeteria.
- ✅ **Order Queue page:** cafeteria combobox (all 3), status filters (pending/preparing/ready/completed/cancelled), date filter — renders and queries correctly.
- ❌ **Notifications (dashboard widget + full page):** **broken** — "Unable to load notifications / Unable to reach the server" states; API returns **500** (F-61-01). The unread-count endpoint works (badge/counts), row listings do not.
- **Manager/faculty/student paths:** covered by the automated suites (web 40 + mobile 34 incl. role-gating and dashboard-gate tests) and by data presence (all roles active with real orders/menus); a full multi-role browser walkthrough was not performed beyond the admin path because the notifications P1 already blocks the notifications segment and the audit is read-only.
- **Demo credentials convention:** committed test-fixture scripts (`scripts/create_live_accounts.py`, `scripts/seed_realistic_data.py`, `scripts/reset_test_passwords.py`) document the demo login convention (seeded users use the shared test password; admin uses its seeded admin password) — referenced here by script, not by value.
- **Environment:** demo env restored after the build side-effect (§13) and re-verified with live data.

**Demo verdict:** core ordering/administration demo paths are presentation-ready; the notifications walkthrough will fail until F-61-01 is remediated.

## 21. Findings

| ID | Area | Sev | Finding | Evidence | Impact |
|---|---|---|---|---|---|
| F-61-01 | Runtime/deployed artifact | **P1** | **Deployed API image is stale vs repository source → notifications listing crashes.** The container image (created 2026-10-04) lacks `ADMIN_ANNOUNCEMENT` in its `NotificationType` enum, while repo source (`notifications/models.py`) includes it (Phase 50). 14 prod rows carry `notification_type='admin_announcement'` (inserted 2026-10-05..06 by host-side verification scripts running current source). Hydrating those rows raises `LookupError: 'admin_announcement' is not among the defined enum values` → `GET /api/v1/notifications` → **500** (empirically proven with an admin session: `limit=5` → 500 "Internal Server Error"; `unread-count` → 200). Browser-verified: admin dashboard notifications widget + notifications page show failure states. Container logs show the enum LookupError traceback live. Core ordering/checkout unaffected. **Remediation (operational, not an implementation phase):** rebuild `uniserve-prod-api` image from current source, redeploy container, re-verify notifications listing → expect 200. | §8/§16/§20; container logs; authenticated probe; browser snapshots | Notifications feature non-functional in the deployed runtime; demo-blocking on the admin landing dashboard; any release cut from the current image ships this defect |
| F-61-02 | Test strategy | P2 | No gate validates the **deployed image** or image-vs-database enum compatibility — all 872+40+34+13+5 tests exercise repository source; F-61-01 passed every green suite | §17 sample reads; F-61-01 contrast | Deployment drift can hide behind perfect CI; recommend an image-vs-DB smoke check in release pipeline (future work) |
| F-61-03 | Web production build | P2 | `next build` fails (exit 1) on `/404`+`/500` prerender — dual-React `useContext` null (root `react` vs `apps/web/react-dom`), the documented known baseline; `output: export` + middleware/rewrites warnings compound the static-export path | §13 build log | Static web production build/deploy path blocked until React hoisting deduplicated; dev runtime + all tests unaffected |
| F-61-04 | Payments ops | P3 | Stale pending/processing payments **19 → 27** since Phase 59; reconcile dry-run classifies 19 closable-to-cancelled + 8 PROCESSING untouched-by-design; script provided, not executed (read-only mandate) | §8 dry-run | Operational cleanup pending ops execution; no money integrity violation (succeeded=11 consistent, 0 integrity violations) |
| F-61-05 | Ops tooling accuracy | P3 | `fixture_hygiene` R6 census pattern `live.%` matches **0** of the actual 7 non-active fixture accounts (real emails use `firstname.lastname@` / `phase*` / `test.*` / `p47.*` patterns) — script under-reports; report-only rule so no destructive risk | §8 R6 output; §19 user inventory | Tooling accuracy gap; census should be widened before relying on R6 in ops |
| F-61-06 | Data hygiene | P3 | E2E fixture cafeteria `50d67d4b…` ("Phase 56 E2E Cafeteria") still **active** and visible in the demo UI; cleanup script provided, ops decision pending | §9; §20 dashboard | Cosmetic demo clutter; retained-by-design until ops executes deactivation |
| F-61-07 | Data hygiene | P3 | Duplicate daily-menu rows retained: 2 groups (Faculty 2026-10-04 rows=5; E2E 2026-10-07 rows=2) — report-only rules by design | §8 R3 | Demo/menu-display edge case; not blocking |
| F-61-08 | Data hygiene | P3 | Itemless cancelled orders ×3 (#44/45/47) retained — report-only by design | Phase 59/61 sweeps | Historical test artifacts; non-blocking |
| F-61-09 | Auth ops | P3 | Sessions 360 total / 221 active un-reaped; dry-run shows **0** currently eligible under default grace windows (all rows younger than windows) | §8 dry-run | Expected stateless-JWT posture; reaper will act as rows age |
| F-61-10 | Menu data | P3 | Dietary tags 3/35 and allergens 2/35 — menu metadata sparse for richness demos | §9 | Demo narrative limitation; data-entry backlog |
| F-61-11 | Environment | P3 | Stale host `uvicorn` (pid 4772) still listening on **8001** from the probe era; healthy but unreferenced (web `.env.local` → 8000) | §2 process/netstat | Environment hygiene; stop before presentation to avoid confusion |
| F-61-12 | Configuration | P3 | Repo-local `apps/api/.env` targets dev DB with stale password — ops scripts fail-closed against it; runtime env overrides required (demonstrated working pattern) | §8 first-attempt logs | Documented "runtime env wins" lesson; runbook should mandate env-override pattern for live ops |
| F-61-13 | Lint debt | P3 | Warning baselines retained: web **95 warnings** / mobile **61 warnings** (0 errors both) | §4/§5 | Documented hygiene backlog; non-blocking |
| F-61-14 | Test stability | P3 | Mobile `auth-context` suite cold-start timeout (39s vs 6.9s) when run concurrently with backend pytest on this host — environmental flake; passes 6/6 isolated and 34/34 in clean full run | §5 | Do not run heavy suites concurrently on low-RAM hosts; no product impact |
| F-61-15 | Deployment config | P3 | `docker-compose.yml` dev defaults (`uniserve_dev`, internal 5432) diverge from the running live container (`uniserve_prod`, host 5433, runtime env) | §15 | Release-planning coherence item; runtime is correct, compose file is dev-oriented |
| F-61-16 | Demo polish | P3 | Test-flavour residue accounts visible in live user list: `pending_verification` ×4 (`phase37.student*`, `test.student4*`), `suspended` ×3 (`p47.*`), probe users (`phase58.probe*`, `p53.e2e`, `p55.recovery`) | §19 inventory | Harmless for demos (active accounts cover all roles) but unpolished if the user/admin list is shown |

**Severity counts: P0 = 0 · P1 = 1 · P2 = 2 · P3 = 13.**

## 22. Release-readiness decision

# **NOT READY**

**Rationale:** One **P1** defect is open in the deployed runtime (F-61-01): the notifications feature — visible on the admin landing dashboard and as a full page — returns HTTP 500 in the running container because the deployed image predates the repository's notification-enum state while the production database already contains rows requiring it. Presenting or releasing the system in this state would fail product acceptance on a user-visible feature path.

**What is NOT blocking:** there is no P0. Every repository-level gate is green (backend 872/5 + ruff 0; web 40/40 + tsc 0 + eslint 0E; mobile 34/34 + tsc 0 + eslint 0E; shared-types 13/13; integration 5/5 on a provably disposable DB; pip check clean; lockfile untouched). Database integrity is sound (0 orphans everywhere checked). Core ordering, checkout, payments, administration, and reporting paths render and behave correctly live. The web production-build failure (F-61-03) is a documented pre-existing baseline that affects only the static-web deploy path, not the running dev/demo runtime.

**What genuinely blocks:** the deployed API image must be rebuilt from current source and redeployed (operational action, hours not sprints), after which `GET /api/v1/notifications` must be re-verified (expect 200 with the 14 `admin_announcement` rows hydrating) and the dashboard notifications widget re-checked in the browser. Once F-61-01 is closed and re-verified, the system qualifies as **READY WITH KNOWN LIMITATIONS** (P2/P3 findings documented above remain as known limitations and pre-release hygiene items).

## 23. Final recommendation

1. **Remediate F-61-01 operationally (the only P1):** rebuild the `uniserve-prod-api` image from the current source tree (`bc967b3` + working tree), redeploy the `uniserve_api` container with the existing runtime environment, then re-verify: (a) authenticated `GET /api/v1/notifications?limit=50` → 200 with `admin_announcement` rows hydrating, (b) admin dashboard widget renders the notification list, (c) container logs show no enum `LookupError`. This is a deployment-refresh action — **not** a new implementation phase.
2. **Then proceed with release-preparation activities** (demo preparation, presentation rehearsal, deployment planning per `DEPLOYMENT_RUNBOOK.md`/`DEPLOYMENT_ARCHITECTURE.md`) — **not Phase 62**. P0=P1 will be 0 after step 1; no further implementation phase is warranted by this audit.
3. **Pre-demo hygiene (P3, opportunistic):** stop the stale 8001 uvicorn (F-61-11); optionally execute `reconcile_payments --execute` after review (F-61-04) and the fixture-hygiene E2E cafeteria rule (F-61-06); schedule the web dual-React fix (F-61-03) as a pre-deployment work item; add an image-vs-DB smoke check to the release pipeline (F-61-02); polish or hide residue accounts if user lists appear in the demo (F-61-16).
4. **Do not** start Phase 62, do not modify product code in response to this audit, and do not treat any retained session/audit/history/fixture row as corruption.

## 24. Git integrity

| Check | Result |
|---|---|
| HEAD (end) | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` — **identical to start** |
| Branch | `main` |
| Dirty entries (pre-report write) | **156** (20 D / 78 M / 58 ??) — **identical to start**; after this report file: 157 with `PHASE_61_…AUDIT.md` as the only addition |
| `package-lock.json` SHA-256 (end) | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` — **identical to pre-audit snapshot** |
| Backend `app/**/*.py` mtimes (80 files) | **0 differences** vs pre-audit snapshot — no lint auto-fix, no source edits |
| Commits / pushes / deploys | **None** (HEAD unchanged; no commit, no push, no deployment executed) |
| Tree cleanups / resets / stash | **None** |
| Migrations created / DB product data modified | **None** |
| Build artifacts | `.next` (failed prod build, known baseline) and `apps/mobile/dist` (successful expo export) — git-ignored, left in place per no-cleanup mandate; dev server restarted to restore the demo environment (§13) |
| Integration env vars | Set only during §7, cleared and verified absent afterwards |
| Secrets in this report | None (runtime DB credentials passed only via transient env; demo credentials referenced by script name only) |

**Read-only compliance: fully verified.** Phase 61 ends exactly one new file: this report.

---

*End of Phase 61 report — decision: **NOT READY** (single P1: F-61-01 deployed-image drift breaking live notifications; remediation = operational image rebuild/redeploy + re-verify; after which: READY WITH KNOWN LIMITATIONS → demo prep / rehearsal / deployment planning. No Phase 62.)*
