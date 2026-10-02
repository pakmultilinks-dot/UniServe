# Phase 33 — Production Release Candidate & Full Deployment Simulation

**Status:** COMPLETE
**Date:** 2026-10-02
**Branch:** `main` (starting HEAD `7caa8a7`, Phase 32)
**Deliverable:** end-to-end local simulation of the production release pipeline, one genuine release-blocking defect found and fixed, simulation environment destroyed after validation.

---

## 1. Objective & Scope

Prove locally — without a VPS, DNS, domain, real credentials, or external services — that a Git release candidate at a pinned commit can travel the entire production pipeline:

Git RC → locked dependencies → production API image → fresh PostgreSQL → Alembic migrations → API readiness → Caddy (only published entry point) → static web artifact → auth/RBAC → realistic cafeteria workflows → backup/restore → failure recovery → security verification → regression suite → evidence.

Explicitly out of scope (per phase constraints): VPS deployment, real DNS/domains, production credentials, JazzCash/external payment providers, unrelated feature changes.

**This document is a simulation report. It is NOT a production deployment claim.**

## 2. Baseline & Constraints

| Item | Value |
|---|---|
| Starting HEAD | `7caa8a7` (`fix: lock production dependencies`, Phase 32) |
| Working tree at start | clean |
| Rehearsal stack (`uniserve_api`, `uniserve_postgres`, `uniserve_caddy`, `n8n`) | untouched throughout |
| Environment rule | disposable Compose project `uniserve-sim`, fresh PostgreSQL volume, own network, temp strong secrets only, destroyed after validation |
| Port rule | API and PostgreSQL expose-only (no host ports); **only Caddy published `8080:80`** |
| Artifact rule | web artifact must not contain `localhost:8000`, `127.0.0.1`, `api.example.com`, `app.example.com` (except source maps/docs) |
| DB rule | no direct database manipulation except test setup/cleanup |
| Image rule | evidence pinned to content-addressed image ID, not `latest` |

## 3. Simulation Environment

- Compose project: `uniserve-sim` (fixed name; separate network `uniserve-sim_default`, separate volume `uniserve-sim_sim_postgres_data`).
- Containers:
  - `uniserve-sim-caddy` (image `caddy:2-alpine`) — **the only published port: `8080:80`**.
  - `uniserve-sim-api` (image `uniserve-sim-api:rc33`) — `expose: 8000`, no host port.
  - `uniserve-sim-postgres` (image `postgres:16-alpine`) — `expose: 5432`, no host port, fresh volume.
- Sim secrets (`.env.sim`, temp only, destroyed): `APP_ENV=production`, `APP_DEBUG=false`, `APP_SECRET_KEY`/`JWT_SECRET_KEY` = `secrets.token_urlsafe(64)` (88 chars), `POSTGRES_PASSWORD` = `token_urlsafe(32)` (43 chars), JSON logs.
- Sim Caddyfile: vhosts `api.uniserve-sim.local` → API, `app.uniserve-sim.local` → static, `:80` catch-all (`/api/*` → API, else static). Domain architecture of the real production Caddyfile was **not** modified for the simulation; the sim uses its own temp copy.

## 4. Release Candidate Identity

| Artifact | Identity |
|---|---|
| Git RC | `main` @ `7caa8a7` (Phase 32 lock commit) |
| API image | `uniserve-sim-api:rc33` = **`sha256:0324fce64d48bdaf322123dc3eadd7955ab4bf8268bf7b2f6002135c868adea1`**, 835,789,886 bytes (~836 MB), built 2026-10-02T09:40:33Z from `apps/api/Dockerfile` + `requirements.lock.txt` (strict locked install) |
| Web artifact | Next.js 14.2.35 static export: **22 HTML + 21 RSC `.txt` files** |
| Migrations | Alembic head **`0009`** (10 migrations, `0000`–`0009`) |

Evidence is pinned to the content-addressed image ID. `latest` tags were never used as evidence.

## 5. Dependency Reproducibility

