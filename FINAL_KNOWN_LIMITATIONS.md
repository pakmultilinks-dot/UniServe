# FINAL KNOWN LIMITATIONS — UniServe

**Phase:** 62 — Demo Readiness, Rehearsal & Final Release Checklist
**Date:** 2026-10-08
**Scope:** Living register of accepted limitations as of demo-readiness sign-off. This is the **final** limitations document for the current release cycle; it supersedes ad-hoc limitation notes scattered across phase reports for demo purposes. Classification legend:

| Class | Meaning |
|---|---|
| **P** — Product limitation | Behaviour of the shipped code/data model itself. Acceptable for demo; may need product work later. |
| **D** — Demo / environment hygiene | Test residue or local-environment condition. Not product behaviour; cleanable later without code changes. |
| **F** — Future enhancement | Not a defect — a deliberate scope cut or post-release idea. |

**Demo-visibility note:** items marked ⚠ can appear on screen during the scripted demo. They are cosmetic/data-hygiene only — no item below breaks any demo flow (all flows were rehearsed green in Phase 62).

**Closed finding (not carried):** F-61-01 (production image ↔ DB enum drift → notification insert 500) was **resolved in Phase 61A** via image rebuild + API-only redeploy (report: `PHASE_61A_DEPLOYED_API_RUNTIME_REMEDIATION.md`). It is closed and deliberately not resurrected here.

**Adjudications honored (not resurrected):** Phase 57's single P1 (default-path inactive cafeterias) closed by Phase 58 (51/51 probes, 853 tests). Phase 59 retired its false-positive rows. Prior-phase closed findings stay closed.

---

## Register (carried from Phase 61 audit; re-verified status in Phase 62)

### F-61-02 — Image ↔ DB drift gate is manual
- **What:** No automated preflight that the running API image supports the deployed DB schema (the Phase 61A failure class: 15-value enum image vs 13-value DB, and its converse).
- **Class:** **P** (process gap around deployables)
- **Status:** Open by design of current tooling; Phase 61A remediation added the manual rebuild recipe to `FINAL_LOCAL_RUN_GUIDE.md` §6.
- **Demo impact:** None — current image (built 2026-10-07T20:16:41Z, digest `sha256:f4e14ce5…`) supports the 15-value enum; `/health/ready` 200; 0 LookupErrors since remediation.

### F-61-03 — Dual-React `next build` failure (F-61-03 family)
- **What:** `npx next build` from `apps/web` fails on the dual-React resolution (root `react 19.x` vs web `react 18.2`) — static-web export path is blocked in this monorepo checkout.
- **Class:** **P** (build-toolchain limitation, dev-server unaffected)
- **Status:** Open; explicitly out of scope for demo (dev server is the demo surface). Blocks only `output: export`-style static deployment from this checkout — Docker/nginx deployments serve the dev-compatible app via Caddy + API containers per `docker-compose.prod.yml`.
- **Demo impact:** None — demo runs `npx next dev` (verified serving 200s). **Do not run `next build`.**

