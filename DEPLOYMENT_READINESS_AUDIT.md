# UniServe — Deployment Readiness Audit (Free-Tier Goal)

> **Date:** 2026-10-11
> **Scope:** Investigation and documentation only. No application code, deployment
> configuration, database contents, or Git history were modified. No service was
> deployed. All checks run were safe and read-only; every command executed is
> listed in §1. Secret values from `.env*` files were never read, printed, or
> reproduced — this document contains environment-variable **names only**.

---

## 1. Method — what was inspected and what was run

**Inspected (read-only):** repository structure, `docker-compose.yml`,
`docker-compose.prod.yml`, `infrastructure/caddy/Caddyfile`, `apps/api/Dockerfile`,
`apps/api/requirements.lock.txt`, `apps/api/app/core/config.py`,
`apps/api/app/core/database.py`, `apps/api/app/main.py`, API module routers and
schemas, Alembic migrations, `apps/web/next.config.js`, `apps/web/lib/api.ts`,
`apps/mobile/app.json`, `scripts/seed_realistic_data.py`, `scripts/backup_database.sh`,
`DEPLOYMENT_ARCHITECTURE.md`, `DEPLOYMENT_BLOCKERS.md`, `DEPLOYMENT_RUNBOOK.md`,
`RELEASE_BLOCKER_CHECKLIST.md`, `.gitignore`, and the tracked `.env.production.example` files.

**Executed (all safe, non-destructive):**

| Check | Result |
|---|---|
| `git status --porcelain` | 0 changes — clean tree |
| `git rev-list --left-right --count main...origin/main` (after `git fetch`) | `0 0` — in sync with origin |
| GitHub API metadata for `pakmultilinks-dot/UniServe` | `private: false` — **public repo**; default branch `main`; no GitHub Pages enabled |
| `docker compose -f docker-compose.prod.yml config --quiet` | exit 0 — compose file valid (run twice) |
| `GET http://localhost:8000/api/v1/health` (local stack) | HTTP 200 |
| `GET http://localhost:8000/api/v1/health/ready` (local stack) | `{"status":"ready","database":"connected","schema":"present"}` |
| Static food files in repo (`apps/api/app/static/food`) | 33 files |
| Food files baked in the previously built API image | 27 (image predates the last 6 files; a **fresh build from current HEAD bakes all 33**) |
| `inspect.signature(asyncpg.connect)` in the API venv | `ssl` default `None` — see §4, "managed Postgres" |
| Oracle Cloud Free Tier page + Render pricing/free docs (fetched 2026-10-11) | terms recorded in §5 |

No test suite was re-run this session (backend baseline 875 passed / 5 skipped is
recorded in `FINAL_PRE_DEPLOYMENT_REPORT.md` §8 from the release-gate session).
No POST/DB-writing requests were made against the local database — only GETs.

---

## 2. Confirmed architecture (with file paths)

