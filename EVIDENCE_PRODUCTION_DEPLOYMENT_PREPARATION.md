# Evidence — Phase 30: Production Deployment Preparation

> **Scope:** Prepare the existing UniServe system for actual production
> deployment. **No product behavior was changed.** No application audit was
> performed. UniServe is **NOT deployed** — this phase prepared configuration,
> scripts, documentation, and verified buildability only.
>
> **Source of truth:** HEAD `815df84` (Phase 29 final product & release audit)
> plus the Phase 30 preparation changes committed by this phase.
> **Verified on:** 2026-10-01, local Windows workstation (Docker Desktop
> 29.8.0 engine, Python 3.11 venv, Node 18+).

---

## 1. VERIFIED

### 1.1 Test & Build Validation

| Check | Result |
|-------|--------|
| Backend suite (`pytest apps/api/tests`) | **613 passed** (609 baseline + 4 new config-guard tests) |
| Production config-guard tests | **12/12 passed** (`test_config_production_guards.py`) |
| Web type-check (`apps/web`) | Clean (tsc --noEmit, no errors) |
| Web production build (`next build`, static export) | Green — Next.js 14.2.35, 24/24 static pages; `apps/web/out` regenerated **byte-identical** to the existing local artifact. Note: `out/` is **gitignored, not committed** — production always rebuilds it on the server (Phase 31 verified this tracking state) |
| Mobile type-check (`apps/mobile`) | Clean (tsc --noEmit, no errors) |
| `alembic current` (dev volume, isolated :5433 container) | `0009 (head)` |
| `alembic check` (dev volume) | `No new upgrade operations detected` — zero schema drift |
| `docker compose config` (dev `docker-compose.yml`) | Valid |
| `docker compose -f docker-compose.prod.yml config` | Valid — 3 services (`postgres`, `api`, `caddy`); **published host ports: 80 and 443 only** (Caddy); API and PostgreSQL are `expose`-only |
| Restart policies (all prod containers) | `unless-stopped` |
| Production image build (`docker compose -f docker-compose.prod.yml build api`) | **SUCCESS** — `uniserve-prod-api:latest` (dependency layer ~71 s, full image exported) |

### 1.2 Production Image Smoke Tests (inside the built image)

| Scenario | Result |
|----------|--------|
| `APP_ENV=production` + dev default `POSTGRES_PASSWORD` | **Fail-closed at import** — `ValidationError: POSTGRES_PASSWORD must be set to a strong value when APP_ENV=production` |
| `APP_ENV=production` + strong secrets/password | `IMPORT-OK env= production` |
| App package present and importable | `pkg-ok /app/app/__init__.py` |
| Alembic migrations in image | `0000_initial.py` … head `0009` present under `/app/migrations/versions` |
| `.env` inside image | **Absent** (build-context `.dockerignore` working — no credentials baked into images) |

### 1.3 Production Configuration Guards (fail-closed, locked by tests)

| Guard | Status |
|-------|--------|
| Default `APP_SECRET_KEY` rejected in production | Active (pre-existing) |
| Default `JWT_SECRET_KEY` rejected in production | Active (pre-existing) |
| `APP_DEBUG=true` rejected in production (exposes /api/docs surface) | Active (pre-existing) |
| **Dev/empty `POSTGRES_PASSWORD` rejected in production** | **Active (NEW — Phase 30)** |
| Test payment provider rejected in production (HTTP 503 on initiation) | Active, unchanged (`apps/api/app/modules/payments/router.py:94-98`) |
| Unknown payment provider names | Fail closed HTTP 503 (unchanged) |

### 1.4 Secret Hygiene

- `git ls-files`: **no** `.env`, `.env.production`, `.pem`, or `.key` files
  tracked — only `*.example` templates.
- `.gitignore` covers `.env`, `.env.*.local`, `.env.production`.
- `apps/api/.dockerignore` excludes `.env*` from the Docker build context.
- `apps/api/alembic.ini` **no longer embeds** a database URL/credential —
  `migrations/env.py` supplies `settings.DATABASE_URL` from `POSTGRES_*`
  environment variables at runtime.
- `.env.production.example` contains **no real credentials** (blank required
  fields with generation commands).

### 1.5 Redis — Inspected, Not Required at Runtime

- Grep of the entire `apps/api/app` tree: **zero Redis client imports**.
- The API starts and serves without Redis (verified in image smoke tests and
  by the running local production-rehearsal stack, which has no Redis).
- `docker-compose.prod.yml` ships the Redis service **commented out** with a
  verified explanation; dev compose has Redis running but unused.
- Conclusion documented in: `DEPLOYMENT_ARCHITECTURE.md`,
  `PRODUCTION_RUNBOOK.md`, `DEPLOYMENT_RUNBOOK.md` (appendix),
  `docker-compose.prod.yml` (comment).

