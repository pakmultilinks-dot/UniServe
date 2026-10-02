# UniServe — Production Provisioning Readiness (Phase 39)

**Date:** 2026-10-02 · **Starting commit:** `7b3a5e8` (`fix: harden OTP and order state handling`) · **Tree:** clean
**Purpose:** exact, repository-derived checklist for external production provisioning. **No deployment performed. No credentials, domains, SMTP, or JazzCash values invented.** This document supersedes stale provisioning statements elsewhere (see §14 drift note).

---

## 1. Current repository baseline

| Item | Fact |
|---|---|
| HEAD | `7b3a5e8` on `main` (Phase 38 hardening: OTP persistence, inventory read scope, ready-path invariants) |
| Tests | 649 backend tests pass; web/mobile type-checks + web production build green (Phase 38) |
| Migrations | Alembic head `0009`; deploy path = manual `alembic upgrade head` (never on startup) |
| Prior deployment | **None.** No VPS, domains, DNS, or external accounts exist. `DEPLOYMENT_BLOCKERS.md` B1–B10 remain the authoritative blocker list (its commit references are stale; the deployable commit is `7b3a5e8` or later) |
| Phase 38 doc | No `PHASE_38_FINAL_PRODUCT_ACCEPTANCE.md` exists; Phase 38 outcome = commit `7b3a5e8` + green regression evidence |
| Secrets hygiene | Only `.example` templates tracked (5 files); `.env.production` + `apps/web/.env.production.local` gitignored; no credential files in tree |

## 2. Production architecture (as committed)

```
Internet ──:80/:443──► Caddy (caddy:2-alpine, uniserve_caddy)
                          ├─ api.<domain>  → reverse_proxy uniserve_api:8000 (expose-only)
                          └─ app.<domain>  → static /srv = apps/web/out (try_files deep-link fix — do not regress)
                     uniserve_api (FastAPI, apps/api) ──:5432──► postgres:16-alpine (uniserve_postgres, volume postgres_data, TZ Asia/Karachi)
                     Redis: NOT required at runtime (compose block commented out — verified no redis import in app)
```

Compose: `docker-compose.prod.yml`, fixed project name `uniserve-prod`, all services `restart: unless-stopped`, api+postgres healthchecks (caddy has none — "Up" is its success state). Mobile is built separately via EAS and is not part of the server stack.

## 3. Required external inputs (owner actions)

| # | Input | Owner action | Needed |
|---|---|---|---|
| 1 | VPS | Provision (Ubuntu 22.04+/Debian 12+, 2+ CPU, 4 GB RAM, 40 GB SSD); run `scripts/vps/run-all.sh` | Before first deploy |
| 2 | SSH access | Key-based root/sudo to the server | Before first deploy |
| 3 | Two domains + DNS | Register `api.<domain>`, `app.<domain>`; A records → server IP | Before first deploy |
| 4 | Server `.env.production` | Create on server from `.env.production.example` (or review + **rotate** the local rehearsal file); `chmod 600` | Before first deploy |
| 5 | Git hosting / transfer | Push `main`, or `scp`/rsync the tree with `.git` intact (rollbacks need it) | Before first deploy |
| 6 | SMTP account | Real SMTP credentials + a From address that the provider allows (see §5) | Before self-serve onboarding (OTP emails); cash-only internal launch can defer |
| 7 | Web API URL | Same as #3 — `NEXT_PUBLIC_API_URL=https://api.<domain>/api/v1` baked at web build time | At web build (on server) |
| 8 | Mobile API URL + Expo account | Edit `apps/mobile/src/config.ts` production URL; Expo account + EAS credentials; store credentials (§8) | Only for mobile production builds |
| 9 | Payment provider contract | Official JazzCash technical contract + merchant credentials (§9) | **Optional** — cash launch supported; payments stay fail-closed (503) |
| 10 | Off-machine backup storage | Any object storage / second host for dump copies | With backups (§10) |
| 11 | External uptime monitor | e.g., UptimeRobot/BetterStack polling `/api/v1/health/ready` (not in repo) | After first deploy |

