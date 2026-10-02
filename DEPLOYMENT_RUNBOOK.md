# UniServe — Deployment Runbook

> Step-by-step guide for deploying UniServe to a production server.
> **Estimated time:** 30–60 minutes for first deployment.
> **Status (Phase 34):** the repository is deployment-validated at release
> candidate `70ae399`; no real deployment target exists yet — see
> `DEPLOYMENT_BLOCKERS.md` for the exact operator inputs required before
> executing this runbook, and `EVIDENCE_PRODUCTION_DEPLOYMENT.md` for what
> was verified.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| VPS | Ubuntu 22.04+ / Debian 12+, 2+ CPU, 4GB+ RAM, 40GB+ SSD |
| Domain | Two subdomains: `api.example.com`, `app.example.com` |
| DNS | A records pointing both subdomains to your server IP |
| SSH | Root or sudo access to the server |
| Blockers | See `DEPLOYMENT_BLOCKERS.md` — every `example.com`/placeholder value in this runbook must be replaced with real operator-provided values |

## Step 1: Prepare Server

```bash
# SSH into your server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose (should be included with Docker)
docker compose version

# Create deployment directory
mkdir -p /opt/uniserve
cd /opt/uniserve
```

## Step 2: Clone Repository

```bash
git clone https://github.com/your-org/UniServe.git .
git checkout main
```

## Step 3: Configure Environment

```bash
# Copy production environment template
cp .env.production.example .env.production

# Generate secrets
APP_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Edit .env.production with the generated values
nano .env.production
```

Required values to fill:

```
APP_SECRET_KEY=<paste APP_SECRET>
JWT_SECRET_KEY=<paste JWT_SECRET>
POSTGRES_USER=uniserve
POSTGRES_PASSWORD=<paste DB_PASS>
POSTGRES_DB=uniserve_prod
CORS_ORIGINS=["https://app.example.com"]
```

## Step 4: Configure DNS

In your DNS provider, create:

| Type | Name | Value |
|------|------|-------|
| A | api | your-server-ip |
| A | app | your-server-ip |

Wait for propagation: `dig +short api.example.com`

## Step 5: Configure Caddy for HTTPS

Edit `infrastructure/caddy/Caddyfile`:

```bash
nano infrastructure/caddy/Caddyfile
```

Replace `api.example.com` and `app.example.com` with your actual domains.

> **Phase 33 requirement — do not regress.** The static blocks must keep
> `try_files {path} {path}.html {path}/index.html /index.html`. Without
> `{path}.html`, every deep link (`/login`, `/dashboard/...`) silently
> serves the root shell and the client router bounces users to `/dashboard`.
> Verify after any edit: `grep try_files infrastructure/caddy/Caddyfile`
> must show all four tokens on the line.

## Step 6: Configure Web Build

Copy the template and confirm the API URL matches your real domain:

```bash
cp apps/web/.env.production.example apps/web/.env.production.local
nano apps/web/.env.production.local
# NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
```

> `NEXT_PUBLIC_API_URL` is baked into the static bundle at build time —
> changing it later requires a rebuild.

## Step 7: Build and Start Services

```bash
# Create backup directory
mkdir -p backups

# Build API image
docker compose -f docker-compose.prod.yml build api

# Build web static export (on the server)
# Dependency note (Phase 32): the root package-lock.json is committed and
# covers all npm workspaces. Install from the REPO ROOT with `npm ci
# --ignore-scripts` (plain `npm ci` fails: react-native-screens' install
# script expects dev-only tooling that is never installed for dependencies;
# no web-build package needs install scripts).
npm ci --ignore-scripts
( cd apps/web && NEXT_PUBLIC_API_URL=https://api.example.com/api/v1 npm run build )

# Verify static files were generated
ls apps/web/out/index.html
# Expected: apps/web/out/index.html

# Start PostgreSQL first
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for healthy
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U uniserve
```

## Step 8: Run Migrations

```bash
# Run migrations inside the API container
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Verify migration status
docker compose -f docker-compose.prod.yml run --rm api alembic current
# Expected: 0009 (head)

# Verify no pending metadata/migration drift
docker compose -f docker-compose.prod.yml run --rm api alembic check
# Expected: no new upgrade head (requires postgres to be running)
```

## Step 9: Start All Services

```bash
docker compose -f docker-compose.prod.yml up -d
```

## Step 10: Verify Health

```bash
# Check all containers are running
docker compose -f docker-compose.prod.yml ps

# Check API health
curl -s https://api.example.com/api/v1/health | python3 -m json.tool
# Expected: {"status": "healthy", "service": "uniserve-api", ...}

# Check readiness
curl -s https://api.example.com/api/v1/health/ready | python3 -m json.tool
# Expected: {"status": "ready"}

> **Monitoring note (Phase 28A design):** `/api/v1/health/ready` always
> returns HTTP 200, in both ready and degraded states. Assert on the JSON
> `status` field (`"ready"` vs `"degraded"`), never on the HTTP code.
> Degraded details appear in the same body (`database`, `schema` fields).

# Check web app
curl -sI https://app.example.com
# Expected: HTTP/2 200
```

## Step 11: Create Admin Account

```bash
# Access the API to create the first admin
# Option A: Register via API and promote via database
curl -s -X POST https://api.example.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "university_id": "ADMIN001",
    "first_name": "Admin",
    "last_name": "User",
    "university_email": "admin@example.com",
    "password": "YOUR-STRONG-PASSWORD",
    "category": "faculty"
  }'