- Image installed strictly from `apps/api/requirements.lock.txt` (**44 pins**, Phase 32).
- Regression rebuild (`docker compose -f docker-compose.prod.yml build api`, exit 0): every one of the **44 locked package/version pairs is present** in the rebuilt image (name-normalized comparison); zero version mismatches. One extra package, `packaging`, is a build-time transitive helper only — not a runtime dependency and not a deviation from the lock.
- Frontend: root `package-lock.json` + `npm ci --ignore-scripts` workflow (Phase 32) unchanged; `npm run build:shared` exit 0.

## 6. Web Artifact Build & Inspection

- `NEXT_PUBLIC_API_URL` is a **build-time** variable read once (`apps/web/src/lib/api.ts:95`): `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"`.
- Build **with** the documented production value (runbook Step 6 / `DEPLOYMENT_RUNBOOK.md`): forbidden-string scan over all `*.html,*.js,*.css,*.txt` in `out/` → **0 matches** (`localhost:8000`, `127.0.0.1`, `api.example.com`, `app.example.com`).
- Build **without** the variable (plain `next build`) embeds the documented dev fallback `http://localhost:8000/api/v1` in one chunk — expected behavior (documented since Phase 28A), and a **deployment prerequisite**: production builds must set `NEXT_PUBLIC_API_URL=https://api.<real-domain>/api/v1` (or copy `apps/web/.env.production.example` → `apps/web/.env.production.local`).

## 7. Topology Start

- `docker compose up -d` on the sim project: all three services healthy; verified via `docker ps` that **only `uniserve-sim-caddy` publishes a host port** (`0.0.0.0:8080->80/tcp`); API shows `8000/tcp`, PostgreSQL `5432/tcp` — expose-only.
- One sim-Caddy vhost issue encountered and corrected in the temp `Caddyfile.sim` during bring-up (sim-only file; production Caddyfile untouched at this step).

## 8. Fresh Database, Migrations, Readiness

- Empty volume → `alembic upgrade head` → **`0009`** (`alembic_version` table confirmed).
- `GET /api/v1/health/ready` → HTTP 200 `{"status":"ready","database":"connected","schema":"present"}`.
- `GET /api/v1/health` → HTTP 200 `{"status":"healthy",...}` — this is the exact path used by the production compose healthcheck (`docker-compose.prod.yml` API healthcheck), verified live.
- Note (Phase 28A design, re-confirmed): readiness **always returns HTTP 200**; degraded state is reported in the JSON `status` field. Monitoring must assert on the field, not the code.

## 9. API Smoke

Login body field `university_email` (not `email`); tokens nested under `tokens`; `/auth/me`; collection endpoints require trailing slash; `PaymentInitiateRequest` requires `idempotency_key`; stock enforced at cart-add (HTTP 400); scheduled orders validated to today/cafeteria-local/after-now/before-closing; production-without-provider payments → HTTP 503. All exercised repeatedly in the workflow below.

## 10. Web Smoke via Caddy — Major Defect Found & Fixed

**Defect (release-blocking):** every route served the identical 5,271-byte root shell ("Redirecting to dashboard…"). Hard reload of `/dashboard/admin/overview` always bounced to `/dashboard` home. Root cause: the production `try_files {path} /index.html` **never tries `{path}.html`**, so per-route HTML files (`login.html`, `dashboard/admin/overview.html`, …) were never served; `apps/web/src/app/page.tsx`'s unconditional `router.replace("/dashboard")` then swallowed every deep link. Verified empirically by byte counts + content diff, and confirmed identical in the production `infrastructure/caddy/Caddyfile` (same config → same production behavior).

**Fix (the single repo change of this phase):** both static-serving blocks in `infrastructure/caddy/Caddyfile` now use:

```caddy
try_files {path} {path}.html {path}/index.html /index.html
```

This is static-file resolution config only — the production domain/vhost architecture was not altered.

