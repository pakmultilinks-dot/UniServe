# Production Stack Integration Audit

**Date**: 2026-09-30
**Baseline Commit**: `cf27bdd` — `feat: prepare UniServe for production deployment`
**Auditor**: Automated integration audit
**Status**: ⚠️ BLOCKERS FOUND AND FIXED — Ready for commit

---

## Executive Summary

The production deployment stack had **2 blocking issues** and **4 medium-severity issues** that would prevent a successful deployment. All have been fixed in this audit. The stack is now internally consistent.

| Metric | Count |
|--------|-------|
| Files inspected | 18 |
| Checks executed | 8 areas |
| Issues found | 6 (2 blocker, 4 medium) |
| Fixes applied | 6 |
| Remaining blockers | 0 |
| Files modified | 7 |

---

## Issues Found & Fixed

### BLOCKER 1: `web_static` volume never populated (FIXED)

**File**: `docker-compose.prod.yml`
**Severity**: BLOCKER
**Production Impact**: Caddy would serve an empty directory — web app completely broken.

The original `docker-compose.prod.yml` declared a `web_static` volume mounted at Caddy's `/srv`, but no service or mechanism existed to populate it. The `web` container wrote files to `/srv` in its own filesystem, not into the volume.

**Fix**: Replaced with bind mount `./apps/web/out:/srv:ro`. Static files are built on the server (`npm run build`) and served directly by Caddy via the host filesystem.

### BLOCKER 2: No web service in docker-compose.prod.yml (FIXED)

**File**: `docker-compose.prod.yml`
**Severity**: BLOCKER
**Production Impact**: No mechanism to build or serve the web application.

The original compose file had no `web` service. The `web_static` volume was empty with no way to fill it.

**Fix**: Removed the unused `web` container. Static files are built on the server and served by Caddy via bind mount. Updated `DEPLOYMENT_RUNBOOK.md` Step 7 with correct build commands.

### MEDIUM 1: `apps/web/Dockerfile` had no CMD (FIXED)

**File**: `apps/web/Dockerfile`
**Severity**: MEDIUM
**Production Impact**: Container would start and immediately exit.

The Dockerfile had `EXPOSE 80 443` but no `CMD` instruction.

**Fix**: Simplified to build-only Dockerfile (no second stage). Static output is at `/app/out` and extracted via `docker cp` or bind mount.

### MEDIUM 2: `apps/web/Caddyfile` had API proxy block (FIXED)

**File**: `apps/web/Caddyfile`
**Severity**: MEDIUM
**Production Impact**: Would conflict with infrastructure Caddyfile if both were used.

The web Caddyfile contained an API reverse proxy block (`:443 { reverse_proxy uniserve_api:8000 }`) that duplicated the infrastructure Caddyfile's functionality.

**Fix**: Simplified to a minimal development-only Caddyfile (`:8080` port). Production uses `infrastructure/caddy/Caddyfile`.

### MEDIUM 3: `DATABASE_OPERATIONS.md` used wrong port (FIXED)

**File**: `DATABASE_OPERATIONS.md`
**Severity**: MEDIUM
**Production Impact**: Backup commands would fail on production.

Documented `pg_dump` with `-p 5433` (dev port). Production PostgreSQL is internal-only at port 5432 — no host port exposed.

**Fix**: Added production warning. Changed backup commands to use `docker exec` (container-based). Added `-f docker-compose.prod.yml` to all compose commands.

### MEDIUM 4: `UPDATE_ROLLBACK_PROCEDURE.md` missing compose file flag (FIXED)

**File**: `UPDATE_ROLLBACK_PROCEDURE.md`
**Severity**: MEDIUM
**Production Impact**: Rollback commands would fail (would use `docker-compose.yml` instead of `docker-compose.prod.yml`).

Full Restore section used `docker compose stop api` without `-f docker-compose.prod.yml`.

**Fix**: Added `-f docker-compose.prod.yml` to all compose commands. Updated web rebuild steps to match new architecture.

---

## Area-by-Area Audit Results

### 1. Production Compose ✅ (after fixes)

| Check | Before Fix | After Fix |
|-------|-----------|-----------|
| Services defined | api, postgres, caddy | api, postgres, caddy |
| Caddy ports | 80, 443 (public) ✅ | 80, 443 (public) ✅ |
| API ports | Internal only ✅ | Internal only ✅ |
| PostgreSQL ports | Internal only ✅ | Internal only ✅ |
| Web static serving | BROKEN (empty volume) | ✅ Bind mount `./apps/web/out:/srv:ro` |
| Healthchecks | API + PostgreSQL ✅ | API + PostgreSQL ✅ |
| Restart policies | `unless-stopped` ✅ | `unless-stopped` ✅ |
| Environment injection | `.env.production` ✅ | `.env.production` ✅ |
| Dependency ordering | postgres → api → caddy ✅ | postgres → api → caddy ✅ |

