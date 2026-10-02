# UniServe — Production Runbook

Operational runbook for deploying, migrating, backing up, restoring, and
recovering UniServe in production using the Docker Compose topology
(`docker-compose.prod.yml`). Every procedure below was rehearsed locally in
Phase 28A (see `PHASE_28A_RELEASE_ENGINEERING_REHEARSAL.md`) before being
documented here.

> **Payment provider status:** online payments are **fail-closed**. The only
> wired provider is the test provider, which is rejected in production
> (HTTP 503) until a real provider (JazzCash) is provisioned externally.
> JazzCash integration is **blocked externally** — do not attempt to enable
> online payments before that work lands.

---

## 1. Architecture (docker-compose.prod.yml)

| Service    | Image                   | Host ports | Internal ports | Purpose                                  |
|------------|-------------------------|------------|----------------|------------------------------------------|
| `caddy`    | `caddy:2-alpine`        | **80, 443**| —              | TLS termination, static web, API proxy  |
| `api`      | built from `apps/api`   | *(none)*   | 8000           | FastAPI application (2 uvicorn workers)  |
| `postgres` | `postgres:16-alpine`    | *(none)*   | 5432           | Primary database (compose volume key `postgres_data`; actual Docker volume is `uniserve-prod_postgres_data`, i.e. `<project>_<key>`) |

Key properties (verified in rehearsal):

- The API and PostgreSQL are **never published on host ports** — only Caddy is
  reachable from the network. Verify anytime with `docker port <container>`.
- The compose project has a fixed name (`name: uniserve-prod`) so its database
  volume (`uniserve-prod_postgres_data`) can never be confused with the
  development stack's volume (`uniserve_postgres_data`).
- Container names are fixed (`uniserve_caddy`, `uniserve_api`,
  `uniserve_postgres`) — **the development stack must be stopped first**
  (`docker compose down`) because it uses the same container names.
- Caddy serves the static Next.js export from `apps/web/out` (read-only bind
  mount) and reverse-proxies `/api/…` to `uniserve_api:8000`.
- The API does **not** auto-migrate on startup. Migrations are a deliberate,
  manual step (section 4).
- **Background workers run inside the API process.** The pickup-expiry worker
  starts from the FastAPI lifespan hook and ticks every 60 seconds
  (`_PICKUP_CHECK_INTERVAL` in `apps/api/app/main.py`). uvicorn runs with
  `--workers 2`, so each worker process runs its own tick — safe by design:
  the expiry query uses `SELECT ... FOR UPDATE SKIP LOCKED`, so concurrent
  ticks never double-process an order. **Do not deploy a separate worker
  container** — it would duplicate the same in-process worker with no benefit.
- **Redis is not required at runtime** (verified Phase 30): no Redis client is
  imported anywhere in `apps/api/app`; the prod compose ships Redis
  commented out.

## 2. Prerequisites

- Docker Engine 24+ and Docker Compose v2 (rehearsed on Docker 29.8.0 /
  Compose v5.5.1).
- `.env.production` in the project root (git-ignored; never commit it).
  The root `.env.example` is the **development** template — do not use it for
  production. Create the production file from the production template:

  ```bash
  cp .env.production.example .env.production
  ```

  Then set at minimum:

  - `APP_SECRET_KEY` — 64+ random chars (`openssl rand -base64 48`)
  - `JWT_SECRET_KEY` — 64+ random chars (`openssl rand -base64 48`)
  - `POSTGRES_PASSWORD` — 32+ random chars (`openssl rand -base64 32`)
  - `APP_ENV=production` and `APP_DEBUG=false`

  **These values are validated at startup (fail-closed):** default or
  empty/whitespace secret keys, `APP_DEBUG=true`, or a `POSTGRES_PASSWORD`
  that is empty, the development default, or shorter than 12 characters —
  with `APP_ENV=production` — crash the API on boot. This is intentional:
  a misconfigured production must not come up.