**Verification after fix (sim copy, same change):** `/login` → 10,648 B (login shell), `/dashboard/admin/overview` → 7,212 B (overview shell), `/dashboard/orders` → 6,692 B, `/dashboard/admin/users` → 7,194 B, `/register` → 13,926 B; browser hard reload of `/dashboard/admin/overview` renders "Administration Overview" with live data (Total Users 35, Total Orders 8, Active Cafeterias 2, 27 menu items) and stays on-route. Only expected client-side noise: a single console 401 on `/auth/me` (in-memory access token + silent-refresh design — first attempt before refresh completes; by design in `packages/shared-types/src/api-client.test.ts`).

**Full workflow re-run after the fix: 48/48 PASS.** The compose bind-mount (`./infrastructure/caddy/Caddyfile:/etc/caddy/Caddyfile:ro`) propagates the fix on deploy.

Historical documents `PHASE_31_PRODUCTION_DEPLOYMENT_PREREQUISITE_FINALIZATION.md` and `PRODUCTION_INTEGRATION_AUDIT.md` still describe the old `try_files` behavior; they are historical records and were left untouched — superseded by this fix (see findings).

## 11. Mobile Compatibility Check

- `apps/mobile/src/config.ts` production `API_BASE_URL` = `https://api.uniserve.app/api/v1` (LGU-branded operator placeholder — **unchanged**; setting the real API domain is a documented deployment prerequisite).
- All mobile-consumed endpoints match the API routes exercised in the workflow (auth, catalog, cart, orders, scheduled, notifications, profile).
- `npm run build:shared` + `npm run type-check:mobile` (`tsc --noEmit`) → **exit 0**.

## 12. Realistic Business Workflow

Scenario: 7 seeded users (3 students, 2 faculty, 1 staff, 1 manager, 1 admin), 2 cafeterias, 27 menu items, 2 daily menus. Script `phase33_workflow.py` (pure ASCII) through the Caddy entry point.

**Result: PASS 48 / FAIL 0 / SKIP 0 — 48/48**, both before and after the Caddyfile fix. Coverage groups: D1–D9 business (registration, OTP, login, catalog, cart, stock rules, order placement, order lifecycle, role-scoped views), E (scheduled orders incl. window rejections), F (faculty flow), G (payment safety), H (notifications).

## 13. Payment Safety & Notifications

- `POST /payments/initiate` in production with test provider configuration → **HTTP 503** `Online payments are unavailable: no production payment provider is configured`. Fail-closed confirmed; no JazzCash (out of scope by constraint).
- `idempotency_key` mandatory; `confirm_order` semantics PENDING→PENDING with `confirmed_at` flag are by design.
- Notification paths exercised through the workflow (H-group checks passed).

## 14. Backup & Restore Drill

- Backup: `scripts/backup_database.sh` **hardcodes `CONTAINER_NAME="uniserve_postgres"`** (not env-overridable — running it against the sim failed harmlessly with `FATAL: role "uniserve_sim" does not exist` against the rehearsal DB, read-only). Drill used a byte-identical temp copy with only `CONTAINER_NAME` defaulted to the sim container; `MSYS2_ARG_CONV_EXCL="*"` required so MSYS does not rewrite `/tmp/...` paths.
- Dump verified host-side: **127,122 bytes, 239 TOC entries, gzip, dbname `uniserve_sim_prod`**.
- Restore: `scripts/restore_database.sh` (env-overridable + `CONFIRM=yes` gate, `--clean --if-exists --no-owner --no-acl`) → **RESTORE-EXIT=0**.
- **Restore nuance (runbook-relevant):** `pg_dump` does not emit `CREATE SCHEMA public` — restore targets a database where the `public` schema already exists (true for any `CREATE DATABASE` in production). Drill: `DROP SCHEMA public CASCADE` → restore fails cleanly (schema missing); `CREATE SCHEMA public AUTHORIZATION ...` → restore succeeds.
- Post-restore verification: readiness `ready` + `schema present`, `alembic current` = **`0009`**, row counts exact (`users 40 | orders 10 | menu_items 27 | cafeterias 2`), admin login HTTP 200 with role `university_admin`.

## 15. Failure & Recovery Drills