### 2. API Container ✅

| Check | Result |
|-------|--------|
| Base image | `python:3.11-slim-bookworm` ✅ |
| System deps | `build-essential`, `libpq-dev` ✅ |
| Python deps | `pip install -e "."` (production only) ✅ |
| Application code | `COPY . .` ✅ |
| Startup command | `uvicorn app.main:app --workers 2` ✅ |
| Health endpoint | `/api/v1/health` (liveness) ✅ |
| Readiness endpoint | `/api/v1/health/ready` (DB check) ✅ |
| Alembic available | Yes (installed as dependency) ✅ |
| `httpx` available | Yes (for healthcheck) ✅ |
| Environment vars | From `.env.production` + compose overrides ✅ |
| `POSTGRES_HOST` override | `postgres` (Docker service name) ✅ |
| `reject_default_secrets` | Validates `APP_SECRET_KEY` and `JWT_SECRET_KEY` ✅ |
| Docs disabled in prod | `docs_url=None` when `APP_DEBUG=false` ✅ |
| Background worker | `_pickup_expiry_worker` (asyncio, 60s interval) ✅ |

### 3. Web + Caddy ✅ (after fixes)

| Check | Result |
|-------|--------|
| Static export | `output: "export"` in `next.config.js` ✅ |
| Build output | 23 routes in `apps/web/out/` ✅ |
| TypeScript check | Zero errors ✅ |
| Build success | All routes compiled ✅ |
| Caddyfile (infra) | `api.example.com` → API proxy, `app.example.com` → static files ✅ |
| Caddyfile (web) | Simplified to dev-only ✅ |
| Static file root | `/srv` (bind mount from `./apps/web/out`) ✅ |
| SPA fallback | `try_files {path} /index.html` ✅ |
| Cache headers | `/_next/static/*` → 1 year immutable, `/_next/image/*` → 1 day ✅ |
| Security headers | HSTS, X-Frame-Options, X-Content-Type-Options ✅ |
| API routing | `api.example.com` → `uniserve_api:8000` ✅ |
| Domain placeholders | `example.com` — requires user replacement ✅ |
| No localhost assumptions | Verified — all references use Docker service names ✅ |

### 4. Environment Variable Flow ✅

**Trace: `.env.production.example` → `docker-compose.prod.yml` → container → code**

| Variable | Example | Compose | Container | Code Location |
|----------|---------|---------|-----------|---------------|
| `APP_NAME` | UniServe | — | env_file | `config.py` |
| `APP_ENV` | production | — | env_file | `config.py` |
| `APP_DEBUG` | false | — | env_file | `config.py` |
| `APP_SECRET_KEY` | (generate) | — | env_file | `config.py` + validator |
| `POSTGRES_HOST` | postgres | `POSTGRES_HOST: postgres` | env_file + override | `config.py` → `DATABASE_URL` |
| `POSTGRES_PORT` | 5432 | `POSTGRES_PORT: 5432` | env_file + override | `config.py` → `DATABASE_URL` |
| `POSTGRES_USER` | uniserve | `${POSTGRES_USER}` | env_file | `config.py` → `DATABASE_URL` |
| `POSTGRES_PASSWORD` | (generate) | `${POSTGRES_PASSWORD}` | env_file | `config.py` → `DATABASE_URL` |
| `POSTGRES_DB` | uniserve_prod | `${POSTGRES_DB}` | env_file | `config.py` → `DATABASE_URL` |
| `JWT_SECRET_KEY` | (generate) | — | env_file | `config.py` + validator |
| `JWT_ALGORITHM` | HS256 | — | env_file | `config.py` |
| `CORS_ORIGINS` | `["https://app.example.com"]` | — | env_file | `config.py` → `CORSMiddleware` |
| `LOG_LEVEL` | INFO | — | env_file | `config.py` |
| `LOG_FORMAT` | json | — | env_file | `config.py` |
| `NEXT_PUBLIC_API_URL` | `https://api.example.com/api/v1` | Build arg | Build-time only | `next.config.js` |

**Findings**:
- ✅ All `.env.production.example` variables have corresponding code references
- ✅ `POSTGRES_HOST` is overridden to `postgres` (Docker service name) in compose
- ✅ Build-time vs runtime variables correctly separated
- ✅ No secrets hardcoded in any file
- ⚠️ `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000/api/v1` in web Dockerfile — must be overridden at build time

### 5. Database + Alembic ✅

