# UniServe — Final Local Run Guide (Demo)

**Phase:** 62 (Demo Readiness, Rehearsal & Final Release Checklist)
**Date:** 2026-10-07
**Audience:** anyone running the UniServe demo stack locally (this rehearsal machine or a fresh one with Docker + Node + repo access).
**Ground rule:** every command below was executed and verified during Phase 61A/62 on this machine. Nothing is invented. Secrets are never reproduced here — credentials live in the committed seed scripts referenced in §6.

---

## 1. What the demo stack consists of

| Component | Technology | Local address | How it runs |
|---|---|---|---|
| Database | PostgreSQL 16 (`postgres:16-alpine`) | `localhost:5433` (host) → 5432 (container) | Docker container `uniserve_postgres`, volume `uniserve_postgres_data`, DB `uniserve_prod` |
| API | FastAPI (`apps/api`, image `uniserve-prod-api`) | `http://localhost:8000` | Docker container `uniserve_api`, uvicorn behind container healthcheck |
| Web console | Next.js 14 dev server (`apps/web`) | `http://localhost:3000` | `npx next dev` (foreground/background terminal) |
| Mobile app | Expo 57 / React Native (`apps/mobile`) | Metro (device/emulator) | `npx expo start` — optional for API-level rehearsal |
| Reverse proxy | Caddy | 80/443 | **Not required for the local demo** — exited by design; web is served by the Next dev server |

- Compose project: `docker-compose.prod.yml` (project name `uniserve-prod`, fixed so it never shares volumes with the dev compose).
- This machine additionally uses a **local port-override file outside the repo** (Phase 61A convention: temp override mapping `api 8000:8000` and `postgres 5433:5432`; compose `expose`s them internally by default). Recreate the same effect on a fresh machine with any equivalent `-f <override>` or edit nothing and reach services via caddy.
- The API container image currently serving = `uniserve-prod-api` built **2026-10-07T20:16:41Z** from repository HEAD `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (Phase 61A rebuild; enum includes `admin_announcement`). Rollback tag: `uniserve-prod-api:pre-phase61a` (2026-10-04 image).

## 2. Prerequisites

- Docker Desktop running (containers `uniserve_postgres` + `uniserve_api` healthy).
- Node.js 18+ with repo `node_modules` installed (npm workspaces; do **not** delete `apps/web/node_modules/next`).
- Python 3.11 venv at repo root (`.venv`) with `apps/api` installed editable (only needed for running the backend test suite, not for the demo runtime).
- `.env.production` in repo root (template: `.env.production.example`) — consumed by both `postgres` and `api` services via `env_file`. Key names verified present: `POSTGRES_USER/PASSWORD/DB`, `JWT_SECRET_KEY`, `APP_SECRET_KEY`, `APP_ENV`, `APP_DEBUG`, `CORS_ORIGINS`, `TZ`, etc. **Values are never committed; do not print them.**
- `apps/web/.env.local` containing exactly `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` (verified on this machine).

## 3. Startup sequence (verified order)

```powershell
# 1) Database + API (production compose, from repo root)
docker compose -f docker-compose.prod.yml up -d            # add your local override -f files if used
docker compose -f docker-compose.prod.yml ps               # both services must show (healthy)

# 2) Health checks
curl.exe http://localhost:8000/api/v1/health               # -> {"status":"healthy","service":"uniserve-api",...}
curl.exe http://localhost:8000/api/v1/health/ready         # -> {"status":"ready","database":"connected","schema":"present"}
docker exec uniserve_postgres pg_isready -U uniserve -d uniserve_prod   # -> accepting connections

# 3) Web console (separate terminal, from apps/web)
cd apps\web
npx next dev                                               # -> Ready, http://localhost:3000
curl.exe -s -o NUL -w "%{http_code}" http://localhost:3000/dashboard     # -> 200

