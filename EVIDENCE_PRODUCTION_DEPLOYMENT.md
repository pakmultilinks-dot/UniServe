# Evidence — Production Deployment Execution (Phase 34)

**Date:** 2026-10-02
**Repository:** `C:\Users\Lenovo\Documents\Code_PlayGround\UniServe` (local)
**Starting commit:** `70ae399` (`fix: validate production release candidate`)
**Outcome:** **No real production deployment occurred.** The deployment target (VPS, domains, DNS, production database location, credentials) is not available in this environment, so Phase 34 executed the repository-preparation/documentation path only. Nothing was simulated and presented as production. No external service was contacted, no account created, no public exposure.

---

## 1. Target determination (facts)

| Check | Result | Source |
|---|---|---|
| Provisioned VPS | None. `VPS_PROVISIONING_REPORT.md` states `BLOCKED — VPS NOT READY` (no cloud provider account, no server IP) | repo document (Phase 18) + `ls` of repo root this phase |
| Docker remote context | None — only `default` (npipe docker_engine) and `desktop-linux` (Docker Desktop) | `docker context ls` |
| Server SSH credentials | Not present in environment | environment inspection |
| Production domain/DNS | Not configured — repo artifacts still carry placeholders (`api.example.com`, `app.example.com`, `api.uniserve.app`) | `grep` of Caddyfile + `.env.production` + `apps/mobile/src/config.ts` |
| Git remote push performed | No — working on local `main` | `git status` |
| Accounts purchased/created | None | environment constraints honored |
| App-store submission | None | — |

**Determination:** blocked-path (deployment not executed). Commit type per plan: `docs:` (preparation/documentation only).

## 2. Deployment environment shape (verified, non-secret)