- For the web app build: create `apps/web/.env.production.local` (git-ignored;
  this is the filename `apps/web/.env.production.example` instructs — Next.js
  loads both `.env.production` and `.env.production.local` in production
  builds) containing:

  ```bash
  NEXT_PUBLIC_API_URL=https://<api-domain>/api/v1
  ```

  The value is baked into the client bundle at build time.
- Real domains configured in `infrastructure/caddy/Caddyfile` (Caddy obtains
  and renews Let's Encrypt certificates automatically; keep ports 80/443 open
  for ACME challenges). VPS provisioning, DNS records and certificate
  specifics are covered in `DEPLOYMENT_RUNBOOK.md`.

## 3. First-time deployment

```bash
# 0. Stop the dev stack if this machine also runs it (container-name collision)
docker compose down

# 1. Build the API image
docker compose -f docker-compose.prod.yml build api

# 2. Start PostgreSQL only and wait for healthy
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml ps   # wait for "healthy"

# 3. Run migrations (see section 4)
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 4. Start the full stack
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # api+postgres "healthy"; caddy "Up"

# 5. Build and export the web app on the host, then reload Caddy
#    (create apps/web/.env.production.local first — see section 2)
#    Dependency note (Phase 32): the root package-lock.json is committed and
#    covers all npm workspaces. Install from the REPO ROOT with `npm ci
#    --ignore-scripts` (plain `npm ci` fails: react-native-screens' install
#    script expects dev-only tooling that is never installed for dependencies).
npm ci --ignore-scripts
( cd apps/web && npm run build )   # emits apps/web/out (static export)
docker compose -f docker-compose.prod.yml restart caddy

# 6. Run the post-deployment verification sequence (section 11)
```

## 4. Database migrations

Migrations run **manually and explicitly** — never implicitly on startup:

```bash
# Apply migrations
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Confirm the expected revision (currently 0009)
docker compose -f docker-compose.prod.yml run --rm api alembic current
```

Rules:

- Take a backup (section 5) before applying migrations to production.
- `alembic upgrade head` is idempotent — already-applied revisions are skipped.
- If the API is running while you migrate, restart it afterwards so it picks
  up any schema-dependent behavior: `docker compose -f docker-compose.prod.yml restart api`.

If a migration fails:

- **Fresh/empty database:** the failure is not destructive. Fix the cause
  (credentials, connectivity, migration file) and re-run `alembic upgrade head`.
- **Existing production database:** restore the pre-migration backup
  (section 6). This is the safe recovery path — take it before attempting
  anything clever.
- **Do not use `alembic downgrade` as a production rollback.** Every revision
  in this repository implements `downgrade()`, but each one is a *destructive
  schema reversal* (`drop_table`/`drop_column` on `users`, `orders`,
  `payments`, etc.) — it removes data-bearing structures, not just schema.
  Downgrade is only appropriate on empty/dev databases.

## 5. Backup

`scripts/backup_database.sh` produces a compressed custom-format dump:

```bash
./scripts/backup_database.sh                     # -> ./backups/uniserve_<ts>.pgdump
./scripts/backup_database.sh /backups/uni        # custom destination
```

- Runs `pg_dump` **inside** the container (PostgreSQL has no host port), then
  copies the dump to the host.
- Verifies each dump with `pg_restore --list` inside the container before it
  is copied out; the script exits non-zero on any failure.
- Retention: dumps older than 30 days in the backup directory are deleted.
- Copy dumps off the machine (object storage / another host). A backup that
  only lives on the database server does not survive the server.
- Cron (daily 02:00): `0 2 * * * /path/to/UniServe/scripts/backup_database.sh /backups/uni`

> Windows developers: Git Bash rewrites POSIX paths passed to `docker exec`.
> Prefix the script with `MSYS2_ARG_CONV_EXCL='*'` or the container-side
> `/tmp` path will be mangled. This does not apply on Linux servers.

## 6. Restore (rehearsed — backup → schema wipe → restore → verify)

**Disaster-recovery procedure.** The rehearsal destroyed the entire public
schema and recovered it from a section-5 backup; follow exactly these steps:

```bash
# 1. Stop the API — writes must not race the restore
docker compose -f docker-compose.prod.yml stop api