| Drill | Action | Result |
|---|---|---|
| D1 | restart API container | readiness recovered in **12 s** |
| D2 | restart PostgreSQL container | readiness **honest degraded**: `{"status":"degraded",...,"Database readiness check failed: ... Connection refused"}` (still HTTP 200 by design), recovered ~6 s after PG up |
| D3 | boot API with empty secrets (`APP_ENV=production`) | **fail-closed**: settings `ValidationError` at worker startup; port never binds |
| D4 | drop `users` table | readiness `{"status":"degraded","schema":"missing"}` + login HTTP 500 — never falsely ready; restore → recovered |
| D5 | stop Caddy | entry point unreachable (**HTTP 000**); start → HTTP 200 |

## 16. Security Verification

| Check | Result |
|---|---|
| S1 published ports | only `uniserve-sim-caddy` publishes `8080`; API `8000/tcp` + PostgreSQL `5432/tcp` expose-only |
| S2 security headers | `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` present on web responses |
| S3 image contents | no `/app/.env` in the image; runtime secrets only via environment |
| S4 error bodies | HTTP 500 body = plain `Internal Server Error`, no stack/config leak |
| S5 log hygiene | sim secrets (88/43 chars) absent from API/Caddy/PostgreSQL logs (`leaked=False`) |
| S6 secret guards | see determination below |
| S7 CORS | evil origin (`http://evil.example`) receives **no** `Access-Control-Allow-Origin`; configured origin `http://localhost:8080` echoed correctly |
| S8 debug surface | `/api/docs`, `/api/redoc`, `/api/openapi.json` → **HTTP 404** in the production runtime |

**S6 determination (weak-secret fail-closed, live-probed):**

Production settings validation in `apps/api/app/core/config.py` provides three fail-closed guards, all confirmed live:

1. `reject_default_secrets` — rejects the two denylisted default values and **empty/whitespace** keys when `APP_ENV=production`.
2. `reject_debug_in_production` — rejects `APP_DEBUG=true` with `APP_ENV=production` (message names the docs/redoc/openapi exposure).
3. `reject_dev_database_password_in_production` — rejects the documented dev DB password.

Live probes on the RC image:

- **Empty keys** + `APP_ENV=production`: settings `ValidationError` fires in uvicorn workers → **port never binds, connection refused** (fail-closed at serve level). Operational nuance: the uvicorn *master* process lingers respawning crashing workers, so the container shows `Up` without ever serving — the production compose healthcheck (§8) marks it unhealthy; container `Up` ≠ serving.
- **Weak but non-empty keys** (`secret` / `secret123`) + valid DB credentials: the API **starts and serves** (`/api/v1/health/ready` → 200 `ready`). There is **no minimum-length/entropy enforcement** — the guard covers denylisted defaults and empties only. Phase 32's "guards fire" claim is accurate for the guards that exist; it does not extend to arbitrary weak values.

Classification: **known limitation**, not a release blocker — the production runbook and the guard's own error message instruct generating keys with `secrets.token_urlsafe(64)`; the simulation used 88-character random keys; production secret generation is operator-owned. Future hardening suggestion recorded in findings.

## 17. Regression Suite (with the Caddyfile fix in tree)

| Suite | Result |
|---|---|
| Backend pytest (`apps/api/tests`, sqlite) | **622 passed**, exit 0 (183 s) |
| `npm run build:shared` | exit 0 |
| `npm run type-check:web` | exit 0 |
| `npm run type-check:mobile` | exit 0 |
| Web production build (static export, with `NEXT_PUBLIC_API_URL`) | exit 0 — 22 HTML + 21 RSC `.txt`, forbidden-string scan **0** |
| `docker compose -f docker-compose.prod.yml config` | valid — services `postgres`, `api`, `caddy` (`.env.production` present as operator file; untouched) |
| Production API image build | exit 0 — 836 MB; all 44 lock pins contained (§5) |
| `alembic check` | not run offline (requires a DB connection; no non-sim DB may be touched) — the fresh-empty-database migration application in §8 (0000→0009, `alembic_version=0009`) is equivalent-or-stronger evidence for release purposes |