### 1.6 Background Workers Layout

- The pickup-expiry worker runs **in-process** from the FastAPI lifespan hook
  (`apps/api/app/main.py`), ticking every 60 s (`_PICKUP_CHECK_INTERVAL`).
- Production uvicorn runs `--workers 2` → each worker process ticks its own
  copy. Safe by design: the expiry query uses `SELECT … FOR UPDATE SKIP
  LOCKED`, so concurrent ticks never double-process an order.
- **No separate worker container is deployed** — documented as forbidden
  (would duplicate the in-process worker with no benefit).

### 1.7 Backup / Restore Tooling

| Script | Capability (verified by review; scripts target Linux servers) |
|--------|----------------------------------------------------------------|
| `scripts/backup_database.sh` | Timestamped `pg_dump --format=custom` inside the container (no host port needed), **new:** `pg_restore --list` verification before the dump leaves the container, copy to `./backups/`, 30-day retention, non-zero exit on failure |
| `scripts/restore_database.sh` | **New:** `CONFIRM=yes` gate (refuses destructive runs otherwise), dump verification (`pg_restore --list`) inside the container **before** touching the database, `--clean --if-exists --no-owner --no-acl` restore, container-running check |

Backups are **not automatic** — a cron entry must be installed by the
operator (documented in `DATABASE_OPERATIONS.md`, `DEPLOYMENT_RUNBOOK.md`
Step 17, `PRODUCTION_RUNBOOK.md` §5).

### 1.8 Deployment Documentation (repo-truth, updated this phase)

| Document | Change |
|----------|--------|
| `DEPLOYMENT_RUNBOOK.md` | 20-step first-deployment sequence retained; `npm ci` → `npm install` (repo has no lockfile — `npm ci` fails); Step 6 now copies `apps/web/.env.production.example`; EAS/mobile and Redis appendices present |
| `DATABASE_OPERATIONS.md` | Rewritten: env-driven Alembic URL explanation, dev-vs-prod connection table, container-name collision warning (dev+prod share `uniserve_postgres`), scripted verified backup/restore commands, **forward-fix-first migration rollback policy**, correct production volume name (`uniserve-prod_postgres_data`) |
| `UPDATE_ROLLBACK_PROCEDURE.md` | `npm ci` → `npm install`; forward-fix preferred over downgrade; restore uses `CONFIRM=yes` script; safety rule #8 added (prefer forward-fix) |
| `PRODUCTION_RUNBOOK.md` | Backup verification + `CONFIRM=yes` restore synced; worker-layout and Redis notes added |
| `DEPLOYMENT_ARCHITECTURE.md` | Last-verified stamp, correct web/mobile build-time URL sources, verified Redis non-dependency note |

---

## 2. PREPARED (Phase 30 file changes)

1. `apps/api/app/core/config.py` — new model validator
   `reject_dev_database_password_in_production` (dev-default or empty
   `POSTGRES_PASSWORD` fails startup when `APP_ENV=production`).
2. `apps/api/tests/test_config_production_guards.py` — base production
   fixture supplies a strong DB password; 4 new regression tests for the
   DB-password guard (rejection of dev default, rejection of empty, strong
   value allowed, development default unchanged).
3. `apps/api/Dockerfile` — non-editable dependency install
   (`pip install .` — production-appropriate; previously `-e "."`),
   `PYTHONUNBUFFERED=1`/`PYTHONDONTWRITEBYTECODE=1`, README included in the
   dependency layer, comment documenting multi-worker pickup-expiry safety.
4. `apps/api/alembic.ini` — hardcoded dev database URL/credential removed;
   blank placeholder with explanation (env.py supplies the URL).
5. `.env.production.example` — completed with `DEFAULT_CAPACITY`,
   no-show window/suspension variables, and a note on code-defined
   `UNIVERSITY_EMAIL_PATTERNS`.
6. `docker-compose.prod.yml` — Redis comment upgraded with the verified
   no-imports finding.
7. `docker-compose.yml` (dev) — obsolete `version:` attribute removed.
8. `scripts/backup_database.sh` — dump verification step added.
9. `scripts/restore_database.sh` — `CONFIRM=yes` gate + pre-restore dump
   verification added.
10. `DATABASE_OPERATIONS.md` — rewritten (see §1.8).
11. `DEPLOYMENT_RUNBOOK.md` — `npm install`, Step 6 template copy.
12. `UPDATE_ROLLBACK_PROCEDURE.md` — rollback policy hardening.
13. `PRODUCTION_RUNBOOK.md` — verification/CONFIRM sync + worker/Redis notes.
14. `DEPLOYMENT_ARCHITECTURE.md` — verification stamp + accuracy fixes.
15. `EVIDENCE_PRODUCTION_DEPLOYMENT_PREPARATION.md` — this document.

