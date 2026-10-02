# Phase 31 — Production Deployment Prerequisite Finalization

> **Date:** 2026-10-02 · **Branch:** `main` · **Baseline HEAD:** `e8c28e5`
> (`feat: prepare UniServe for production deployment`) · Working tree clean
> at phase start.
>
> **Scope:** Final pre-deployment prerequisite audit. One authoritative
> checklist (`PRODUCTION_DEPLOYMENT_CHECKLIST.md`) + this evidence record.
> **UniServe was NOT deployed** (see §19). No VPS, domain, DNS, credentials,
> or JazzCash work was performed.

---

## 1. Baseline (verified)

| Item | State |
|---|---|
| Branch / HEAD | `main` @ `e8c28e5`, clean tree |
| Production compose | `docker-compose.prod.yml` — project `uniserve-prod`, 3 services (caddy/api/postgres), Redis commented (verified no runtime imports) |
| Production Dockerfile | `apps/api/Dockerfile` — non-editable `pip install .`, unbuffered, uvicorn `--workers 2` |
| Caddy | `infrastructure/caddy/Caddyfile` — `api.example.com`/`app.example.com` placeholders, automatic HTTPS, security headers, API proxy + static export |
| API configuration | `apps/api/app/core/config.py` Settings (pydantic-settings, `extra="ignore"`, env via `POSTGRES_*` etc.) — no direct `os.getenv` reads anywhere in `apps/api/app` |
| Web configuration | Next.js 14.2.35, `output: "export"`, build-time `NEXT_PUBLIC_API_URL` (single env read: `apps/web/src/lib/api.ts:95`) |
| Mobile configuration | Expo SDK 51; `src/config.ts` endpoint map keyed by EAS channel; zero `process.env` reads in `apps/mobile/src` |
| Migration head | `0009` (`0009_checkout_idempotency.py`); `alembic check` clean |
| Docs | `DEPLOYMENT_RUNBOOK.md` (20 steps), `PRODUCTION_RUNBOOK.md` (§1–§12), `DATABASE_OPERATIONS.md`, `UPDATE_ROLLBACK_PROCEDURE.md`, `DEPLOYMENT_ARCHITECTURE.md` — all audited this phase, accurate |

## 2. Environment contract (authoritative)

All API configuration flows through `Settings` (pydantic). No
`os.getenv`/`os.environ` reads exist in `apps/api/app`. Contract:

| Variable(s) | Class | Notes |
|---|---|---|
| `APP_ENV` | required (prod) | `production` selects all fail-closed guards |
| `APP_DEBUG` | required=false in prod | `true` + production → startup crash |
| `APP_SECRET_KEY`, `JWT_SECRET_KEY` | operator-generated | defaults rejected; **empty/whitespace rejected (new, Phase 31)** |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | operator-generated | password: dev-default/empty/**<12 chars rejected (new, Phase 31)**; host/port overridden to `postgres:5432` by compose |
| `CORS_ORIGINS` | required for web | JSON array; localhost default is dev-only; **not** startup-guarded (API-only deployments legitimately omit browser origins) — runbook checklist requires real origins |
| `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | optional | code defaults HS256 / 30 min / **30 days**; prod template sets refresh **7 days** (tighter recommendation — intentional, documented in PRODUCTION_RUNBOOK §9) |
| `OTP_*` (5), `PIN_*` (3), `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `PASSWORD_RESET_MAX_REQUESTS` | optional | template values equal code defaults |
| `REFUND_DEADLINE_HOURS`, `PICKUP_WINDOW_MINUTES`, `DEFAULT_PREPARATION_TIME_MINUTES`, `DEFAULT_CAPACITY`, `NOSHOW_*` (6) | optional business rules | template = defaults |
| `LOG_LEVEL`, `LOG_FORMAT` | optional | template INFO/json (dev default DEBUG) |
| `PAYMENT_PROVIDER` + 6 `PAYMENT_*` | optional, backend-only | default `test` → rejected in production (503 fail-closed) `[JC]` |
| `UNIVERSITY_EMAIL_PATTERNS` | code constants | env override possible (JSON) but not documented as an operator knob — code constants by design |
| `SMTP_*` (5) | **documented-but-unused** | commented placeholders; `extra="ignore"` → API ignores; `app/core/email.py` is a stub. Honest "future" labels in templates — no fix needed |
| `APP_HOST`, `APP_PORT` | read, runtime-unused | uvicorn CMD binds fixed `0.0.0.0:8000` in the container — harmless |
| `DATABASE_URL` (root `.env.example`) | **inert** | Settings builds URL from `POSTGRES_*` (property, not field). Template line now labeled INERT (Phase 31 fix) |
| `NEXT_PUBLIC_API_URL` | **build-time, web only** | baked into static bundle; missing value silently bakes the localhost dev fallback (`api.ts:95`) — checklist requires setting it; local `out/` builds are gitignored dev artifacts |
| Mobile API URL | build-time, code constant | `apps/mobile/src/config.ts` — operator edits `ENV.production.API_BASE_URL` before EAS build; not an env var |

**Inconsistencies found:** (a) `apps/api/.env.example` claimed "comma-separated"
CORS origins — value must be a JSON array (pydantic `list[str]`); **fixed**.
(b) Root `.env.example` `DATABASE_URL` interpolation line inert without
comment; **labeled**. (c) `apps/web/Dockerfile` ARG defaults to localhost —
**unreferenced legacy** (no compose service builds it; production serves the
bind-mounted static export) — documented, not deleted. No production
variables are read by frontend code (verified by grep). No wrong variable
names between template and Settings.

## 3. Secret safety (verified + gaps closed)

Production refuses (all verified by tests + in-image smoke):

| Check | Status |
|---|---|
| Known default `APP_SECRET_KEY`/`JWT_SECRET_KEY` | rejected (pre-existing) |
| **Empty/whitespace secret keys** | **rejected — GAP FOUND & FIXED (Phase 31)** |
| `APP_DEBUG=true` in production | rejected (pre-existing) |
| Dev-default / empty `POSTGRES_PASSWORD` | rejected (Phase 30) |
| **Weak (`<12` chars) `POSTGRES_PASSWORD`** | **rejected — GAP FOUND & FIXED (Phase 31)** |
| Test payment provider in production | initiation → HTTP 503 (unchanged) `[JC]` |
| Generated-secret instructions | accurate — `secrets.token_urlsafe(64/32)` commands verified working; PRODUCTION_RUNBOOK §2 synced with new guard behavior |

Evidence: pre-fix probe showed empty secret, whitespace secret, and 1/10-char
passwords all **accepted** in production (with debug off). After the fix,
all four scenarios fail closed; `test_config_production_guards.py` =
**21/21 passed** (12 prior + 9 new). No real secrets were generated or
committed.

## 4. URL/domain audit (112 `localhost`/`127.0.0.1` + 51 `example.com` hits classified)

| Class | Examples | Verdict |
|---|---|---|
| Legitimate dev/test | `.env*.example` templates, `config.py` dev defaults, `next.config.js` dev-only rewrites (disabled in prod builds), `config.ts` development channel, `live_verify*.py`, `scripts/*` (dev servers), historical EVIDENCE/PHASE docs, `docker-compose.prod.yml` healthcheck `localhost:8000` (**container-local, correct**), `restore_database.sh` `curl localhost` (**via Caddy on the same VPS — correct**), `production_health_check.py` default + documented `--api-url` override, `phase19_e2e_test.py` env-overridable base | keep — no changes |
| Documentation placeholders | `api.example.com`/`app.example.com` in Caddyfile, templates, runbooks | keep — replaced by operator per checklist §3 |
| Production artifact problems | **None found.** `apps/web/out` (local build with localhost URL) is **gitignored, never committed** — no committed artifact leaks localhost; server-side rebuild is mandatory and documented. `apps/web/Dockerfile` unreferenced legacy | no fix required |

No hardcoded HTTP where HTTPS is expected in any production-path code
(CORS/rewrites URLs are dev-only paths; payment callback template is HTTPS).

## 5. Caddy/domain readiness (verified)

`infrastructure/caddy/Caddyfile` matches the production architecture:
automatic HTTPS (ACME on first start with real DNS), API reverse proxy to
`uniserve_api:8000` with X-Forwarded headers, static export served from
`/srv` (compose bind mount `./apps/web/out`), SPA fallback
(`try_files … /index.html`), immutable caching for `_next/static`,
security headers on both vhosts (nosniff, DENY, HSTS on web, `-Server`),
JSON access logs to stdout. No env vars — static file, mounted read-only;
cert state persists in `infrastructure/caddy/data|config` (gitignored).

**Operator must replace exactly two lines** (checklist §3):
`api.example.com {` and `app.example.com {` with the real domains. Nothing
else. Let's Encrypt issuance intentionally not attempted locally (placeholder
domains are refused by ACME by design — rehearsed in Phase 28A).

## 6. Production Compose readiness (verified via resolved config)

`docker compose -f docker-compose.prod.yml config` resolves to:

- Project `uniserve-prod`; volume `uniserve-prod_postgres_data` — isolated
  from dev (`uniserve_postgres_data`).
- **Published host ports: 80 + 443 only** (Caddy). API (`expose 8000`) and
  PostgreSQL (`expose 5432`) have no host ports.
- `restart: unless-stopped` on all three services.
- Dependency chain: caddy → api (`service_healthy`) → postgres
  (`service_healthy`); postgres healthcheck `pg_isready`, api healthcheck
  HTTP `/api/v1/health` (liveness, container-local).
- Environment loading: `.env.production` via `env_file` for api **and**
  postgres; compose overrides `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`
  for the api (service-name resolution); `TZ=Asia/Karachi` for postgres.
  Missing `.env.production` makes compose fail loudly (no silent fallback).
- No development-only services active; Redis commented (no runtime imports —
  re-verified Phase 30/31 greps). Migrations never run automatically.

## 7. Docker image verification (verified — Docker 29.8.0 available)

Rebuilt `uniserve-prod-api:latest` after the Phase 31 guard changes:
build SUCCESS (dependency layer cached). In-image smoke:

| Scenario | Result |
|---|---|
| Dev-default `POSTGRES_PASSWORD` + production | fail-closed `ValidationError` (strong-value message) |
| **Empty `APP_SECRET_KEY` + production** | **fail-closed "Secret keys must not be empty" (new)** |
| **Weak (8-char) password + production** | **fail-closed (new)** |
| Strong secrets + production | `IMPORT-OK env= production` |
| `.env` inside image | **absent** (dockerignore working — no secrets baked) |
| Migrations in image | 11 `.py` files under `/app/migrations/versions` incl. head `0009_checkout_idempotency.py` |

## 8. Database deployment sequence (verified against docs)

Fresh-production sequence documented and consistent across
`PRODUCTION_RUNBOOK.md` §3–§4 and `DEPLOYMENT_RUNBOOK.md` Steps 7–9:
postgres starts → credentials from `.env.production` (`env_file`) →
`pg_isready` healthy → `run --rm api alembic upgrade head` (env.py builds
URL from `POSTGRES_*`; `alembic.ini` carries no credential) →
`alembic current` = `0009 (head)` → API starts → `/api/v1/health/ready`
reports `ready` + `schema: present` (readiness probes the core `users`
table, so a wiped schema is detected). Existing-database upgrade path
documented separately (`UPDATE_ROLLBACK_PROCEDURE.md` update procedure +
pre-migration backup rule). Historical migrations untouched; **no
destructive downgrade testing performed** this phase (dev volume probed
read-only via isolated `:5433` container, torn down after).

## 9. Backup/restore readiness (audited; operator sequences in checklist §8–§10)

| Element | State |
|---|---|
| `scripts/backup_database.sh` | pg_dump inside container → `pg_restore --list` verification → copy out → 30-day prune; non-zero on failure |
| `scripts/restore_database.sh` | **`CONFIRM=yes` gate** (refuses otherwise), in-container dump verification **before** destructive steps, `--clean --if-exists --no-owner --no-acl`, temp cleanup |
| `DATABASE_OPERATIONS.md` | scripted commands, cron example, forward-fix-first policy, volume-name distinctions |
| Cron instructions | present in runbook + checklist — **backups are NOT automatic until the operator installs the cron entry** |
| Backup destination | `./backups/` (gitignored) — checklist requires off-machine copies |
| Post-restore verification | `alembic current` → head; readiness → `ready`; row spot-check — rehearsed Phase 28A (schema wipe → restore → verify) |

Exact operator sequences for **Backup / Restore / Restore verification /
Emergency recovery** are in `PRODUCTION_DEPLOYMENT_CHECKLIST.md` §8–§10.

## 10. Web production artifact (verified)

- `output: "export"` → static export; **no runtime web server/container**
  (none in prod compose — correct; do not introduce one).
- `NEXT_PUBLIC_API_URL` is the single build-time env; `next.config.js`
  rewrites are dev-only (return `[]` in production builds — the export
  warning is cosmetic and expected).
- `out/` is gitignored (never committed); production build on the server,
  served by Caddy read-only bind mount. Local dev `out/` contains the
  localhost fallback URL — irrelevant to deployment (checklist §4 mandates
  rebuild with the real API URL).
- Type-check clean; production build green (24/24 static pages,
  `out/index.html` emitted).

## 11. Mobile production artifact (audited)

- `app.json`: bundle IDs `com.uniserve.mobile` (iOS + Android), expo-router
  plugin — **must remain unchanged** (store identity).
- `eas.json`: `production` channel + `autoIncrement`; submit config
  references `google-service-account.json` (**not committed** — external)
  and empty `appleId`/`ascAppId` (external).
- `src/config.ts`: endpoint map keyed by EAS channel
  (`production` → `https://api.uniserve.app/api/v1` placeholder). Channel
  is injected by EAS at build time; local/dev builds default to
  development. **Operator must edit the production URL before an EAS
  build** (checklist §11). Zero `process.env`/`EXPO_PUBLIC_*` reads — no
  backend secrets can leak into the bundle.
- **Cannot be verified without an Expo/EAS account:** EAS build
  execution, APK/IPA artifacts, store submission. Not attempted; none
  produced. Mobile production readiness is claimed only to the extent the
  repository proves: configuration is minimal-viable and consistent.

## 12. Deployment smoke-test checklist

The definitive 22-step post-deployment sequence (DNS → HTTPS → containers →
migrations → readiness → web → login → roles → isolation → menu → orders →
lifecycle → cancellation → notifications → log scan → backup job → restore
docs → payments fail-closed → port exposure) is maintained in
`PRODUCTION_DEPLOYMENT_CHECKLIST.md` §7, cross-linked to
`PRODUCTION_RUNBOOK.md` §11 (command-level) and `DEPLOYMENT_RUNBOOK.md`
Steps 11–16 (first-time business verification). No destructive production
actions are part of it.

## 13. Rollback (verified — 5 categories documented distinctly)

| Category | Where documented | Posture |
|---|---|---|
| Application rollback | PRODUCTION_RUNBOOK §9; UPDATE_ROLLBACK "Code Rollback" | previous commit → rebuild → restart |
| Static web rollback | same sections (web lines) | previous commit → `npm install && npm run build` → `restart caddy` |
| Migration issue | PRODUCTION_RUNBOOK §4; DATABASE_OPERATIONS policy; UPDATE_ROLLBACK rule 8 | **forward-fix first**; downgrade last-resort (backup + stopped API); `alembic downgrade base` explicitly forbidden as routine |
| DB corruption/loss | PRODUCTION_RUNBOOK §6 (rehearsed); restore script gate | verified backup → controlled restore → readiness verify |
| Environment/config error | PRODUCTION_RUNBOOK §9 | keep `.env.production.bak-<ts>`, restore, restart |

`alembic downgrade` is **not** recommended anywhere as a generic rollback.

## 14. Security final pass (verified)

- No secrets tracked: `git ls-files` matches only `*.example` templates.
- No production `.env` tracked; `.gitignore` covers `.env`,
  `.env.*.local`, `.env.production`, `backups/`, `out/`, caddy data/config.
- No credentials in the Docker image (`.env` absent; smoke-verified).
- CORS explicit (`settings.CORS_ORIGINS` → CORSMiddleware; no wildcard;
  dev localhost default documented as dev-only).
- Production debug disabled (guard); default secrets rejected; empty
  secrets rejected (new); dev-default/empty/weak DB passwords rejected.
- Payment test provider cannot succeed in production (503 at initiation —
  code-verified at `payments/router.py:94-98`, unchanged) `[JC]`.
- Logs: structlog; rehearsal scans found no secrets; smoke checklist step 18
  repeats the grep on every deployment.
- Database not publicly exposed (no host ports); API not publicly exposed
  (expose-only); **Caddy is the sole public entry point** (80/443).
- Docs gating: `/api/docs`, `/api/redoc`, `/api/openapi.json` unmounted in
  production (`main.py` gates on `APP_DEBUG`).

## 15. External dependency matrix

| Dependency | Repo ready? | Operator action | External dependency | Verified? |
|---|---|---|---|---|
| VPS | scripts in `scripts/vps/` | purchase + provision | hosting provider | **No** |
| Domain | Caddyfile placeholders | buy + configure | registrar | **No** |
| DNS | runbook Step 4 | create A records | DNS provider | **No** |
| TLS | Caddy automatic | keep 80/443 open; replace placeholders | Let's Encrypt | **No** (requires real domains) |
| Production secrets | mechanism + guards ready | generate on server | — | **No** (none created) |
| Expo/EAS | config ready | edit mobile prod URL; account; build | Expo | **No** |
| SMTP | not implemented (stub) | decide later | email provider | **No** |
| JazzCash | **blocked** — fail-closed guard only | official API contract + credentials | JazzCash | **No** `[JC]` |
| Backups | scripts ready | cron + off-machine copy | storage | **No** |
| Monitoring | not configured | uptime + log alerts | monitoring provider | **No** |

No providers, credentials, or dates were invented.

## 16. Files changed (Phase 31)

| File | Change |
|---|---|
| `apps/api/app/core/config.py` | **Code:** reject empty/whitespace secret keys in production; reject `POSTGRES_PASSWORD` < 12 chars in production (error message synced) |
| `apps/api/tests/test_config_production_guards.py` | 9 new tests (empty/whitespace secrets ×2 fields, dev-unchanged, weak passwords ×3, 12-char boundary) — 21/21 pass |
| `apps/api/.env.example` | CORS comment corrected: JSON array (was "comma-separated") |
| `.env.example` | `DATABASE_URL` line labeled UNUSED/INERT (Settings builds URL from `POSTGRES_*`) |
| `PRODUCTION_RUNBOOK.md` | §2 fail-closed description synced with new guard behavior |
| `EVIDENCE_PRODUCTION_DEPLOYMENT_PREPARATION.md` | Corrected `out/` wording: gitignored local artifact, not a committed artifact |
| `PRODUCTION_DEPLOYMENT_CHECKLIST.md` | **NEW** — the one authoritative operator checklist (§0–§11 incl. smoke test, backup/restore/emergency sequences, rollback matrix, external dependency matrix) |
| `PHASE_31_PRODUCTION_DEPLOYMENT_PREREQUISITE_FINALIZATION.md` | **NEW** — this evidence report |

## 17. Validation results (all green)

| Check | Result |
|---|---|
| Backend suite (`pytest apps/api/tests`) | **622 passed** in 162.18s (613 baseline + 9 new) |
| Config-guard tests | **21/21 passed** |
| Web type-check | clean |
| Web production build | green — 24/24 static pages, `out/index.html` emitted |
| Mobile type-check | clean |
| `alembic current` (isolated dev-volume container `:5433`) | `0009 (head)` |
| `alembic check` | `No new upgrade operations detected` |
| `docker compose -f docker-compose.prod.yml config` | valid; published ports **80/443 only** |
| Docker image build | SUCCESS (post-change rebuild) |
| In-image smoke | all guards fail closed as expected; strong config imports; no `.env`; migrations to 0009 |
| `git status` | expected modified files only; temp PG container removed; `out/` stays ignored |

## 18. Remaining blockers

Deployment-blocking (all external/operator — none are repo defects):
1. No VPS provisioned · 2. No domains/DNS · 3. No TLS (follows DNS) ·
4. No production secrets generated · 5. Web/mobile build-time URLs must be
set to real domains on the build host · 6. Expo/EAS account for mobile
builds · 7. Backup cron not installed (no server) · 8. Monitoring absent.

Design-level (accepted, documented):
- **JazzCash externally blocked** `[JC]` — online payments remain
  fail-closed 503; guard untouched.
- SMTP unimplemented (in-app notifications only).
- Unpinned Python/Node dependencies (no lockfiles) — non-reproducible
  builds; future release-engineering phase.

## 19. Explicit statement

**UniServe was NOT deployed by this phase.** No VPS was provisioned, no
domain purchased, no DNS modified, no production credentials created, no
JazzCash work performed, and no external service was contacted. The local
production-rehearsal stack on this workstation was left untouched. The
deployment checklist is executable **when** the external infrastructure in
§15 becomes available — and every item remains honestly marked unverified
until then.
