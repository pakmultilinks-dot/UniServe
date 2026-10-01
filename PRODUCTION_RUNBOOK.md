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
| `postgres` | `postgres:16-alpine`    | *(none)*   | 5432           | Primary database (volume `postgres_data`)|

Key properties (verified in rehearsal):

- The API and PostgreSQL are **never published on host ports** — only Caddy is
  reachable from the network. Verify anytime with `docker port <container>`.
- The compose project has a fixed name (`name: uniserve-prod`) so its database
  volume can never be confused with the development stack's volume.
- Container names are fixed (`uniserve_caddy`, `uniserve_api`,
  `uniserve_postgres`) — **the development stack must be stopped first**
  (`docker compose down`) because it uses the same container names.
- Caddy serves the static Next.js export from `apps/web/out` (read-only bind
  mount) and reverse-proxies `/api/…` to `uniserve_api:8000`.
- The API does **not** auto-migrate on startup. Migrations are a deliberate,
  manual step (section 4).

## 2. Prerequisites

- Docker Engine 24+ and Docker Compose v2 (rehearsed on Docker 29.8.0 /
  Compose v5.5.1).
- `.env.production` in the project root (git-ignored; never commit it).
  Create it from the template:

  ```bash
  cp .env.production.example .env.production
  ```

  Then set at minimum:

  - `APP_SECRET_KEY` — 64+ random chars (`openssl rand -base64 48`)
  - `JWT_SECRET_KEY` — 64+ random chars (`openssl rand -base64 48`)
  - `POSTGRES_PASSWORD` — 32+ random chars (`openssl rand -base64 32`)
  - `APP_ENV=production` and `APP_DEBUG=false`

  **These values are validated at startup (fail-closed):** default secrets or
  `APP_DEBUG=true` with `APP_ENV=production` crash the API on boot. This is
  intentional — a misconfigured production must not come up.

- For the web app build: `apps/web/.env.production` with
  `NEXT_PUBLIC_API_URL=https://<api-domain>/api/v1`.
- Real domains configured in `infrastructure/caddy/Caddyfile` (Caddy obtains
  and renews Let's Encrypt certificates automatically; keep ports 80/443 open
  for ACME challenges).

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
docker compose -f docker-compose.prod.yml ps   # all services healthy

# 5. Build and export the web app on the host, then reload Caddy
( cd apps/web && npm ci && npm run build )   # emits apps/web/out (static export)
docker compose -f docker-compose.prod.yml restart caddy
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

## 5. Backup

`scripts/backup_database.sh` produces a compressed custom-format dump:

```bash
./scripts/backup_database.sh                     # -> ./backups/uniserve_<ts>.pgdump
./scripts/backup_database.sh /backups/uni        # custom destination
```

- Runs `pg_dump` **inside** the container (PostgreSQL has no host port), then
  copies the dump to the host.
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

# 2. Restore the dump (replaces current contents; --clean --if-exists)
./scripts/restore_database.sh backups/uniserve_<ts>.pgdump

# 3. Verify schema revision
docker compose -f docker-compose.prod.yml run --rm api alembic current   # -> 0009 (head)

# 4. Restart the API and verify readiness
docker compose -f docker-compose.prod.yml up -d api
curl -fsS https://<api-domain>/api/v1/health/ready
```

Success criteria: `alembic current` prints the head revision, readiness
returns `"status": "ready", "schema": "present"`, and pre-backup rows are
visible (spot-check with `psql` inside the container).

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

Container health: `docker compose -f docker-compose.prod.yml ps` — all three
services must show `healthy`.

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
| `HTTP 401/403` on API calls | Auth/session issue | Check `Authorization: Bearer <access token>`; tokens expire (30 min access / 30 days refresh). |
| Caddy cannot obtain certificates | Domain/DNS issue | Confirm DNS A records point at the server and ports 80/443 are reachable. Placeholder domains (e.g. `example.com`) are refused by Let's Encrypt **by design**. |
| Port conflict on `up` | Dev stack still running | `docker compose down` (dev), then start the prod stack. |

Rollback of a bad API build: rebuild from the last known-good git commit and
`up -d api`. Rollback of a bad migration: restore the pre-migration backup
(section 6) — this is why section 5's rule (backup before migrating) exists.

## 10. Security posture (verified)

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

## 11. What is NOT covered here (blocked externally)

- **JazzCash integration** — credential provisioning, merchant onboarding,
  signing/webhook contract confirmation with JazzCash, and the provider
  implementation itself are externally blocked. Until completed and audited,
  production online payments remain disabled (fail-closed 503). Do not
  weaken the guard to "make payments work".
- **Domain/DNS/certificate configuration** — performed once per environment,
  outside this runbook's rehearsal scope.