| Component | Technology | Key files |
|---|---|---|
| Web app | Next.js 14, **static export** (`output: "export"`); no server runtime needed | `apps/web/next.config.js`, build output `apps/web/out/` |
| Web → API wiring | `NEXT_PUBLIC_API_URL` baked **at build time**; dev-only `/api` rewrite disabled in production | `apps/web/lib/api.ts`, `apps/web/.env.production.example` |
| Web auth | JWT in `localStorage` + lightweight `uniserve_session` flag cookie (`document.cookie`, samesite=lax) — cookie is **not** proof of auth | `apps/web/lib/api.ts` |
| Mobile app | Expo SDK 57; `EXPO_PUBLIC_API_BASE_URL` (localhost fallback); `app.json` contains only the app name — **no EAS owner/projectId yet** | `apps/mobile/app.json`, `apps/mobile/src/…/config.ts` |
| API | FastAPI 0.141 + SQLAlchemy 2.0 (async) + asyncpg 0.31 + Alembic 1.20 + uvicorn (2 workers); Python 3.11-slim-bookworm; installs `requirements.lock.txt` with `--no-deps` + `pip check` | `apps/api/Dockerfile`, `apps/api/requirements.lock.txt` |
| Static food images | Served by the API from `/app/app/static` at `/api/v1/static` (mount is conditional on the directory existing); 33 files committed; prod bind-mounts a named volume over `…/static/food` | `apps/api/app/main.py:192-196`, `docker-compose.prod.yml` (volume `menu_images_data`) |
| Database | PostgreSQL 16 (internal only in prod — `expose`, not `ports`); named volume `postgres_data`; one init script (extensions only, **no seed data**) | `docker-compose.prod.yml`, `infrastructure/database/init/001_extensions.sql` |
| Migrations | **Manual only** — no startup hook; lifespan starts only the in-process pickup-expiry worker. 15 revisions (`0000`…`0013`, head `0013`) | `apps/api/migrations/versions/`, `DEPLOYMENT_RUNBOOK.md` |
| Edge / TLS | Caddy reverse proxy with auto-HTTPS; API vhost + static web vhost with SPA `try_files` fallback | `infrastructure/caddy/Caddyfile` |
| Prod orchestration | Compose project `uniserve-prod`: caddy + api + postgres; API healthcheck via httpx `/api/v1/health` | `docker-compose.prod.yml` |
| Health endpoints | `GET /api/v1/health` (liveness, no DB) and `GET /api/v1/health/ready` (DB + `users` schema check) | `apps/api/app/api/health.py` |
| Auth/OTP | JWT + refresh; registration → `PENDING_VERIFICATION`; login rejects non-`ACTIVE`; only OTP verification → `ACTIVE`; SMTP provider **fails closed** when `SMTP_HOST`/`FROM_EMAIL` are empty | `apps/api/app/modules/auth/service.py`, `apps/api/app/core/email.py` |
| Payments | `PAYMENT_PROVIDER` defaults to `test` → online payment endpoints return HTTP 503 in production; cash-on-pickup unaffected | `apps/api/app/modules/payments/…` |
| Seed data | `scripts/seed_realistic_data.py` creates demo users/menu/orders and marks accounts `email_verified` / `active` via direct DB update; committed demo accounts in `DEMO_ACCOUNTS.md` | `scripts/seed_realistic_data.py`, `DEMO_ACCOUNTS.md` |
| CI | **None** — no `.github/workflows` exists; all builds are manual | — |
| Secrets hygiene | `.gitignore` covers `.env`, `.env.local`, `.env.*.local`, `.env.production`; only the two `.env.production.example` templates are tracked | `.gitignore`, `git ls-files` |

**Repository state:** git root `…/Code_PlayGround/UniServe`, branch `main`, HEAD
`3fd39c5` ("feat: complete UniServe product improvements and QA"), clean tree,
in sync with `origin` (`https://github.com/pakmultilinks-dot/UniServe.git`, **public**).

---

## 3. Exact deployment blockers

Ordered by what must be resolved first. "Operator input" means a decision or
credential only the operator can supply — no code change is implied.

1. **No deployment target exists (primary blocker).** No VM, cloud account, or
   hosting service has been provisioned. Nothing can be deployed until an
   operator creates one (see §5 for the recommended free option). — *Operator input.*
2. **Placeholder domains in the Caddyfile.** `infrastructure/caddy/Caddyfile`
   declares `api.example.com` and `app.example.com` vhosts (line 8, line 30).
   These must be replaced with the operator's real subdomains at deploy time.
3. **Placeholder CORS origin.** `CORS_ORIGINS` must list the exact real web
   origin(s) (e.g. `https://app.<domain>`). The local `.env.production` currently
   contains an `https://app.example.com` placeholder alongside localhost entries.
4. **Server-side web build with the real API URL.** `NEXT_PUBLIC_API_URL` is
   compiled into the static bundle; the existing local `apps/web/out/` was built
   with a placeholder/localhost URL and **must be rebuilt on (or for) the server**
   with `NEXT_PUBLIC_API_URL=https://api.<domain>/api/v1`.