| Check | Result |
|-------|--------|
| PostgreSQL image | `postgres:16-alpine` ✅ |
| Internal hostname | `postgres` (Docker service name) ✅ |
| Database URL construction | `postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}` ✅ |
| Alembic URL override | `env.py` overrides `alembic.ini` with `settings.DATABASE_URL` ✅ |
| Migration head | `0009` (checkout_idempotency) ✅ |
| Migration count | 10 files (0000–0009) ✅ |
| Drift check | No drift detected ✅ |
| Health/readiness | `pg_isready` (Docker) + `/api/v1/health/ready` (SQL SELECT 1) ✅ |
| Persistent volume | `postgres_data` → `/var/lib/postgresql/data` ✅ |
| Init script | `001_extensions.sql` (uuid-ossp, pg_trgm) ✅ |
| Timezone | `TZ=Asia/Karachi` ✅ |
| Connection pool | `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True` ✅ |
| Startup ordering | `postgres` healthy → `api` starts → migrations via `alembic upgrade head` ✅ |

### 6. Health Checks ✅

| Check | Target | Location | Result |
|-------|--------|----------|--------|
| Docker API healthcheck | `localhost:8000/api/v1/health` | Inside API container | ✅ Correct (container-local) |
| Docker PostgreSQL healthcheck | `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` | Inside PostgreSQL container | ✅ Correct (container-local) |
| Health check script default | `http://localhost:8000` | Host machine | ⚠️ Defaults to dev URL — runbook documents `--api-url` |
| Health check script production | `https://api.example.com` | Host machine | ✅ Correct when `--api-url` is used |

**Note**: The `localhost` in the API healthcheck is correct — it executes inside the API container itself. The health check script's default of `localhost:8000` is for development; the runbook documents using `--api-url https://api.example.com`.

### 7. Backup / Restore ✅ (after fixes)

| Check | Result |
|-------|--------|
| Backup script | `scripts/backup_database.sh` ✅ |
| Backup method | `docker exec uniserve_postgres pg_dump` ✅ |
| Container name | `uniserve_postgres` (matches compose) ✅ |
| Database name | `${POSTGRES_DB:-uniserve_prod}` (matches compose) ✅ |
| Backup format | `--format=custom --compress=9` (PostgreSQL 16 compatible) ✅ |
| Retention | 30 days (`-mtime +30`) ✅ |
| Cron-compatible | Yes (`0 2 * * *`) ✅ |
| Restore method | `docker exec -i uniserve_postgres pg_restore` ✅ |
| Restore safety | Stop API before restore ✅ |
| Documentation port | Fixed: was 5433, now uses container commands ✅ |
| Compose file flag | Fixed: all commands now use `-f docker-compose.prod.yml` ✅ |

### 8. Deployment Runbook Consistency ✅ (after fixes)

| Check | Before Fix | After Fix |
|-------|-----------|-----------|
| Compose file reference | `docker-compose.prod.yml` ✅ | ✅ |
| Web build step | Missing — no build instructions | ✅ Added `npm ci` + `npm run build` |
| Migration command | `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head` ✅ | ✅ |
| Health verification | `curl -s https://api.example.com/api/v1/health` ✅ | ✅ |
| Backup command | `./scripts/backup_database.sh` ✅ | ✅ |
| Crontab entry | `0 2 * * * /opt/uniserve/scripts/backup_database.sh /opt/uniserve/backups` ✅ | ✅ |
| Rollback commands | Missing `-f docker-compose.prod.yml` | ✅ Fixed |
| Web rebuild | Referenced removed `web` service | ✅ Fixed to `npm run build` |

---

## Environment Variable Cross-Reference

### Variables in `.env.production.example` but NOT in `config.py`:
- `APP_HOST` — Not read by `config.py` (Uvicorn uses `--host 0.0.0.0` from CMD)
- `APP_PORT` — Not read by `config.py` (Uvicorn uses `--port 8000` from CMD)
- `OTP_*` variables — Read by `config.py` ✅
- `PIN_*` variables — Read by `config.py` ✅
- `REFUND_DEADLINE_HOURS` — Read by `config.py` ✅
- `PICKUP_WINDOW_MINUTES` — Read by `config.py` ✅
- `DEFAULT_PREPARATION_TIME_MINUTES` — Read by `config.py` ✅
- `NOSHOW_*` variables — Read by `config.py` ✅
- `LOGIN_*` variables — Read by `config.py` ✅
- `PASSWORD_RESET_MAX_REQUESTS` — Read by `config.py` ✅

### Variables in `config.py` but NOT in `.env.production.example`:
- `DEFAULT_CAPACITY` — Has default value `10`, not documented in example (LOW)
- `NOSHOW_STUDENT_WINDOW_DAYS` — Has default value `30`, not documented (LOW)
- `NOSHOW_STUDENT_SUSPENSION_DAYS` — Has default value `7`, not documented (LOW)
- `NOSHOW_FACULTY_WINDOW_DAYS` — Has default value `30`, not documented (LOW)
- `NOSHOW_FACULTY_SUSPENSION_DAYS` — Has default value `3`, not documented (LOW)
- `UNIVERSITY_EMAIL_PATTERNS` — Complex dict, not suitable for env var (OK)