# 2. Restore the dump (CONFIRM=yes is mandatory — the script refuses without
#    it; the dump is verified with pg_restore --list before anything destructive)
CONFIRM=yes ./scripts/restore_database.sh backups/uniserve_<ts>.pgdump

# 3. Verify schema revision
docker compose -f docker-compose.prod.yml run --rm api alembic current   # -> 0009 (head)

# 4. Restart the API and verify readiness
docker compose -f docker-compose.prod.yml up -d api
curl -fsS https://<api-domain>/api/v1/health/ready
```

Success criteria: `alembic current` prints the head revision, readiness
returns `"status": "ready", "schema": "present"`, and pre-backup rows are
visible (spot-check with `psql` inside the container).

The restore script defaults (`DB_USER=uniserve`, `DB_NAME=uniserve_prod`,
container `uniserve_postgres`) match `.env.production.example`. If you renamed
the database user/name, override them explicitly:

```bash
CONFIRM=yes DB_USER=<user> DB_NAME=<db> ./scripts/restore_database.sh backups/uniserve_<ts>.pgdump
```

## 7. Health checks & monitoring

| Endpoint             | Meaning                                                                 |
|----------------------|-------------------------------------------------------------------------|
| `GET /api/v1/health`        | **Liveness** — process is up (no DB). Used by the container healthcheck. |
| `GET /api/v1/health/ready`  | **Readiness** — DB connectivity **and** core schema present.            |

Readiness semantics (since Phase 28A):

- `{"status":"ready","database":"connected","schema":"present"}` — fully operational.
- `{"status":"degraded","database":"disconnected"}` — database unreachable.
- `{"status":"degraded","database":"connected","schema":"missing"}` — database
  answers queries but the application schema is gone (wiped/never-migrated).
  **Treat as an outage and execute section 6.**

Monitor both endpoints; alert on any non-`ready` readiness response.

Container health: `docker compose -f docker-compose.prod.yml ps` — `api` and
`postgres` must show **healthy**; `caddy` has no healthcheck defined in the
compose file, so **Up/running** (not `healthy`) is its success state.

## 8. Routine operations

```bash
# Logs (structlog JSON on the API; Caddy access logs on stdout)
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs --tail 200 caddy

# Restart a service
docker compose -f docker-compose.prod.yml restart api

# Deploy a new API build
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml up -d api