5. **`.env.production` must be provisioned on the server** with freshly generated
   secrets (`APP_SECRET_KEY`, `JWT_SECRET_KEY`) and real `POSTGRES_*` values.
   It must never be committed and never copied from this development machine.
6. **SMTP is unconfigured → registration and password-reset are unavailable for
   new users.** The auth flow fails closed (`PENDING_VERIFICATION` cannot log in).
   The committed demo accounts are seeded as `active`, so **demo login works
   without SMTP**. Enabling self-service registration later needs a free SMTP
   provider (e.g. Brevo, 300 emails/day) — optional for a demo.
7. **Migrations and seeding are manual, and the seed script targets the dev
   stack.** There is no auto-migrate at startup (`alembic upgrade head` must be
   run per `DEPLOYMENT_RUNBOOK.md`). `scripts/seed_realistic_data.py` hardcodes
   `BASE_URL = http://localhost:8000/api/v1` and `PG_DB = uniserve_dev`; on the
   prod stack the API is not published to the host and the DB name comes from
   `.env.production`. A fresh database contains **no demo data** (init SQL is
   extensions-only), so seeding (or equivalent manual setup) is required for a
   browsable demo. Practical path: temporarily publish `127.0.0.1:8000` for the
   API and align the DB name during seeding via a **server-local** override file
   (not committed), then remove it.
8. **Mobile distribution.** `apps/mobile/app.json` has no EAS `owner`/`projectId`.
   A demo via **Expo Go** (phone scans a QR from a running Metro bundler with
   `EXPO_PUBLIC_API_BASE_URL` set to the deployed API) costs $0. Standalone
   Android builds need an Expo account (free tier ≈30 build credits/month);
   iOS builds require a paid Apple Developer account ($99/yr).
9. **No CI pipeline** (informational): every build is manual; there is no
   automated test/build gate on push.
10. **Orphan `phase28a_rehearsal_marker` table** exists only in the *local*
    database, not in migrations (informational: irrelevant for a fresh server;
    do not `alembic upgrade`/`downgrade` to address it).

Optional, non-blocking (carried from `RELEASE_BLOCKER_CHECKLIST.md`): payment
provider credentials (online payments stay 503-fail-closed; cash works), EAS
credentials, and a one-time review/rotation of any secrets that ever touched
this development machine.

---

## 4. Demo features: what works without paid services

| Feature | Free? | Notes |
|---|---|---|
| Login (demo accounts) | ✅ $0 | Seeded accounts are `active`; no SMTP needed |
| Menu browsing + food images | ✅ $0 | 33 images served by the API/Caddy from the `menu_images_data` volume |
| Ordering (cash-on-pickup) | ✅ $0 | `payment_method: "cash"` |
| Staff confirm → prepare → ready → collect flow | ✅ $0 | Full status machine (`pending/preparing/ready/completed/cancelled`) |
| Order lookup by number, ETA, cancellation, manager-cancel | ✅ $0 | |
| Admin / staff / manager dashboards (web) | ✅ $0 | Static export + API |
| Reports, notifications (in-app), favorites, no-show tracking | ✅ $0 | |
| Scheduled orders, pickup-expiry worker | ✅ $0 | Worker runs in-process inside the API container |
| Health + readiness endpoints | ✅ $0 | Useful for smoke tests and uptime pings |
| Self-service registration / password reset | ❌ needs SMTP | Fails closed without it; free SMTP (e.g. Brevo) unlocks it |
| Online payments | ❌ needs provider creds | Intentionally 503-fail-closed; cash demo unaffected |
| iOS / store builds | ❌ paid | Apple Developer account required for iOS |

**Managed-Postgres compatibility finding (verified, not assumed):** the API builds
its connection URL as `postgresql+asyncpg://…` with **no TLS parameter**
(`apps/api/app/core/config.py`), and `create_async_engine` passes no `ssl`
connect-args (`apps/api/app/core/database.py`). `asyncpg.connect`'s `ssl` default
is `None` (verified in the installed venv), i.e. plaintext. Managed free Postgres
services that **enforce TLS** (Neon, Supabase, Render Postgres external
connections) will therefore reject this client **without a code change**. Running
Postgres in the existing compose stack on a VM avoids this entirely. A future,
small code change (URL `?ssl=require` or connect-args) would be needed to use
TLS-enforcing managed databases — out of scope for this audit.