**Verdict**: No critical mismatches. The undocumented variables all have sensible defaults.

---

## Files Inspected

| # | File | Status |
|---|------|--------|
| 1 | `docker-compose.prod.yml` | Modified ✅ |
| 2 | `apps/api/Dockerfile` | Verified ✅ |
| 3 | `apps/web/Dockerfile` | Modified ✅ |
| 4 | `apps/web/next.config.js` | Verified ✅ |
| 5 | `apps/web/Caddyfile` | Modified ✅ |
| 6 | `infrastructure/caddy/Caddyfile` | Verified ✅ |
| 7 | `.env.production.example` | Verified ✅ |
| 8 | `apps/web/.env.production.example` | Verified ✅ |
| 9 | `apps/api/app/core/config.py` | Verified ✅ |
| 10 | `apps/api/app/core/database.py` | Verified ✅ |
| 11 | `apps/api/app/main.py` | Verified ✅ |
| 12 | `apps/api/app/api/health.py` | Verified ✅ |
| 13 | `apps/api/alembic.ini` | Verified ✅ |
| 14 | `apps/api/migrations/env.py` | Verified ✅ |
| 15 | `apps/api/pyproject.toml` | Verified ✅ |
| 16 | `scripts/production_health_check.py` | Verified ✅ |
| 17 | `scripts/backup_database.sh` | Verified ✅ |
| 18 | `DEPLOYMENT_RUNBOOK.md` | Modified ✅ |
| 19 | `DEPLOYMENT_ARCHITECTURE.md` | Modified ✅ |
| 20 | `UPDATE_ROLLBACK_PROCEDURE.md` | Modified ✅ |
| 21 | `DATABASE_OPERATIONS.md` | Modified ✅ |
| 22 | `apps/mobile/eas.json` | Verified ✅ |
| 23 | `apps/mobile/src/config.ts` | Verified ✅ |

---

## Production Architecture (Final)

```
Internet → Caddy (ports 80/443)
               ├── api.example.com → uniserve_api:8000 (reverse proxy)
               └── app.example.com → /srv (static files from ./apps/web/out)

uniserve_api → uniserve_postgres:5432 (internal network)
```

**Services in docker-compose.prod.yml:**
1. `caddy` — Caddy 2 Alpine, ports 80+443, serves static files + proxies API
2. `api` — FastAPI + Uvicorn (2 workers), internal port 8000, healthcheck via httpx
3. `postgres` — PostgreSQL 16 Alpine, internal port 5432, healthcheck via pg_isready

**Web deployment:** Static files built on server (`npm run build`), served by Caddy via bind mount.

---

## Remaining Items (Not Blockers)

| Item | Severity | Description |
|------|----------|-------------|
| Domain replacement | REQUIRED | Replace `example.com` with actual domain in Caddyfile |
| `.env.production` creation | REQUIRED | Create from `.env.production.example` with real secrets |
| SMTP configuration | OPTIONAL | Email notifications not yet configured |
| Stripe configuration | OPTIONAL | Online payments not yet configured |
| EAS account setup | REQUIRED | For mobile app builds |
| App store accounts | REQUIRED | For mobile app submission |

---

## Git Status

```
Modified files (7):
 M DATABASE_OPERATIONS.md
 M DEPLOYMENT_ARCHITECTURE.md
 M DEPLOYMENT_RUNBOOK.md
 M UPDATE_ROLLBACK_PROCEDURE.md
 M apps/web/Caddyfile
 M apps/web/Dockerfile
 M docker-compose.prod.yml

Current commit: cf27bdd (feat: prepare UniServe for production deployment)
This audit created changes but has NOT committed them.
```

---

## Summary

The production deployment stack is now **internally consistent and ready for deployment**. The two blocking issues (empty web volume, missing web build instructions) have been fixed. The architecture is:

- **Caddy** serves static Next.js files (bind mount) and proxies API requests
- **FastAPI** handles business logic with 2 Uvicorn workers
- **PostgreSQL** stores all data with persistent volume
- **No Redis** (not used at runtime, commented out)
- **Health checks** at Docker and application levels
- **Backups** via `pg_dump` with 30-day retention

**Next steps for the user:**
1. Provision a VPS (Ubuntu 22.04 LTS)
2. Purchase a domain and configure DNS
3. Follow `DEPLOYMENT_RUNBOOK.md` (20 steps)
4. Replace `example.com` with actual domain
5. Create `.env.production` with generated secrets