# Deploy new web assets (static export, no container rebuild)
( cd apps/web && npm run build )
docker compose -f docker-compose.prod.yml restart caddy
```

Container logs were scanned in rehearsal for credential leakage — the API,
PostgreSQL, and Caddy logs contained **no** secrets, tokens, or passwords.

## 9. Failure & recovery playbook

| Symptom | Diagnosis | Action |
|---|---|---|
| API container restarting / unhealthy | Misconfiguration (secrets/debug) or crash | `docker compose -f docker-compose.prod.yml logs api` — startup rejects default secrets or `APP_DEBUG=true` in production **by design**. Fix `.env.production`, then `up -d api`. |
| Readiness `degraded` + `disconnected` | PostgreSQL down | `docker compose -f docker-compose.prod.yml up -d postgres`; verify healthy; readiness recovers automatically. |
| Readiness `degraded` + `schema: missing` | Schema wiped / never migrated | Restore per section 6 (or run migrations on an empty DB per section 4). |
| `HTTP 503` on online payment initiation | No production payment provider configured | **Expected fail-closed behavior** until JazzCash (or another provider) is provisioned externally. Not an outage. |
| Web pages error / blank | Stale or missing static export | Rebuild `apps/web/out` (section 3 step 5) and `restart caddy`; confirm `apps/web/out/index.html` exists on the host. |
| Caddy returns 502/504 for API calls | Caddy cannot reach the API upstream | `docker compose -f docker-compose.prod.yml ps` (api healthy?); `docker compose -f docker-compose.prod.yml logs --tail 100 caddy api`; restart api if needed. |
| Login fails for everyone | Auth service or DB issue, or token/config mismatch | Check api logs and readiness; confirm `JWT_SECRET_KEY` has not changed (a change invalidates all existing sessions — users must log in again). |
| `HTTP 401/403` on API calls | Auth/session issue | Check `Authorization: Bearer <access token>`; tokens expire — access **30 min**, refresh **7 days** with the provided `.env.production.example` (code defaults are 30 min / 30 days if the variables are unset). |
| Caddy cannot obtain certificates | Domain/DNS issue | Confirm DNS A records point at the server and ports 80/443 are reachable. Placeholder domains (e.g. `example.com`) are refused by Let's Encrypt **by design**. |
| Port conflict on `up` | Dev stack still running | `docker compose down` (dev), then start the prod stack. |

### Rollback vs recovery — they are different things

**Application rollback** (code only, no data change):

- API: `git checkout <last-good-commit> && docker compose -f docker-compose.prod.yml build api && docker compose -f docker-compose.prod.yml up -d api`
- Web: `git checkout <last-good-commit> && npm ci --ignore-scripts && (cd apps/web && npm run build) && docker compose -f docker-compose.prod.yml restart caddy`
- Environment: keep a copy of the previous `.env.production` before every
  edit (`cp .env.production .env.production.bak-<ts>`) and restore it the
  same way, then restart the api.

**Database recovery** (data/schema, with data consequences):

- Bad migration on an existing database: **restore the pre-migration backup**
  (section 6). Do not `alembic downgrade` in production — downgrades drop
  data-bearing tables/columns (section 4).
- Lost/corrupted data: restore the most recent backup you can accept
  (section 6) and accept the loss since that snapshot.

A backup taken **before** every migration is what makes both paths possible.

## 10. Production security checklist (verified)

Run through before declaring an environment live:

- [ ] `.env.production` exists, is git-ignored, and contains **generated**
      `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` (no defaults,
      no shared values with development).
- [ ] `APP_ENV=production` and `APP_DEBUG=false` (startup **fails closed**
      otherwise — default secrets or `APP_DEBUG=true` prevent boot).
- [ ] `CORS_ORIGINS` lists only the real web origin(s) as JSON, e.g.
      `["https://app.<domain>"]` (default is localhost-only).
- [ ] `LOG_LEVEL=INFO` (not DEBUG) and `LOG_FORMAT=json`.
- [ ] Database not exposed: `docker port uniserve_postgres` prints nothing.
- [ ] API not exposed: `docker port uniserve_api` prints nothing.
- [ ] Only Caddy is reachable: ports 80/443 published, nothing else.
- [ ] HTTPS prerequisite: real domains in `infrastructure/caddy/Caddyfile`,
      DNS A records pointing at the server, ports 80/443 open for ACME.
- [ ] Session config reviewed: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30`,
      `JWT_REFRESH_TOKEN_EXPIRE_DAYS=7` (template values); changing
      `JWT_SECRET_KEY` later invalidates all sessions.
- [ ] Logs contain no secrets (spot-check: `docker compose -f
      docker-compose.prod.yml logs api | grep -Ei "password|secret|token"`
      → only expected config-free lines; rehearsal scan found 0 matches).
- [ ] Backups land outside the database server (off-machine copy scheduled);
      `backups/` is git-ignored.
- [ ] File permissions on the server: `.env.production` readable only by the
      deploy user (`chmod 600 .env.production`); repo owned by that user.