---

## 5. Proposed free architecture + limitations

### Recommended: one Always-Free VM running the existing compose stack, unchanged

**Oracle Cloud Always-Free VM** (terms fetched from oracle.com/cloud/free on
2026-10-11): Arm Compute — **1,500 OCPU-hours + 9,000 GB-hours per month**
(≈ one 4-OCPU / 24 GB Ampere A1 VM running continuously, or smaller shapes),
plus 2 AMD E2.Micro instances (1/8 OCPU, 1 GB). A credit/debit card is required
at signup; a US$300 trial credit expires after 30 days, after which **Always Free
services continue at $0** if no paid resources are created.

Why it fits UniServe with **zero code changes**:

- It runs the unmodified `docker-compose.prod.yml` (Caddy + API + PostgreSQL) with
  the **named volumes** `postgres_data` and `menu_images_data` persisting across
  restarts and reboots — the storage-persistence requirement that eliminates
  most serverless options.
- 24 GB RAM comfortably fits Postgres + a 2-worker uvicorn + Caddy, **and** the
  Next.js static build (no need to build elsewhere).
- A **free subdomain** (e.g. DuckDNS `api-<name>.duckdns.org` +
  `app-<name>.duckdns.org`, A records → VM IP) slots directly into the existing
  Caddyfile, and **Caddy obtains Let's Encrypt certificates automatically** —
  exactly the design in `infrastructure/caddy/Caddyfile`.
- The public GitHub repo can be cloned on the server directly (no CI needed).
- All locked binary Python packages (asyncpg, pydantic-core, cryptography,
  argon2-cffi-bindings, bcrypt, cffi, greenlet, markupsafe, uvloop, watchfiles,
  httptools, websockets) publish `manylinux/aarch64` wheels, and the official
  `python:3.11-slim`, `postgres:16-alpine`, and `caddy` images are multi-arch.
  The Dockerfile's `pip check` will fail loudly during build if any wheel were
  missing — a built-in verification step on first ARM build.

**Free-tier risks and guardrails (accounted for):**

| Risk | Mitigation |
|---|---|
| Oracle reclaims **idle** Always-Free ARM instances (low sustained CPU) | Keep-alive: a tiny cron `curl` to the health endpoint every ~10 min keeps CPU above the idle threshold and doubles as uptime monitoring |
| Accidental charges on Oracle | Provision **only** Always-Free-eligible shapes (A1 ≤ 4 OCPU / 24 GB total; stay within published free storage/egress limits); never create paid-only shapes/regions; set a budget alarm on the account; delete trial-only resources before day 30 if not converting to Pay-As-You-Go |
| ARM capacity varies by region | If A1 shapes are unavailable in one region at signup, try another Always-Free-eligible region |
| Free subdomain providers can be slow/unreliable | DuckDNS-style domains work with Let's Encrypt; a ~$10/yr registrar domain is a drop-in upgrade later (only Caddyfile + DNS change) |
| Database loss | `scripts/backup_database.sh` (pg_dump) on a cron; **never** run `docker compose down -v` or `docker volume rm` |
| Upload loss (admin-added food images) | Persisted by the `menu_images_data` named volume; included in backups if desired |

### Alternatives considered — compatibility verdicts