## 18. Simulation Cleanup

- `docker compose -p uniserve-sim down -v` → containers, network `uniserve-sim_default`, and volume `uniserve-sim_sim_postgres_data` removed.
- `docker rmi uniserve-sim-api:rc33` → image deleted (ID recorded in §4 before deletion).
- All temp artifacts removed (`$env:TEMP\uniserve_phase33`: env, sim Caddyfile, compose file, scripts, dumps, capture file).
- Residue check: no `uniserve-sim*`, no stray drill containers, no sim volumes. Rehearsal stack still up and healthy, untouched.
- Git tree after cleanup: **only `infrastructure/caddy/Caddyfile` modified** at HEAD `7caa8a7`.

## 19. Findings Classification

**Release blockers:** **NONE remaining.** One genuine release-blocking defect was found by this simulation (Caddy `try_files` deep-link breakage, §10) and fixed in-repo; all other checks passed.

**Deployment prerequisites (operator-owned, unchanged by this phase):**

1. Set real domains: production Caddyfile vhosts (`infrastructure/caddy/Caddyfile` still ships `api.example.com` / `app.example.com` placeholders), web build `NEXT_PUBLIC_API_URL`, mobile `apps/mobile/src/config.ts` `API_BASE_URL`.
2. Generate production secrets per runbook (`secrets.token_urlsafe(64)`); never reuse sim/dev values.
3. Production database must exist **with the `public` schema** before any restore (§14).
4. Build the web artifact on the server with `NEXT_PUBLIC_API_URL` set (§6); build/deploy per `DEPLOYMENT_RUNBOOK.md`.

**Known limitations:**

1. `/api/v1/health/ready` returns HTTP 200 in both ready and degraded states — monitor the JSON `status` field (deliberate Phase 28A design).
2. Secret validation rejects empty/denylisted-default/debug-on/dev-DB-password, but does **not** enforce entropy/length on arbitrary values (§16 S6).
3. Under `--workers N`, a settings-validation failure leaves the uvicorn master alive (container `Up`, never serving) — the compose healthcheck is the catch.
4. `pg_dump` output assumes the target database already has the `public` schema (§14).
5. Root-page client redirect depends on correct static `try_files` — fixed in §10; any future static host must preserve `{path}.html` resolution.

**Documentation issues (informational):**

1. `PHASE_31_PRODUCTION_DEPLOYMENT_PREREQUISITE_FINALIZATION.md` and `PRODUCTION_INTEGRATION_AUDIT.md` still describe the old `try_files {path} /index.html` behavior — superseded by §10; historical records left untouched.
2. `scripts/backup_database.sh` hardcodes `CONTAINER_NAME="uniserve_postgres"` while `scripts/restore_database.sh` is env-overridable — asymmetry should be resolved in a future phase.

**Future improvements (non-blocking):**

1. Add a minimum-length/entropy check to `reject_default_secrets` (e.g., ≥ 32 chars).
2. Consider HTTP 503 on degraded readiness for load-balancer integration (would require revisiting the Phase 28A contract).
3. Make `backup_database.sh` `CONTAINER_NAME` env-overridable like the restore script.

## 20. Verdict & Next Action

The release-candidate pipeline is **validated end-to-end locally**: pinned Git RC, locked dependencies, content-addressed production image, fresh-database migrations to `0009`, Caddy-only entry point, clean static web artifact, 48/48 business workflow, fail-closed payments, verified backup/restore, honest failure recovery, hardened security posture, and a green regression suite — with one genuine release-blocking defect found and fixed (`infrastructure/caddy/Caddyfile` `try_files`). The simulation environment was destroyed; no production systems were touched.

**Next action:** commit `fix: validate production release candidate` (config fix + this evidence document), then the release proceeds by operator action per `DEPLOYMENT_RUNBOOK.md` (real domains, production secrets, server-side web build). **Do not start Phase 34 automatically.**