Local `.env.production` (exists, gitignored, **never committed**): `APP_ENV=production`, `APP_DEBUG=false`, `APP_NAME=UniServe`, `APP_HOST=0.0.0.0`, `APP_PORT=8000`, `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, `POSTGRES_USER=uniserve`, `POSTGRES_DB=uniserve_prod`, `JWT_ALGORITHM=HS256`, `LOG_LEVEL=INFO`, `LOG_FORMAT=json`, `CORS_ORIGINS=["https://app.example.com"]` (**placeholder**), `APP_SECRET_KEY`/`JWT_SECRET_KEY`/`POSTGRES_PASSWORD` = strong `token_urlsafe` values (values not displayed; lengths 64/64/32-byte class). All OTP/PIN/NOSHOW/LOGIN tuning vars present. `.env.production.example` tracked in repo as the template.

Git safety verified: `git check-ignore .env.production` → `.gitignore:48`; `apps/web/.env.production.local` also ignored; `git ls-files` shows only the five `.example` templates (`.env.example`, `.env.production.example`, `apps/api/.env.example`, `apps/web/.env.example`, `apps/web/.env.production.example`).

`docker-compose.prod.yml`: services `postgres` (postgres:16-alpine, TZ Asia/Karachi, init mount, pg_isready healthcheck), `api` (expose-only 8000, env_file `.env.production`, httpx healthcheck), `caddy` (80/443, mounts Caddyfile + `apps/web/out`, depends_on api healthy); Redis block commented with the verified "not required at runtime" note.

## 3. Repository deployment readiness (verified this phase)

| Item | Fact |
|---|---|
| Backend tests | `pytest` — **622 passed**, exit 0 |
| Shared types build | `npm run build:shared` — exit 0 |
| Web type-check | `npm run type-check:web` — exit 0 |
| Mobile type-check | `npm run type-check:mobile` — exit 0 |
| Web build | `npm run build:web` — exit 0; `apps/web/out` = **22 HTML + 21 RSC .txt** files |
| Deep-link HTML artifacts | All 11 routes present as per-route HTML (`login`, `register`, `dashboard`, `dashboard/orders`, `dashboard/menu`, `dashboard/inventory`, `dashboard/admin/overview`, `dashboard/admin/users`, `dashboard/admin/refunds`, `dashboard/admin/reports`, `dashboard/profile`) — matching the committed Caddyfile `try_files {path} {path}.html …` fix |
| Compose config | `docker compose -f docker-compose.prod.yml config --quiet` — exit 0; services: postgres, api, caddy |
| Prod image build | `build api` — exit 0 (`uniserve-prod-api`, requirements.lock.txt path, Phase 33 RC image lineage) |
| Image env safety | `docker run --rm uniserve-prod-api:latest ls /app/.env` → No such file (no `.env` baked into image) |
| Migrations | Alembic head `0009`; deploy path = fresh-server `compose up postgres` → `alembic upgrade head` (validated on fresh DB in Phase 33); `alembic check` added to runbook Step 8 |
| Redis | Not required at runtime — `grep -E '^(import redis|from redis|REDIS_)'` across `apps/api/app` → **no matches**; compose has no redis service; runbook Appendix documents this |
| Payment safety | Fail-closed intact: `POST /api/v1/payments/initiate` without provider → HTTP 503 (live-verified on the Phase 33 RC image); code path unchanged since |
| Caddy deep-link guard | `try_files {path} {path}.html {path}/index.html /index.html` committed in `70ae399` and marked "do not regress" in the runbook |
| Docs gate | `/api/docs|redoc|openapi.json` → 404 in production runtime (APP_DEBUG=false) — live-verified Phase 33, unchanged |

## 4. Database, backup, rollback readiness

- **Production database:** does not exist anywhere (no server). First deployment will be a **fresh** database created by Compose; `infrastructure/database/init/` mount + healthcheck verified in compose config.
- **Backup:** `scripts/backup_database.sh` verified working in Phase 33 (dumps `uniserve_postgres` → `.pgdump`, verifies with `pg_restore --list`, 239 TOC entries on the rehearsal database); targets the production container name `uniserve_postgres` (documented in runbook Step 17 notes). A cron entry template is in Step 17.
- **Restore:** `scripts/restore_database.sh` — `CONFIRM=yes` gate, env-overridable container/user/db, verifies the dump **before** touching the database, `--clean --if-exists --no-owner --no-acl`. Documented in runbook "Restore (Database)", including the prerequisite that the target DB has its `public` schema (pg_dump does not emit `CREATE SCHEMA public`).
- **Rollback:** documented in runbook "Update & Rollback" — API image (rebuild from previous commit), web artifact (rebuild `out/` from previous commit), Caddy (restore previous Caddyfile, preserve try_files), migrations (**no blind downgrade** — restore from backup or roll forward).
- **Rollback path for migrations on a first deploy:** no backup exists yet → first-deploy note added (take a backup immediately after seeding).

## 5. What was NOT done (explicit)

1. No real production deployment (no target existed).
2. No simulation presented as production (rehearsal stack untouched; no new sim created).
3. No external service contacted; no accounts; no purchases.
4. No public exposure of the application.
5. No payment provider configured — cash-only fail-closed default preserved.
6. No app-store/EAS submission.
7. No secret values displayed anywhere (shapes/lengths only).

## 6. Blockers & deliverables

- **Blockers:** `DEPLOYMENT_BLOCKERS.md` — B1 server, B2 SSH, B3 domains/DNS, B4 Caddyfile real domains, B5 server-side web build, B6 mobile URL + EAS, B7 server-side `.env.production`, B8 real CORS_ORIGINS, B9 git hosting, B10 payment provider (optional). Each with missing prerequisite / why / operator action / expected value / verification command.
- **Runbook:** `DEPLOYMENT_RUNBOOK.md` updated this phase — status header + blockers reference; Caddy `try_files` do-not-regress note (Step 5); `alembic check` (Step 8); readiness status-field monitoring note (Step 10); payment fail-closed note (Step 14); backup notes + full Restore section (Step 17 area); new **Update & Rollback** and **Troubleshooting** sections; deep-link + role smoke additions (Step 19).
- **Commit (planned):** `docs: finalize UniServe production deployment runbook` (blocked path — preparation/documentation only).