## 4. Exact environment-variable contract

Consumed by `apps/api/app/core/config.py` (`Settings`, env-file `.env.production` via compose `env_file`). "Guard" = fail-closed startup validator (API refuses to boot; verified in `tests/test_config_production_guards.py`). Production template: `.env.production.example`.

| Variable | Consumed by | Required? | Example (placeholders only) | Validation / behavior |
|---|---|---|---|---|
| `APP_NAME` | Settings/logging | Optional | `UniServe` | none |
| `APP_ENV` | Settings + guards | **Yes** — must be `production` | `production` | Literal `development\|testing\|staging\|production`; activates all guards below |
| `APP_DEBUG` | Settings; gates `/api/docs` `/api/redoc` `/api/openapi.json` | **Yes** | `false` | **Guard:** `true` + production → boot failure |
| `APP_SECRET_KEY` | Session/signing internals | **Yes** | `python -c "import secrets; print(secrets.token_urlsafe(64))"` | **Guard:** default/empty/whitespace value + production → boot failure |
| `APP_HOST` / `APP_PORT` | uvicorn | Yes (defaults fine) | `0.0.0.0` / `8000` | none — container-internal |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Settings → DB URL | Yes — compose overrides to `postgres` / `5432` | set by compose | **Note:** `DATABASE_URL` is constructed from discrete `POSTGRES_*` fields; any `DATABASE_URL=` line is inert |
| `POSTGRES_USER` | DB URL + backup script | Yes | `uniserve` | none |
| `POSTGRES_DB` | DB URL + backup script | Yes | `uniserve_prod` | none |
| `POSTGRES_PASSWORD` | DB URL | **Yes** | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | **Guard:** empty, dev default `uniserve_dev_password`, or <12 chars + production → boot failure |
| `JWT_SECRET_KEY` | Access/refresh token signing | **Yes** | same generation as `APP_SECRET_KEY` | **Guard:** same as `APP_SECRET_KEY`; **changing it later invalidates all sessions** |
| `JWT_ALGORITHM` | auth | Yes (default fine) | `HS256` | none |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` / `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | auth | Optional | `30` / `7` | none (defaults 30/7 prod, 30/30 dev) |
| `CORS_ORIGINS` | FastAPI CORSMiddleware | **Yes** — JSON array of exact web origin(s) | `["https://app.<domain>"]` | **No startup guard** — wrong value fails only in browsers post-deploy. Must replace the local rehearsal value (contains `localhost` origins + `app.example.com` placeholder) |
| `LOG_LEVEL` / `LOG_FORMAT` | structlog | Recommended | `INFO` / `json` | none (guard does not enforce; use INFO + json) |
| `SMTP_HOST` | `app/core/email.py` SMTPEmailProvider | **Yes for OTP email delivery** | `smtp.<provider>.com` | Absent → email **fails closed at runtime** (reported failure, never fake success); app still boots |
| `SMTP_PORT` | SMTPEmailProvider | Yes | `587` (starttls) or `465` (ssl) | none |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTPEmailProvider | If provider requires auth | `<smtp-user>` / `<smtp-password>` | login attempted only when username set |
| `SMTP_FROM_EMAIL` | SMTPEmailProvider | **Yes for OTP email delivery** | `noreply@<your-domain>` | Absent → fail closed like `SMTP_HOST` |
| `SMTP_TLS_MODE` | SMTPEmailProvider | Yes | `starttls` | **Guard:** `none` + production → boot failure (plaintext SMTP rejected) |
| `PAYMENT_PROVIDER` | payments factory (`providers/__init__.py`) | Optional — leave commented for cash launch | *(unset)* | `test` (default) → **rejected in production**: initiate + webhook → HTTP 503; unknown name → fail-closed 503. Real value only from a signed provider contract (§9) |
| `PAYMENT_ENVIRONMENT`, `PAYMENT_MERCHANT_ID`, `PAYMENT_API_KEY`, `PAYMENT_API_SECRET`, `PAYMENT_WEBHOOK_SECRET`, `PAYMENT_CALLBACK_URL` | future provider adapter | Only with a real provider | `<provider-values>` | backend-only; never in `NEXT_PUBLIC_*` or mobile config; commented out in template |
| `OTP_LENGTH`/`OTP_EXPIRE_MINUTES`/`OTP_MAX_ATTEMPTS`/`OTP_RESEND_COOLDOWN_SECONDS`/`OTP_MAX_RESENDS` | auth | Optional | `6`/`10`/`5`/`60`/`3` | defaults already production-sane |
| `PIN_*`, `NOSHOW_*`, `LOGIN_*`, `PASSWORD_RESET_MAX_REQUESTS`, `REFUND_DEADLINE_HOURS`, `PICKUP_WINDOW_MINUTES`, `DEFAULT_PREPARATION_TIME_MINUTES`, `DEFAULT_CAPACITY` | users/orders/policy | Optional | template defaults | none — policy knobs |
| `UNIVERSITY_EMAIL_PATTERNS` | users derivation | Only if email format differs | *(code default: `lgu.edu.pk` patterns)* | JSON regex map; defined in code by default |
| `NEXT_PUBLIC_API_URL` | `apps/web/src/lib/api.ts` (web bundle) | **Yes — build time, web only** | `https://api.<domain>/api/v1` in `apps/web/.env.production.local` | **Not read at runtime** — baked into bundle; wrong value silently calls wrong host; verify `apps/web/out` contains no `localhost`/`example.com` |
| Mobile `API_BASE_URL` | `apps/mobile/src/config.ts` (hardcoded per env) | Yes for mobile builds | `https://api.<domain>/api/v1` replacing `https://api.uniserve.app/api/v1` | not env-driven; selected by EAS channel (`expo-constants` extra.eas.channel) |