| Platform | Can host | Limitations (fetched 2026-10-11) | Verdict |
|---|---|---|---|
| **Cloudflare Pages / GitHub Pages / Vercel** (static) | The web export only | No server runtime, no disk, no Postgres — the API still needs a home; two origins require a `CORS_ORIGINS` update | Works as a *web-only* front door; doesn't remove the VM need; adds moving parts |
| **Render Free** | Web service + Postgres, in principle | Web: 0.1 CPU/512 MB, **spins down after 15 min idle** (~1 min cold start), 750 instance-hours/mo, ephemeral FS (**admin image uploads lost on redeploy/sleep**), **no SMTP ports (25/465/587) on free services**, 5 GB bandwidth then billed-or-suspended. Postgres Free: **expires 30 days after creation** (+14-day grace), 1 GB, no backups. Also blocked by the TLS/asyncpg finding in §4 | Degraded, short-lived demo only; data expiry after 30 days makes it unsuitable as a persistent demo |
| **Hugging Face Spaces** | A single container | No compose (UniServe is 3 services), free tier has no persistent disk | Not compatible without re-architecting |
| **Serverless containers (Cloud Run free tier, etc.)** | The API container | No persistent disk (image uploads lost); TLS-enforcing managed DB needed (blocked by §4 finding); background worker needs a long-running instance | Not compatible without changes |
| **Expo / EAS** (mobile) | Expo Go demo at $0 | Free EAS ≈30 build credits/month for standalone Android; iOS always paid | Expo Go path recommended for the demo |

**Bottom line:** the only realistic **$0, persistent, no-code-change** architecture
is a single Always-Free VM (Oracle recommended) running the compose stack that
already exists in this repository, fronted by free subdomains and Caddy auto-HTTPS.

---

## 6. Environment variables (names only — no values)

Provision these **on the server** in `.env.production` (never committed). Values
must be generated/entered by the operator; secrets must be fresh, not reused from
any development machine.

**Core:** `APP_NAME`, `APP_ENV`, `APP_DEBUG`, `APP_SECRET_KEY`, `APP_HOST`, `APP_PORT`
**Database:** `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
**JWT:** `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
**CORS / logging:** `CORS_ORIGINS`, `LOG_LEVEL`, `LOG_FORMAT`
**OTP:** `OTP_LENGTH`, `OTP_EXPIRE_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS`, `OTP_MAX_RESENDS`
**PIN lockout:** `PIN_LENGTH`, `PIN_MAX_FAILED_ATTEMPTS`, `PIN_LOCKOUT_MINUTES`
**Business rules:** `REFUND_DEADLINE_HOURS`, `PICKUP_WINDOW_MINUTES`, `DEFAULT_PREPARATION_TIME_MINUTES`, `DEFAULT_CAPACITY`, `NOSHOW_STUDENT_THRESHOLD`, `NOSHOW_STUDENT_WINDOW_DAYS`, `NOSHOW_STUDENT_SUSPENSION_DAYS`, `NOSHOW_FACULTY_THRESHOLD`, `NOSHOW_FACULTY_WINDOW_DAYS`, `NOSHOW_FACULTY_SUSPENSION_DAYS`, `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`, `PASSWORD_RESET_MAX_REQUESTS`
**SMTP (optional — absent ⇒ registration/reset disabled, fail-closed):** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `FROM_EMAIL`, `SMTP_TLS_MODE`
**Payments (optional — absent ⇒ online payments 503-fail-closed, cash unaffected):** `PAYMENT_PROVIDER`, `PAYMENT_ENVIRONMENT`, `PAYMENT_MERCHANT_ID`, `PAYMENT_API_KEY`, `PAYMENT_API_SECRET`, `PAYMENT_WEBHOOK_SECRET`
**Web build-time:** `NEXT_PUBLIC_API_URL` (set only during `next build`, e.g. `https://api.<domain>/api/v1`)
**Mobile build-time:** `EXPO_PUBLIC_API_BASE_URL`

---

## 7. Ordered deployment steps (free tier)

Each step maps to `DEPLOYMENT_RUNBOOK.md`; placeholders like `<domain>` are
operator inputs. Nothing here commits anything to Git.

1. **Provision the VM:** create an Oracle Cloud Always-Free account (card
   required for verification) and launch an **Ampere A1** VM (Ubuntu 22.04/24.04
   ARM64) within Always-Free limits; open only 22/80/443 (host firewall e.g. UFW).
2. **DNS:** register two free subdomains (e.g. `api-<name>.duckdns.org`,
   `app-<name>.duckdns.org`) with A records pointing at the VM's public IP.
