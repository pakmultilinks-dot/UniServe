# UniServe — Database Operations Guide

> PostgreSQL 16, managed via Alembic migrations.
> **Last verified against repo state:** Phase 30 production deployment preparation.

---

## How the Database URL Is Resolved

`apps/api/alembic.ini` intentionally contains **no** database URL.
`apps/api/migrations/env.py` overrides `sqlalchemy.url` at runtime with
`settings.DATABASE_URL`, built from `POSTGRES_*` environment variables
(loaded by `apps/api/app/core/config.py`).

Consequence: **Alembic must run where the correct POSTGRES_* environment is
visible** — inside the API container (production) or from `apps/api/` with
`.env` present (development).

| Environment | Where to run Alembic | POSTGRES_HOST | Port |
|-------------|----------------------|---------------|------|
| Development | `apps/api/` on host (`.env` loaded) | `localhost` | `5433` (dev compose) |
| Production | Inside the API container | `postgres` (Docker service) | `5432` (internal only) |

> ⚠️ **Do not run dev and prod compose stacks on the same host.** Both define
> `container_name: uniserve_postgres` — starting one while the other runs
> fails with a name conflict. The production project name (`uniserve-prod`)
> keeps **volumes** separate (`uniserve-prod_postgres_data` vs dev
> `uniserve_postgres_data`), but container names collide.

---

## Quick Reference

| Operation | Command |
|-----------|---------|
| Apply all pending migrations | `alembic upgrade head` |
| Check current migration | `alembic current` |
| Check for pending migrations | `alembic check` |
| View migration history | `alembic history` |
| Backup database | `./scripts/backup_database.sh` |
| Restore database | `CONFIRM=yes ./scripts/restore_database.sh <file>` |
| Health check | `pg_isready` (see below) |

---

## Initial Migration (New Deployment)

Production (inside the API container):

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm api alembic current
# Expected: <head revision> (head)
```

Development (from `apps/api/`, dev compose postgres running on :5433):

```bash
cd apps/api
../../.venv/Scripts/python.exe -m alembic upgrade head   # Windows venv
# or: alembic upgrade head                                # with venv activated
```

This applies all migrations up to head `0009` and creates the full schema
(tables, indexes, enum types, `uuid-ossp` / `pg_trgm` extensions).

## Migration Upgrade

```bash
# Apply any pending migrations
alembic upgrade head

# Check current version
alembic current

# Check if new upgrade operations exist
alembic check
# Expected: "No new upgrade operations detected"

# View migration history
alembic history
```

## Migration Rollback Policy

> ⚠️ **Never blindly roll back migrations in production.**
>
> - **Preferred: forward fix.** Write a new migration that corrects the
>   problem; do not downgrade a production database.
> - **Downgrade only** when you fully understand the data implications,
>   **after** taking a verified backup (`./scripts/backup_database.sh`),
>   and with the API stopped so no writes race the schema change:
>
> ```bash
> ./scripts/backup_database.sh ./backups
> docker compose -f docker-compose.prod.yml stop api
> docker compose -f docker-compose.prod.yml run --rm api alembic downgrade -1
> docker compose -f docker-compose.prod.yml up -d api
> ```
>
> - `alembic downgrade base` destroys the schema. It is a last-resort,
>   data-loss operation — never part of a routine rollback.

## Database Backup

### Scripted Backup (Recommended)

```bash
# Production — dumps the uniserve_postgres container, verifies the dump
# (pg_restore --list), stores it timestamped under ./backups/, and prunes
# backups older than 30 days. Fails non-zero on any error.
./scripts/backup_database.sh ./backups
```

Schedule via cron (daily at 2 AM):

```cron
0 2 * * * cd /opt/uniserve && ./scripts/backup_database.sh /opt/uniserve/backups
```

> Backups are **not** automatic out of the box — the cron entry above must
> be installed by the operator.

### Manual Backup (Container)

> Production does **not** publish PostgreSQL on any host port (`expose` only).
> Use `docker exec` — the host-port variant below is development-only.

```bash
# Using pg_dump with Docker
docker exec uniserve_postgres pg_dump \
  -U uniserve \
  -d uniserve_prod \
  --format=custom \
  --compress=9 \
  -f /tmp/backup_$(date +%Y%m%d_%H%M%S).pgdump

# Copy backup to host
docker cp uniserve_postgres:/tmp/backup_*.pgdump ./backups/
```

### Backup via Host (development only — port 5433 exposed)

```bash
# Development only (port 5433 exposed)
pg_dump \
  -h localhost \
  -p 5433 \
  -U uniserve \
  -d uniserve_dev \
  --format=custom \
  --compress=9 \
  -f backup_$(date +%Y%m%d_%H%M%S).pgdump
```

### Schema-Only Backup

```bash
docker exec uniserve_postgres pg_dump \
  -U uniserve \
  -d uniserve_prod \
  --schema-only \
  -f /tmp/schema_only.sql
```

## Database Restore

```bash
# 1. Snapshot the CURRENT state first (so a bad restore can be rolled forward)
./scripts/backup_database.sh ./backups

# 2. Stop the API so writes cannot race the restore
docker compose -f docker-compose.prod.yml stop api

# 3. Restore — CONFIRM=yes is mandatory (the script refuses without it);
#    the dump is verified with pg_restore --list before anything destructive
CONFIRM=yes ./scripts/restore_database.sh backups/uniserve_YYYYmmdd_HHMMSS.pgdump

# 4. Restart and verify
docker compose -f docker-compose.prod.yml up -d api
docker compose -f docker-compose.prod.yml run --rm api alembic current
```

### Full Reset (DANGEROUS — destroys all data)

```bash
# Backup first. ALL data is lost.
./scripts/backup_database.sh ./backups

# Stop all services
docker compose -f docker-compose.prod.yml down

# Remove the PRODUCTION project volume (name is project-prefixed)
docker volume rm uniserve-prod_postgres_data

# Restart (fresh database)
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for healthy, then migrate
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U uniserve
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

## Health Checks

```bash
# Production — PostgreSQL accepting connections
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U uniserve -d uniserve_prod

# Production — API readiness endpoint (through Caddy/HTTPS)
curl -fsS https://<your-api-domain>/api/v1/health/ready

# Development — host port 5433
pg_isready -h localhost -p 5433 -U uniserve

# Check table count (any environment)
docker compose -f docker-compose.prod.yml exec postgres psql -U uniserve -d uniserve_prod -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
# Expected: 27

# Check active connections
docker compose -f docker-compose.prod.yml exec postgres psql -U uniserve -d uniserve_prod -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

## Connection Pool Configuration

The API uses SQLAlchemy async with connection pooling:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `pool_size` | 20 | Persistent connections in pool |
| `max_overflow` | 10 | Extra connections for peak load (max 30) |
| `pool_pre_ping` | True | Validates connections before use |

These are configured in `apps/api/app/core/database.py`. For production with a single API container, these defaults are appropriate. For multiple API containers, reduce `pool_size` proportionally.

## Timezone

PostgreSQL is configured with `TZ=Asia/Karachi` in the Docker Compose environment. All timestamps are stored as `TIMESTAMPTZ` (timezone-aware). This matches the application's `ZoneInfo("Asia/Karachi")` usage.