**Unchanged on purpose:** all product code paths (auth, authorization,
cafeteria rules, ordering, payments/refunds, UI), JazzCash handling (none —
externally blocked), the payments 503 production guard, EAS/app.json
(already minimal-viable: production channel, bundle IDs, autoIncrement),
Caddyfile domains (placeholders retained for the operator to replace),
`apps/mobile/src/config.ts` (placeholder production URL retained — operator
edits before an EAS build; documented, not guessed).

---

## 3. EXTERNAL REQUIREMENTS (must be provided by the operator)

| Requirement | Details |
|-------------|---------|
| VPS | Ubuntu 22.04+/Debian 12+, Docker Engine + Compose. Provisioning scripts exist (`scripts/vps/`) but were **deliberately not executed** — no server was purchased or configured. |
| Domain(s) + DNS | `app.example.com` / `api.example.com` are **placeholders**. Create DNS A records and replace the placeholders in `infrastructure/caddy/Caddyfile`. Caddy then obtains Let's Encrypt certificates automatically on first start (ports 80/443 reachable). |
| Production secrets | Generate on the server: `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` (commands documented in `.env.production.example`). Store only in git-ignored `.env.production`. |
| Web production build | Build on the server with `NEXT_PUBLIC_API_URL=https://<real-api-domain>/api/v1` (see runbook Step 6). |
| Mobile production URL | Edit `apps/mobile/src/config.ts` (`ENV.production.API_BASE_URL`) to the real API domain; Expo account required for EAS builds; store submission is manual (no CI builds APK/IPA). |
| Backups | Install the cron entry (§1.7). Copy dumps off the server. |
| Monitoring | Uptime checks + log alerting (out of scope of this phase). |
| Payment provider | **JazzCash remains externally blocked** — no authoritative contract. Online payments stay fail-closed (HTTP 503 on initiation in production) until a real provider is provisioned and configured via backend-only env vars. |
| Email/SMTP | Not implemented (placeholders in env templates). Notifications are in-app only. |

---

## 4. BLOCKERS (for an actual production deployment — none block this phase)

1. **No production server/domains/secrets exist yet** — all deployment steps
   in the runbook require operator-provisioned infrastructure.
2. **No real payment provider contract** — online payments cannot be enabled
   by configuration alone; the system correctly refuses (503) rather than
   guessing an undocumented API.
3. **No SMTP service** — email-based flows (if/when required) unconfigured.
4. **Python dependencies are unpinned** (`>=` ranges in
   `apps/api/pyproject.toml`; no lockfile). Builds are therefore not
   bit-reproducible — the image built this session resolved newer versions
   (e.g. FastAPI 0.142.2) than the local dev venv. Changing pinning was out
   of scope (would alter runtime dependencies); documented for a future
   release-engineering phase. Same situation for Node: no
   `package-lock.json` (`npm install` required, `npm ci` fails).

---

## 5. NOT VERIFIED (honesty list)

- **UniServe is NOT deployed.** No VPS was provisioned, no DNS configured,
  no external service purchased or touched. Only the **local
  production-rehearsal stack** (Caddy/API/PostgreSQL containers on this
  workstation) exists, and it was left running as found.
- **HTTPS with real certificates** was not exercised — Caddy's automatic
  Let's Encrypt flow requires real domains/DNS (external requirement §3).
- **E2E suite against a production-guarded deployment** was not re-run this
  phase (Phase 29 established: unguarded dev stack 31/31; guarded deploy
  fails closed by design at the payments step).
- **Load/performance characteristics** were not measured.
- **Restore execution against a live production database** was not performed
  this phase (script logic reviewed and gate/verification added; the
  restore procedure itself was rehearsed in Phase 28A — see
  `PRODUCTION_RUNBOOK.md` §6).
- **Non-x86_64 image builds** (e.g. ARM) were not tested.
- **Cron backup installation** was not performed on any server.
- **APK/IPA artifacts** were not produced (requires an Expo account —
  external requirement).

---

## 6. Validation Command Log (this phase)

```
pytest apps/api/tests                     → 613 passed (233.87s)
test_config_production_guards.py          → 12 passed
apps/web:  npm run type-check             → clean
apps/web:  npm run build                  → 24/24 pages, static export OK
apps/mobile: npm run type-check           → clean
alembic current  (dev volume :5433)       → 0009 (head)
alembic check    (dev volume :5433)       → No new upgrade operations detected
docker compose config                     → OK (dev + prod)
docker compose -f docker-compose.prod.yml build api → SUCCESS (uniserve-prod-api:latest)
docker run image + dev DB password        → fail-closed ValidationError (expected)
docker run image + strong prod secrets    → IMPORT-OK env=production
image content: app pkg OK, migrations 0000-0009 present, no .env in image
```

Temporary validation container (`uniserve_phase30_pg`, dev volume on :5433)
was removed after validation. No other temporary files were created.