3. **Install Docker** on the VM (`curl -fsSL https://get.docker.com | sh`;
   verify `docker compose version`).
4. **Clone the public repo** on the server: `git clone https://github.com/pakmultilinks-dot/UniServe.git /opt/uniserve && cd /opt/uniserve && git checkout main`.
5. **Set the real domains** in `infrastructure/caddy/Caddyfile` (replace both
   `example.com` vhosts; keep the `try_files {path} {path}.html {path}/index.html /index.html` line **byte-exact** — it is the SPA deep-link fix).
6. **Provision `.env.production` on the server** from `.env.production.example`:
   generate fresh `APP_SECRET_KEY`/`JWT_SECRET_KEY`, set real `POSTGRES_*`,
   `APP_ENV=production`, and `CORS_ORIGINS` containing the exact web origin
   (`https://app-<name>…`). Leave `SMTP_*`/`PAYMENT_*` absent unless available.
   `chmod 600` the file.
7. **Build the web bundle with the real API URL** (on the server, or locally and
   upload `out/`): from the repo root `npm ci --ignore-scripts`, then
   `npm run build:shared`, then in `apps/web`:
   `NEXT_PUBLIC_API_URL=https://api-<name>…/api/v1 npm run build` → produces `out/`.
8. **Start the database:** `docker compose -f docker-compose.prod.yml up -d postgres` (wait until healthy).
9. **Run migrations:** `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head` (head = `0013`).
10. **Seed demo data** (fresh DBs contain none): run `scripts/seed_realistic_data.py`
    with the prod stack reachable — temporarily publish the API on
    `127.0.0.1:8000` and align the DB name via a **server-local, uncommitted**
    compose override, execute the script, then remove the override. Verify demo
    logins against `DEMO_ACCOUNTS.md`.
11. **Start the full stack:** `docker compose -f docker-compose.prod.yml up -d --build`.
    Confirm the API container now shows the `menu_images_data` mount (containers
    created before the volume existed do not get it until recreated) and that all
    33 food-image URLs return 200.
12. **Smoke-test** (§8) end-to-end over HTTPS, including an automatic TLS
    certificate for both vhosts (Caddy obtains it on first request).
13. **Optional:** configure free SMTP (e.g. Brevo) to enable registration demos;
    point the mobile app at the deployed API via `EXPO_PUBLIC_API_BASE_URL` for
    an Expo Go demo.
14. **Set up keep-alive + backups:** cron `curl` of `/api/v1/health` every ~10
    minutes (prevents idle reclamation + monitors uptime) and a scheduled
    `scripts/backup_database.sh` pg_dump.

---

## 8. Smoke tests (run against the deployed URLs)

`API=https://api-<domain>/api/v1` · `WEB=https://app-<domain>`
Demo credentials are the committed fixtures in `DEMO_ACCOUNTS.md`
(admin, manager, staff, faculty, and student test accounts — safe for presentation).

1. **Health:** `curl -fsS $API/health` → 200. `curl -fsS $API/health/ready` →
   `"database":"connected"`, `"schema":"present"`.
2. **Login:** `POST $API/auth/login` with a demo account → response contains
   `access_token` and `refresh_token`. (Registration without SMTP is expected to
   stop at `PENDING_VERIFICATION` — that is correct fail-closed behavior.)
3. **Menus & images:** `GET $API/cafeterias` → ≥1 cafeteria;
   `GET $API/menu-search?q=<term>` → items; `GET $API/static/food/<file>` → 200
   for all 33 committed images.
4. **Ordering (cash):** as a student, `POST $API/cafeterias/<id>/cart/items`
   (`{"menu_item_id": <id>, "quantity": 1}`), then
   `POST $API/cafeterias/<id>/cart/checkout`
   (`{"payment_method": "cash", "order_type": "immediate"}`) → order created;
   `GET $API/orders/<id>` and `GET $API/orders/by-number/<n>` succeed.
