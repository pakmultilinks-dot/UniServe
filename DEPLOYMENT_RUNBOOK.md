# UniServe — Deployment Runbook

> Step-by-step guide for deploying UniServe to a production server.
> **Estimated time:** 30–60 minutes for first deployment.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| VPS | Ubuntu 22.04+ / Debian 12+, 2+ CPU, 4GB+ RAM, 40GB+ SSD |
| Domain | Two subdomains: `api.example.com`, `app.example.com` |
| DNS | A records pointing both subdomains to your server IP |
| SSH | Root or sudo access to the server |

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
# NOTE: the repo has no package-lock.json — use npm install, NOT npm ci
cd apps/web
npm install
NEXT_PUBLIC_API_URL=https://api.example.com/api/v1 npm run build
cd ../..

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
4. Place an order (cash or online)
5. Verify order appears in staff view

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

## Step 20: Deployment Complete

✅ UniServe is now running in production.

**Next steps:**
- Monitor logs for the first 24 hours
- Verify backup ran successfully at 2 AM
- Set up uptime monitoring (e.g., UptimeRobot, BetterStack)
- Configure email notifications for critical alerts

---

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