- [ ] Online payments **fail-closed**: `PAYMENT_PROVIDER` unset/test →
      initiation returns HTTP 503 in production. JazzCash is externally
      blocked — do not weaken this guard.
- [ ] Web export contains no backend secrets (only `NEXT_PUBLIC_API_URL`);
      mobile build contains no backend secrets (EAS channel endpoint map).

Summary of verified posture (no new architecture introduced):

- API and PostgreSQL expose **no host ports** — network access is Caddy-only.
- Startup validation is fail-closed: default `APP_SECRET_KEY`/`JWT_SECRET_KEY`
  or `APP_DEBUG=true` with `APP_ENV=production` prevents boot.
- `APP_DEBUG=false` in production keeps `/api/docs`, `/api/redoc` and
  `/api/openapi.json` unmounted.
- Web static export contains no backend secrets (only
  `NEXT_PUBLIC_API_URL`). Mobile builds contain no backend secrets
  (endpoint map keyed by EAS channel).
- Online payments fail closed (HTTP 503) — no provider credentials exist in
  the repository or in `.env.production.example`.
- The developer database volume (`uniserve_postgres_data`) is separate from
  the production volume (`uniserve-prod_postgres_data`) and is never touched
  by production operations.

## 11. Post-deployment verification sequence

Run in order after every deployment (each step uses existing tools/scripts —
no fake payment success is ever created):

```bash
# 1+2. Containers healthy (api, postgres healthy; caddy Up — no healthcheck)
docker compose -f docker-compose.prod.yml ps

# 3. Migrations at expected head
docker compose -f docker-compose.prod.yml run --rm api alembic current   # -> 0009 (head)

# 4. API liveness + readiness (expect "ready" + "schema": "present")
curl -fsS https://<api-domain>/api/v1/health
curl -fsS https://<api-domain>/api/v1/health/ready
#    (or the helper: python scripts/production_health_check.py --api-url https://<api-domain>)

# 5. Web page loads (static export served by Caddy)
curl -fsS https://<app-domain>/ | head -c 200        # expect HTML, not an error shell
```

Steps 6–10 (login, role separation, cafeteria isolation, menu, order
lifecycle) are covered by the existing E2E suite, which exercises exactly
those flows against a running API:

```bash
# 6-10. login + role separation + cafeteria isolation + menu + order lifecycle
#        (+ notifications, scheduled orders, edge cases) — 31 checks
python scripts/phase19_e2e_test.py
#    BASE defaults to http://localhost:8000/api/v1; override with
#    UNISERVE_E2E_BASE_URL=https://<api-domain>/api/v1 if pointing at a
#    non-local environment. The accounts are seeded test accounts
#    (scripts/seed_realistic_data.py) — run against staging/dev, NOT production.
#    NOTE: against a production-guarded deployment the payment-initiation
#    check fails with HTTP 503 by design — 30/31 with that single failure is
#    the expected fail-closed verification result, not a regression.
```

```bash
# 11. Logs contain no secrets
docker compose -f docker-compose.prod.yml logs api 2>&1 | grep -Eic "password|secret|token|bearer"
#    expect 0 matches (rehearsal baseline)

# 12. Online payment remains fail-closed (expect HTTP 503 in production)
#    Initiate an online checkout as a test user and POST
#    /api/v1/payments/initiate/<order_id> — production must return 503
#    "Online payments are unavailable: no production payment provider is
#    configured". A 2xx here means the guard was weakened — stop and fix.
```

## 12. What is NOT covered here (blocked externally)

- **JazzCash integration** — credential provisioning, merchant onboarding,
  signing/webhook contract confirmation with JazzCash, and the provider
  implementation itself are externally blocked. Until completed and audited,
  production online payments remain disabled (fail-closed 503). Do not
  weaken the guard to "make payments work".
- **Domain/DNS/certificate configuration** — performed once per environment,
  outside this runbook's rehearsal scope.