5. **Staff flow + order status:** as staff/manager:
   `POST $API/orders/<id>/confirm` → `POST $API/orders/<id>/prepare` →
   `PUT $API/orders/<id>/ready` → student `POST $API/orders/collect` →
   status `completed`. Statuses observed along the way:
   `pending → preparing → ready → completed`.
6. **Dashboards:** `WEB/login`, `WEB/dashboard` (student), `WEB/dashboard/staff`,
   `WEB/dashboard/admin` all load and show live data from the API; admin reports
   (`GET $API/reports/…`) render non-empty aggregates.
7. **CORS:** the browser pages under `WEB` call the API without CORS errors
   (origin listed in `CORS_ORIGINS`).
8. **Negative test (expected failure):** an online-payment initiation without
   provider credentials returns HTTP 503 (fail-closed), while cash ordering in
   step 4 succeeds.
9. **Persistence:** `docker compose -f docker-compose.prod.yml restart` → all of
   the above still pass (data survived; volumes intact).

---

## 9. Rollback and data-protection precautions

- **Before any migration on a live server:** run `scripts/backup_database.sh`
  (pg_dump) and keep the dump off-box. Restore path: create a fresh database and
  restore the dump; schema rollbacks use `alembic downgrade <revision>` only to
  revisions that actually exist in `apps/api/migrations/versions/`.
- **Never destroy volumes:** do not run `docker compose down -v`, and never
  `docker volume rm` on `postgres_data` or `menu_images_data` — they hold all
  user data and uploaded images. `docker compose down` (without `-v`) is safe.
- **Code rollback:** `git revert <commit>` (or `git checkout <last-good-sha>`)
  then rebuild images — the repo history is clean and linear at `3fd39c5`; no
  history rewriting, ever.
- **Config rollback:** keep a copy of the last-known-good server-side
  `.env.production` and Caddyfile (outside Git, permission-restricted). When
  editing the Caddyfile, preserve the SPA `try_files` line byte-exactly.
- **Secrets:** `.env.production` lives only on the server (`chmod 600`), is
  gitignored, and its values must never be pasted into tickets, logs, chats, or
  reports. Rotate `APP_SECRET_KEY`/`JWT_SECRET_KEY` if exposure is ever suspected
  (rotation logs everyone out — acceptable for a demo).
- **Network:** keep PostgreSQL internal (`expose` only — already the case in
  `docker-compose.prod.yml`); expose only 80/443 (and 22 from your IP).
- **Free-tier hygiene:** keep-alive cron (idle reclamation), scheduled backups,
  and a cloud budget alarm prevent silent data loss or surprise charges.

---

## 10. Summary

**What is ready:** a clean, public GitHub repository at `3fd39c5` (main, in sync);
a valid production compose stack (Caddy + FastAPI + PostgreSQL) that passed
`compose config` and ran healthy locally this session (`/health` 200,
`/health/ready` → connected + schema present); a static-export web app needing no
server runtime; 33 committed food images that bake into a fresh API build;
manual-but-documented migrations (head `0013`) and a seed script with committed
demo accounts; cash-on-pickup ordering and all dashboards working without any
paid service; strict secrets hygiene (env files gitignored, only examples tracked);
and a $0 architecture that requires **zero code changes** (Always-Free VM + the
existing compose file + free subdomains + Caddy auto-HTTPS).

**What blocks deployment:** (1) no cloud account/VM exists yet; (2) placeholder
`example.com` values in the Caddyfile, `CORS_ORIGINS`, and the web API URL must
be replaced with real domains and the web bundle rebuilt server-side; (3)
server-side `.env.production` with fresh secrets must be provisioned; (4)
migrations + seeding must be run manually (fresh DBs have no demo data; the seed
script's defaults target the dev stack); (5) SMTP is absent — new-user
registration/reset stays disabled until a free SMTP provider is added (demo logins
are unaffected).

**Single next action:** provision the Oracle Cloud Always-Free account and launch
the ARM VM (step 1 of §7) and claim the two free subdomains (step 2). Everything
else is mechanical execution of the runbook above once the machine and DNS names
exist.