# 4) Mobile app (optional for API-level rehearsal)
cd apps\mobile
npx expo start                                             # scan QR with Expo Go / open emulator
```

**Expected, non-blocking startup noise (do not "fix"):**
- Next dev prints `⚠ Specified "rewrites" will not automatically work with "output: export"` and `⨯ Middleware cannot be used with "output: export"` — pre-existing baseline warnings (the same repo config known since Phase 56+); the dev server still reaches `✓ Ready` and serves 200.
- Next dev prints `Found lockfile missing swc dependencies, patching...` followed by an npm `ENOWORKSPACES` error and `Failed to patch lockfile` — non-fatal, server works normally. The repo's `package-lock.json` stays byte-identical (this is why the patcher fails; leave it alone).
- First page compile takes ~40 s (`Compiling /dashboard ... Compiled in 43.5s`); subsequent requests are ~1 s.

## 4. What NOT to run (verified landmines)

| Command | Why not |
|---|---|
| `npx next build` (or `npm run build` in `apps/web`) | Known dual-React baseline failure (Phase 61 finding F-61-03: root React 19 vs web React 18) — **and** it clobbers `apps/web/.next`, breaking the running dev server. Static-web deploy path only; irrelevant to the demo. |
| `docker compose down -v` / `docker volume rm` | Destroys `uniserve_prod` demo data. Never needed. |
| `ruff check app` (without `--no-fix`) | `pyproject.toml` sets `fix = true` — it would auto-modify source. Use `ruff check --no-fix app` if linting. |
| Running the backend suite while a dev uvicorn on **:8001** holds old code | Host residue (F-61-11). The demo API is the **container on :8000**; stop the stale `:8001` uvicorn (pid 4772) before demos to avoid confusion. |
| Heavy suites (backend pytest + mobile jest + web vitest) **concurrently** | 8 GB host flake (F-61-14). Run gates sequentially. |

## 5. Shutting down / restarting

```powershell
# Stop web: Ctrl+C in the next dev terminal (or kill the node listener on :3000)
# Stop stack (data preserved):
docker compose -f docker-compose.prod.yml stop
# Full down WITHOUT volume removal is acceptable:
docker compose -f docker-compose.prod.yml down
# Rebuild + redeploy ONLY the API (the Phase 61A remediation recipe):
docker compose -f docker-compose.prod.yml -f <your-override> build api
docker compose -f docker-compose.prod.yml -f <your-override> up -d --no-deps api
```

`--no-deps` guarantees PostgreSQL is untouched. After any `next build` accident, restore the web server by killing the node process on :3000 and re-running `npx next dev`.

## 6. Demo accounts (local seeded data)

All accounts below exist in the local `uniserve_prod` database and cover the five demo roles. **Passwords are seeded test-fixture values documented in the committed scripts — see `scripts/seed_realistic_data.py` (role accounts) and `scripts/reset_test_passwords.py` (live.* probe accounts); admin password is defined in `seed_realistic_data.py` as well.** They are not production secrets; never reuse them anywhere real.

| Role | Emails |
|---|---|
| University admin | `admin@lgu.edu.pk` |
| Students | `ayesha.khan@student.lgu.edu.pk`, `bilal.hussain@student.lgu.edu.pk`, `fatima.raza@student.lgu.edu.pk` |
| Faculty | `dr.sana.malik@lgu.edu.pk`, `dr.imran.chaudhry@lgu.edu.pk` |
| Cafeteria staff | `ahmed.raza@lgu.edu.pk` |
| Cafeteria manager | `sana.malik@lgu.edu.pk` |

Login API shape (web/mobile both use it): `POST /api/v1/auth/login` with `{"university_email": "...", "password": "..."}` → response nests tokens at `tokens.access_token` (not top-level). Web session lives in the browser (survives dev-server restarts).

## 7. Data safety rules for the demo

- The database is **real local product data** accumulated across phases (18 users, 5 cafeterias, 52 orders, 39 payments, 4 refunds, 148 notifications, 806 audit events, schema `alembic_version 0013`). Do not reset it.
- Verification activity (logins, mark-read, new demo orders) adds normal auth/audit/session rows — expected and permitted.
- `admin_announcement` rows (14) must never be deleted to "clean up" — they are part of the notification demo.
- Known cosmetic residue (documented in `FINAL_KNOWN_LIMITATIONS.md`): E2E cafeteria `Phase 56 E2E Cafeteria` appears in admin lists; residue `pending_verification`/`suspended` accounts appear in the admin user list. Harmless; do not delete during the demo.

## 8. 60-second smoke check before presenting

```powershell
curl.exe http://localhost:8000/api/v1/health
curl.exe http://localhost:8000/api/v1/health/ready
curl.exe -s -o NUL -w "%{http_code}" http://localhost:3000/dashboard
```
Then log in as admin on `http://localhost:3000` → dashboard must show live stats + the Notifications widget with unread `admin_announcement` rows (this exact path was the Phase 61 blocker; it is fixed and re-verified in Phase 62). Full rehearsal evidence: `PHASE_62_DEMO_READINESS_AND_FINAL_RELEASE_CHECKLIST.md`; screenshot map: `DEMO_SCREENSHOT_CHECKLIST.md`.

## 9. Where things live

| Item | Path |
|---|---|
| Final release decision + rehearsal evidence | `PHASE_62_DEMO_READINESS_AND_FINAL_RELEASE_CHECKLIST.md` |
| Known limitations register | `FINAL_KNOWN_LIMITATIONS.md` |
| Demo screenshot map | `DEMO_SCREENSHOT_CHECKLIST.md` |
| Previous readiness audit (Phase 61) | `PHASE_61_POST_PHASE_60_STABILITY_AND_RELEASE_READINESS_AUDIT.md` |
| Deployed-image remediation (Phase 61A) | `PHASE_61A_DEPLOYED_API_RUNTIME_REMEDIATION.md` |
| Ops-hardening evidence (Phase 60) | `PHASE_60_OPERATIONS_HARDENING_AND_TEST_NET_COMPLETION.md` |
| Deployment runbook (production VPS path) | `DEPLOYMENT_RUNBOOK.md` (out of scope for this local demo guide) |