### F-61-04 — Stale pending payments (27 rows → 3 online-pending orders)
- **What:** Phase 50-era payment rows left `pending` in DB; re-checked in Phase 62: **3 orders** remain `payment_method=online, status=pending` (orders #48/#49/#52, all Student Cafeteria, PKR 80 each, from Phase 50 E2E seeding), with one linked refund request pending admin triage (order #52).
- **Class:** **D** (test residue in live DB)
- **Status:** Open; cleanable later via admin refund adjudication + data cleanup — no code change needed.
- **Demo impact:** ⚠ Visible in refunds console as a pending row and in orders console as pending online orders. Not a functional defect — payment/refund states are internally consistent (order #48 has a succeeded payment + rejected refund; #49 rejected refund; #52 pending refund).

### F-61-05 — `fixture_hygiene` R6 pattern
- **What:** E2E fixtures still rely on the R6 hygiene pattern (seeded probe accounts/cafeterias kept for test continuity) rather than full teardown.
- **Class:** **D**
- **Status:** Open by policy — Phase 10 constraint prohibits data resets/deletes; residue is preserved deliberately.
- **Demo impact:** ⚠ Contributes to visible residue items below (F-61-06, F-61-16).

### F-61-06 — "Phase 56 E2E Cafeteria" active and student-visible
- **What:** A test cafeteria (`50d67d4b-…`, type `student`) is `is_active=true` with live menus (draft + archived daily menus for 2026-10-07) — appears in cafeteria lists/dropdowns for students.
- **Class:** **D**
- **Status:** Open; re-confirmed in Phase 62 (visible in admin browser, student API listing, and staff/manager cafeteria listings).
- **Demo impact:** ⚠ Demo-visible in cafeteria browse. It behaves like a normal active cafeteria (ordering would work). Scripted demo should browse Student/Faculty Cafeteria.

### F-61-07 — Duplicate daily menus (2 groups)
- **What:** Two daily-menu groups with identical date/cafeteria scope exist (e.g. Phase 56 E2E Cafeteria 2026-10-07 has one `draft` + one `archived` row with 3 items each).
- **Class:** **D**
- **Status:** Open; re-confirmed in Phase 62 DB recon. Harmless — archived row is inert.
- **Demo impact:** None in normal flows (UI resolves the active/published menu; archived rows are ignored).

### F-61-08 — Itemless cancelled orders (×3)
- **What:** Three cancelled orders carry no line items (historical E2E teardown artifact).
- **Class:** **D**
- **Status:** Open; re-confirmed via census (32 cancelled orders total; the 3 itemless ones predate Phase 60 hardening).
- **Demo impact:** ⚠ Only if someone opens those specific historical orders in the admin console. Normal demo paths (recent orders, order #31 lifecycle) are unaffected.

### F-61-09 — Sessions un-reaped (383 rows)
- **What:** `user_sessions` table holds 383 rows including expired sessions; no background reaper is configured in the current runtime.
- **Class:** **P** (operational hygiene gap — access tokens expire correctly; stale refresh-session rows persist)
- **Status:** Open; token *validation* is unaffected (expired tokens are rejected at auth time). Phase 62 logins added their sessions as expected.
- **Demo impact:** None — invisible in UI; DB-level only.

### F-61-10 — Dietary tags 3/35, allergens 2/35
- **What:** Only 3 of 35 menu items carry dietary tags; 2 carry allergen data. Nutrition metadata is sparse in seed data.
- **Class:** **D** (data completeness of seed) / partially **F** (richer nutrition UX is post-release scope)
- **Status:** Open; no code defect.
- **Demo impact:** ⚠ Dietary/allergen badges appear on few items. Do not script a demo beat around dietary filtering.

### F-61-11 — Stale host uvicorn PID 4772 on :8001
- **What:** A leftover uvicorn process from an earlier local run still listens on host port 8001.
- **Class:** **D** (host residue — not part of the Docker demo stack)
- **Status:** Open; container `uniserve_api` (:8000) is unaffected. Kill manually via Task Manager / `taskkill` if desired — outside repo, no code change.
- **Demo impact:** None — all clients point to :8000.

### F-61-12 — `apps/api/.env` stale in repo
- **What:** The checked-in `apps/api/.env` file contains outdated values; the runtime environment (container env_file `.env.production`, compose env) wins at runtime.
- **Class:** **D**
- **Status:** Open; no functional impact — runtime env precedence verified by live probes in Phases 58–62.
- **Demo impact:** None.

### F-61-13 — Lint warning baselines (web 95W, mobile 61W)
- **What:** Both frontends carry long-standing warning counts (0 errors each).
- **Class:** **F** (cleanup backlog, not defects)
- **Status:** Open; **re-verified in Phase 62**: web eslint 0E/95W, mobile eslint 0E/61W — exactly at baseline, no regression.
- **Demo impact:** None.

### F-61-14 — Mobile cold-start flake under concurrent suites
- **What:** Mobile jest can flake when suites run concurrently on the 8GB host.
- **Class:** **D** (host constraint) / **P** (test-parallelism sensitivity)
- **Status:** Mitigated by procedure: run suites **sequentially** (`--runInBand`). **Re-verified in Phase 62: 34/34 passed, no flake.**
- **Demo impact:** None — never run suites concurrently during demo prep.

### F-61-15 — Compose dev defaults vs runtime override
- **What:** `docker-compose.yml` defaults (ports 8000/5432 etc.) differ from the local verification override (temp file outside repo: api 8000→8000, postgres 5433→5432) and from `docker-compose.prod.yml`.
- **Class:** **D** (environment configuration drift between dev/prod/verify)
- **Status:** Documented, not code-fixed — override file lives in `%TEMP%` and must not be committed. `FINAL_LOCAL_RUN_GUIDE.md` §2/§4 documents the exact local topology.
- **Demo impact:** None if the run guide is followed.

### F-61-16 — Residue accounts visible in admin user list
- **What:** Admin user console lists seeded test/probe accounts (e.g. `phase58.probe…@…`, `test.student4…@…`, suspended `p47.*` accounts — 18 users total: 11 active, 3 suspended, 4 pending_verification).
- **Class:** **D**
- **Status:** Open by policy (no deletions); re-confirmed in Phase 62 browser rehearsal.
- **Demo impact:** ⚠ Demo-visible on the users screen. Scripted admin demo should focus on role badges/counts, not on individual user rows.

---

## Demo-visibility summary

| Visible during scripted demo? | Items |
|---|---|
| Yes, avoid scripting beats around them | F-61-04 (pending refunds/online orders), F-61-06 (E2E cafeteria), F-61-08 (itemless cancelled, only on those 3 orders), F-61-10 (sparse dietary badges), F-61-16 (residue accounts in user list) |
| No (backend/build/tooling only) | F-61-02, F-61-03, F-61-05, F-61-07, F-61-09, F-61-11, F-61-12, F-61-13, F-61-14, F-61-15 |

**None of the 15 open items is a demo blocker.** Every role rehearsal, the critical order E2E story, RBAC enforcement, notification runtime, and all 8 regression gates passed live in Phase 62 with these limitations in place.

## Cleanup backlog (post-demo, no current commitment)

1. Adjudicate pending refund on order #52; settle/reconcile the 3 stale online-pending orders (F-61-04).
2. Deactivate or rename "Phase 56 E2E Cafeteria" + retire duplicate daily-menu rows (F-61-06, F-61-07).
3. Archive/delete itemless cancelled orders (F-61-08) and probe accounts per data-retention policy (F-61-05, F-61-16).
4. Add session reaper job (F-61-09); enrich dietary/allergen seed data (F-61-10).
5. Kill host :8001 residue (F-61-11); refresh stale `apps/api/.env` docs (F-61-12); schedule lint-warning burn-down (F-61-13).
6. Long-term: automated image↔DB schema preflight (F-61-02); resolve dual-React monorepo layout for static export (F-61-03).