# Promote to university_admin via direct SQL
docker compose -f docker-compose.prod.yml exec postgres psql -U uniserve -d uniserve_prod -c \
  "UPDATE users SET role = 'university_admin' WHERE university_id = 'ADMIN001';"
```

## Step 12: Configure Cafeteria

Log in as admin via the web app (`https://app.example.com`):

1. Navigate to Admin Dashboard → Cafeterias
2. Create your first cafeteria (e.g., "Main Cafeteria")
3. Assign a cafeteria manager
4. Create menu items with categories and prices

## Step 13: Publish First Menu

As cafeteria manager:

1. Log in to the web app
2. Navigate to Menu Management
3. Create a daily menu for today
4. Add menu items to the daily menu
5. Set status to "Published"

## Step 14: Verify Customer Ordering

1. Register a student account (or use existing)
2. Browse the cafeteria menu
3. Add items to cart
4. Place an order (cash or online — see payment note)
5. Verify order appears in staff view

> **Payment safety:** with no production payment provider configured,
> `POST /api/v1/payments/initiate` fails closed with **HTTP 503**
> (`Online payments are unavailable: no production payment provider is
> configured`). Cash ordering is unaffected. Enabling online payments
> requires an external provider contract and operator-supplied credentials
> (`DEPLOYMENT_BLOCKERS.md` B10) — never configure guessed values.

## Step 15: Verify Staff Operations

1. Log in as cafeteria staff
2. View incoming orders
3. Confirm and prepare an order
4. Mark as ready for pickup
5. Verify student receives notification

## Step 16: Verify Admin Access

1. Log in as university_admin
2. View dashboard overview
3. Check reports (sales, orders)
4. Verify user management works
5. Check notification system

## Step 17: Configure Backups

```bash
# Make backup script executable
chmod +x scripts/backup_database.sh

# Test backup
./scripts/backup_database.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /opt/uniserve/scripts/backup_database.sh /opt/uniserve/backups

> **Notes:** `scripts/backup_database.sh` targets the default production
> container name `uniserve_postgres` (as set by `docker-compose.prod.yml`).
> Each run verifies the dump with `pg_restore --list` before copying it out;
> verify manually anytime with `pg_restore --list <file> | head`.
> Keep at least one backup off the server. Never delete the only backup.

## Restore (Database)

```bash
# 1) Stop the API first so writes do not race the restore
docker compose -f docker-compose.prod.yml stop api

# 2) Restore (CONFIRM=yes is a required gate; the script verifies the dump
#    with pg_restore --list BEFORE touching the database)
CONFIRM=yes ./scripts/restore_database.sh backups/uniserve_<timestamp>.pgdump

# 3) Restart and verify
docker compose -f docker-compose.prod.yml up -d api
curl -s https://api.example.com/api/v1/health/ready | python3 -m json.tool
# Expected: {"status": "ready", "database": "connected", "schema": "present"}
docker compose -f docker-compose.prod.yml exec postgres psql -U uniserve -d uniserve_prod \
  -c "SELECT version_num FROM alembic_version;"
# Expected: 0009
```

> **Prerequisite:** the target database must already exist **with its
> `public` schema** — `pg_dump` does not emit `CREATE SCHEMA public` (true
> for any database created by PostgreSQL/Compose). If restore fails with
> `schema "public" does not exist`, create it first, then retry. A restore
> REPLACES current contents — always snapshot first if the data matters.
```

## Step 18: Configure Restart Policy

Docker Compose already sets `restart: unless-stopped` for all services. Additionally:

```bash
# Ensure Docker starts on boot
systemctl enable docker

# Verify
systemctl is-enabled docker
```

## Step 19: Final Smoke Test

```bash
# Run health check script
python3 scripts/production_health_check.py --api-url https://api.example.com

# Verify HTTPS is working
curl -sI https://api.example.com/api/v1/health
curl -sI https://app.example.com

# Check logs for errors
docker compose -f docker-compose.prod.yml logs --tail=50 api
docker compose -f docker-compose.prod.yml logs --tail=50 postgres
docker compose -f docker-compose.prod.yml logs --tail=50 caddy
```