## 5. SMTP provisioning checklist

- **Application readiness: DONE.** `SMTPEmailProvider` (`apps/api/app/core/email.py`) is provider-neutral stdlib SMTP; `available()` requires `SMTP_HOST` + `SMTP_FROM_EMAIL`; fail-closed contract — transport failure is logged and reported, never faked, and never raises into the auth flow; OTP hashing/expiry/attempts unaffected. Boot guard rejects `SMTP_TLS_MODE=none` in production.
- **Owner action (external):** provision an SMTP account (university mail relay or transactional provider) → fills `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_TLS_MODE`. Confirm the provider permits the From domain (SPF/DKIM is provider-side).
- **Live delivery test (after deploy):** register a real account → check inbox for the OTP email → complete verification → also verify resend cooldown + failure path (wrong From/host → API reports email failure, no fake success).
- **Without SMTP:** system still deploys; OTP self-serve onboarding cannot deliver codes (fail-closed); admin can still create accounts out-of-band (`scripts/create_live_accounts.py`). No code change needed or permitted for this.

## 6. Domain/DNS/Caddy checklist

1. Owner registers domains; creates DNS records: `A api <server-ip>`, `A app <server-ip>`; verify `dig +short` both.
2. Edit `infrastructure/caddy/Caddyfile` — **replace exactly two lines**: `api.example.com {` → `api.<domain> {`, `app.example.com {` → `app.<domain> {`.
3. **Do not touch** `try_files {path} {path}.html {path}/index.html /index.html` (Phase 33 deep-link fix) or the `reverse_proxy uniserve_api:8000` target. Caddy auto-issues/renews Let's Encrypt certs (ports 80/443 must stay open); do not hand-edit TLS.
4. Verify post-deploy: `https://<api-domain>/api/v1/health` → 200; `https://<app-domain>/login` → route-specific HTML (deep links).

## 7. VPS/server checklist

1. Server per §3 #1; run `scripts/vps/run-all.sh` (verify → update → Docker → deploy user → SSH hardening → firewall (22/80/443 only) → `/opt/uniserve` → post-reboot verify).
2. Clone repo to `/opt/uniserve`, checkout `7b3a5e8` (or the then-current release commit).
3. `cp .env.production.example .env.production`; generate secrets (§4); set real `CORS_ORIGINS`; `chmod 600 .env.production`. (The local rehearsal `.env.production` has strong secrets but **rehearsal CORS origins** — review/rotate before use, or generate fresh on the server.)
4. `npm ci --ignore-scripts` from **repo root** (root lockfile covers all workspaces; plain `npm ci` fails on react-native-screens' install script).
5. Build web on the server with real `NEXT_PUBLIC_API_URL` (§4); confirm `apps/web/out/index.html` + zero localhost/example references in `out/`.
6. `docker compose -f docker-compose.prod.yml build api`.
7. **Migration order:** `up -d postgres` → wait healthy → `run --rm api alembic upgrade head` → `alembic current` = `0009` → `alembic check` (no drift). Migrations are manual; take a backup before every migration on an existing DB; never blind-`downgrade`.
8. `up -d` → `restart caddy` (pick up web export) → all healthy/Up.
9. Post-deploy: backups cron (§10), first backup immediately after seeding (first deploy has no prior backup), smoke test per `PRODUCTION_DEPLOYMENT_CHECKLIST.md` §7 (includes: payments must still 503; logs contain no secrets; api/postgres ports unpublished).
10. Rollback reference: `UPDATE_ROLLBACK_PROCEDURE.md` + runbook "Update & Rollback" (code/web/Caddy/config/migration rollback paths).

## 8. Mobile/EAS checklist

- **Config location:** production API URL is hardcoded in `apps/mobile/src/config.ts` → `ENV.production.API_BASE_URL` (committed placeholder `https://api.uniserve.app/api/v1` must be replaced with the real API domain; staging placeholder also exists — replace or delete before staging builds). Selected by EAS channel via `Constants.expoConfig.extra.eas.channel`.
- **EAS profiles (`apps/mobile/eas.json`):** `development` (internal, dev client), `staging` (internal), `production` (channel `production`, autoIncrement). `submit.production.android.serviceAccountKeyPath = ./google-service-account.json` (**not in repo — owner supplies**), `track: internal`; `submit.production.ios.appleId/ascAppId` empty — owner fills.
- **Owner supplies:** Expo account + EAS credentials (`eas login`, EAS CLI ≥ 5); Android: Play service account JSON + signing keystore; iOS: Apple Developer account, certs/profiles (EAS can manage or upload).
- **Validated locally (no external access):** `npm run type-check:mobile`; `grep -n 'API_BASE_URL' apps/mobile/src/config.ts` (production value = real domain, no localhost); `eas build --platform all --profile production` only when credentials exist.
- **Not runnable here:** no Expo account/credentials exist — no EAS build attempted (per constraints).

## 9. JazzCash integration gate

- **Current state (verified in code):** provider registry contains only `test`; in production both `POST /payments/initiate/{order_id}` and `POST /payments/webhook/{provider}` raise HTTP 503 while the wired provider is the test provider (`apps/api/app/modules/payments/router.py` — fail-closed guard on both endpoints). Cash ordering is fully functional; online orders cannot reach a paid state. **Deploying without JazzCash is supported by design.**
- **Gate to enable online payments — ALL required, none invented:**
  1. Signed technical contract with JazzCash (official API docs, endpoints, signature scheme, sandbox + production URLs, merchant onboarding). Reference request already prepared: `PHASE_26B_JAZZCASH_TECHNICAL_REQUEST.md`.
  2. Real merchant credentials → `PAYMENT_MERCHANT_ID`, `PAYMENT_API_KEY`, `PAYMENT_API_SECRET`, `PAYMENT_WEBHOOK_SECRET`, `PAYMENT_CALLBACK_URL=https://api.<domain>/api/v1/payments/webhook/jazzcash`, `PAYMENT_PROVIDER=<registered-name>`, `PAYMENT_ENVIRONMENT=production` — server-side `.env.production` only.
  3. Provider adapter implemented under `apps/api/app/modules/payments/providers/` implementing the existing `PaymentProvider` ABC (server-authoritative amounts, signature-first webhook verification, idempotent processing), registered in `PROVIDER_REGISTRY`, plus tests — a separate engineering phase gated on step 1.
- **Until then:** initiation + webhooks return 503 — this is correct behavior, not an outage. Never configure guessed endpoints/signatures.

## 10. Backup/restore checklist

- **Backup script (repo, unchanged):** `scripts/backup_database.sh [dir]` — `pg_dump -Fc -Z9` inside `uniserve_postgres` (defaults `uniserve_prod`/`uniserve`, overridable via `POSTGRES_USER`/`POSTGRES_DB` env), verifies via `pg_restore --list` before copying out, prunes `uniserve_*.pgdump` >30 days, default dir `./backups`.
- **Server setup:** `mkdir -p /opt/uniserve/backups`; test once manually; cron `0 2 * * * cd /opt/uniserve && ./scripts/backup_database.sh /opt/uniserve/backups`; **copy dumps off the machine** (retention on the server alone does not survive server loss).
- **Restore (owner must know before launch):** `docker compose -f docker-compose.prod.yml stop api` → `CONFIRM=yes ./scripts/restore_database.sh backups/uniserve_<ts>.pgdump` (gate + pre-verify built in) → `up -d api` → `alembic current` = head → readiness ready. Prerequisite: target DB has `public` schema (`pg_dump` does not emit `CREATE SCHEMA public`).
- **Migration safety:** backup immediately before every `alembic upgrade head` on an existing DB; first deploy → backup right after first successful seed.

## 11. Monitoring/operations checklist

- **Endpoints:** `GET /api/v1/health` = liveness (no DB; used by api container healthcheck); `GET /api/v1/health/ready` = DB connectivity + schema presence (`status: ready|degraded`, `database`, `schema` fields — HTTP 200 even when degraded; alert on non-`ready` body).
- **Container states:** api/postgres → `healthy`; caddy → `Up` (no healthcheck defined). `restart: unless-stopped` + `systemctl enable docker` for boot survival.
- **Logs:** API structlog JSON (`LOG_FORMAT=json`, `LOG_LEVEL=INFO`); Caddy JSON access logs to stdout — all via `docker compose -f docker-compose.prod.yml logs`. Spot-check for leakage: `logs api | grep -Eic "password|secret|token|bearer"` → 0. No log-rotation config in repo — operator may set Docker daemon `json-file` rotation (optional, operator side).
- **Smoke script:** `python3 scripts/production_health_check.py --api-url https://<api-domain>` (runbook Step 19).
- **External monitoring (owner):** uptime poll of `/api/v1/health/ready`; alert on degraded/non-200; optional error-rate alerts on `"level":"error"` in API logs. No APM/alerting ships in the repo.
- **Ops references (unchanged):** `PRODUCTION_RUNBOOK.md` (operations/troubleshooting), `DATABASE_OPERATIONS.md`, `DEPLOYMENT_RUNBOOK.md` (first deploy + rollback).

## 12. Exact deployment sequence

Order matters; steps 1–4 are external prerequisites, 5–12 are execution (per `PRODUCTION_DEPLOYMENT_CHECKLIST.md`, which remains the executable checklist):

```
1.  [EXT] VPS + SSH                    (§3 #1–2)
2.  [EXT] Domains + DNS A records      (§3 #3)
3.  [REPO] Server at /opt/uniserve @ release commit; .env.production generated + chmod 600 (§7.2–3)
4.  [EXT/OP] Caddyfile two domain lines replaced (§6)
5.  [OP] npm ci --ignore-scripts (repo root) → web build with real NEXT_PUBLIC_API_URL (§7.4–5)
6.  [REPO] docker compose build api    (§7.6)
7.  [REPO] up postgres → healthy → alembic upgrade head → current=0009 → alembic check (§7.7)
8.  [REPO] up -d → restart caddy → health + readiness 200 (§7.8)
9.  [OP] backups cron + off-machine copy + first backup after seed (§10)
10. [OP] Smoke test: checklist §7 items incl. payments 503, no-secret logs, unpublished db/api ports
11. [OP] First admin + cafeteria + menu + ordering verification (runbook Steps 11–16)
12. [EXT/OP] External uptime monitor (§3 #11); SMTP live test if provisioned (§5)
```

## 13. MUST NOT be attempted without external credentials/access

Real VPS/SSH connections · domain registration/DNS changes · real `.env.production` secret generation on behalf of the owner · SMTP account creation or credential guessing · JazzCash endpoints/signatures/webhooks/sandbox behavior invention or any provider adapter without the signed contract · EAS production builds without an Expo account · Play Store/App Store submissions (incl. `google-service-account.json` fabrication) · pushing to remote · enabling the test payment provider in production · weakening the 503 guards, startup guards, or Caddy `try_files` line · dependency upgrades or UI redesign under this phase.

## 14. Final remaining blockers

| Blocker | Status | Unblocks |
|---|---|---|
| B1 VPS + B2 SSH | **open — owner** | everything |
| B3 domains/DNS + B4 real Caddyfile domains + B8 real `CORS_ORIGINS` | **open — owner** | HTTPS, web/API URLs |
| B5 server-side web build (real `NEXT_PUBLIC_API_URL`) | open — executes at deploy | web artifact |
| B6 mobile production URL + Expo/store credentials | open — owner | mobile builds only |
| B7 server-side `.env.production` (secrets reviewed/rotated, real CORS) | open — owner | api/postgres boot |
| B9 git hosting reachable (push or tree transfer) | open — owner | code delivery |
| B10 payment provider contract | **optional — by design** | online payments only (fail-closed 503 meanwhile) |
| SMTP account | open — owner | OTP self-serve email (deploy works without) |

**No application blockers remain.** Repo-side deployment tooling (compose, Caddy, VPS scripts, backup/restore, runbooks, fail-closed guards) is complete and validated locally.

**Documentation drift (reported, not silently fixed):** `PRODUCTION_DEPLOYMENT_CHECKLIST.md` §2 states "SMTP — not implemented; notifications are in-app only" — this is stale: `SMTPEmailProvider` shipped in Phase 36 (§5 of this doc is authoritative). `DEPLOYMENT_BLOCKERS.md` cites superseded commit `70ae399`; the deployable commit is `7b3a5e8`.

---

## Phase 39 validations run (this phase)

- `git status` — clean at start (`7b3a5e8`) and after commit.
- `docker compose -f docker-compose.prod.yml config --quiet` → **OK**; `docker compose -f docker-compose.yml config --quiet` → **OK**.
- `.env.production` shape review (names/lengths only): `APP_ENV=production`, `APP_DEBUG=false`, secrets set (86/86/43 chars — strong class), no `SMTP_*`/`PAYMENT_PROVIDER` entries (fail-closed paths active), **CORS contains rehearsal origins — must be replaced (§4, §7.3)**.
- Git hygiene: `.env.production` + `apps/web/.env.production.local` ignored; only `.example` templates tracked; `apps/mobile/google-service-account.json` absent (owner-supplied).
- Backend tests / type-checks: **not re-run** — no application or frontend configuration changes made in this phase (per task constraint).