Verify deep links by **hard-reloading** each route in a browser — each must
render route-specific content, not the root shell:
`/login`, `/register`, `/dashboard`, `/dashboard/orders`,
`/dashboard/menu`, `/dashboard/inventory`, `/dashboard/admin/overview`,
`/dashboard/admin/users`, `/dashboard/admin/refunds`,
`/dashboard/admin/reports`, `/dashboard/profile`.

Role smoke (mirrors the Phase 33 validated workflow): student
login → menu → cart → cash order → order history; faculty across both
cafeterias incl. guest ordering; cafeteria staff order operations +
inventory; manager menu/inventory/refunds/staff/reports; university admin
university-wide dashboard/users/cafeterias/reports/refunds. Cross-role and
cross-cafeteria access must remain blocked.

## Step 20: Deployment Complete

✅ UniServe is now running in production.

**Next steps:**
- Monitor logs for the first 24 hours
- Verify backup ran successfully at 2 AM
- Set up uptime monitoring (e.g., UptimeRobot, BetterStack)
- Configure email notifications for critical alerts

---

## Update & Rollback

**Application update (subsequent releases):**

```bash
git pull                                  # new commit on main
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

**Rollback paths:**

| Layer | Rollback |
|---|---|
| API image | `git checkout <previous-commit>` → `build api` → `up -d api` |
| Web artifact | rebuild the static export from the previous commit (with `NEXT_PUBLIC_API_URL` set); Caddy serves `apps/web/out` automatically via the bind mount |
| Caddy config | `git checkout <previous-commit> -- infrastructure/caddy/Caddyfile` → `restart caddy` — preserve the `try_files` deep-link line |
| Database migrations | **Do not blindly downgrade.** Alembic downgrades are not guaranteed lossless. Preferred: restore the pre-deploy backup (see Restore), or roll forward with a fix migration |

First deployment has no prior application backup — after the initial
`alembic upgrade head`, note the applied head and take a first backup
immediately after seeding.

## Troubleshooting

| Symptom | Diagnosis | Action |
|---|---|---|
| `/api/docs`, `/api/redoc`, `/api/openapi.json` → 404 | Expected in production (`APP_DEBUG=false` gates them — verified live in Phase 33) | None |
| `POST /payments/initiate` → 503 | No production payment provider configured | Expected fail-closed; cash orders unaffected |
| `/api/v1/health/ready` HTTP 200 but `status: degraded` | Database/schema issue (by design readiness never uses HTTP codes) | Read `database`/`schema` fields; `docker compose logs postgres` |
| Web deep links bounce to `/dashboard` home | Caddy `try_files` lost `{path}.html` (regression of the Phase 33 fix) | Restore the documented `try_files` line (Step 5) and `restart caddy` |
| One 401 on `/auth/me` after web hard reload | In-memory access token + silent refresh (first attempt before refresh completes) | Expected; repeated 401s → check CORS (B8) and auth logs |
| `restore_database.sh`: `schema "public" does not exist` | Target database lacks the `public` schema | `CREATE SCHEMA public AUTHORIZATION <db-user>;` then retry |
| `backup_database.sh`: `role ... does not exist` | Script targets the default container `uniserve_postgres` | Run from the production compose context (or adjust `CONTAINER_NAME`) |
| Container `Up` but API unreachable | Workers crash-looped on settings validation (empty/weak default secrets) | `docker compose logs api`; regenerate secrets (`token_urlsafe(64)`), `up -d`. Container `Up` ≠ serving |
| Errors in production logs | Startup/DB/auth/5xx/worker issues | `docker compose logs api postgres caddy`; `LOG_FORMAT=json` — grep `"level":"error"` |

## Appendix: Mobile App (EAS) — Not Part of Server Deployment

The mobile app is built and distributed with Expo EAS (`apps/mobile/eas.json`);
it is **not** deployed by this server runbook. Before an EAS production build:

1. Set the production API URL in `apps/mobile/src/config.ts`
   (`ENV.production.API_BASE_URL`) to your real API domain.
   The committed placeholder is `https://api.uniserve.app/api/v1`.
2. Build from `apps/mobile/` with an Expo account (external requirement):
   `eas build --platform all --profile production`
3. This repository produces no APK/IPA in CI — store submission is manual.

---

## Appendix: Redis — Not Required at Runtime

Verified during production deployment preparation: **no Redis client is
imported anywhere in `apps/api/app`**. The API starts and serves normally
without Redis; `docker-compose.prod.yml` ships with the Redis service
commented out. Only uncomment it if you later implement Redis-based
caching or sessions.
