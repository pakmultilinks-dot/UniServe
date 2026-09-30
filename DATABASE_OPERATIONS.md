# UniServe — Database Operations Guide

> PostgreSQL 16, managed via Alembic migrations.
> **All commands assume the API container is running** or PostgreSQL is accessible at localhost:5433.

---

## Quick Reference

| Operation | Command |
|-----------|---------|
| Apply all pending migrations | `alembic upgrade head` |
| Check current migration | `alembic current` |
| Check for pending migrations | `alembic check` |
| Backup database | `pg_dump` (see below) |
| Restore database | `pg_restore` (see below) |
| Health check | `pg_isready` |

---

## Initial Migration (New Deployment)

```bash
# Inside the API container or with PostgreSQL accessible:
cd /app  # or apps/api/
alembic upgrade head
```

This applies all 10 migrations (0000 → 0009) and creates:
- 27 tables
- 105 indexes
- 3 enum types (user_role, user_category, account_status, + others)
- PostgreSQL extensions (uuid-ossp, pg_trgm)

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

## Migration Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade 0005

# Rollback all (DANGEROUS — destroys schema)
alembic downgrade base
```

> ⚠️ **Always backup before rolling back migrations in production.**

## Database Backup

### Full Backup (Recommended)

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

### Backup via Host (if port is exposed)

```bash
pg_dump \
  -h localhost \
  -p 5433 \
  -U uniserve \
  -d uniserve_prod \
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
# Stop the API first to prevent writes
docker compose stop api

# Restore from backup
docker exec -i uniserve_postgres pg_restore \
  -U uniserve \
  -d uniserve_prod \
  --clean \
  --if-exists \
  < backup_20260930_120000.pgdump

# Restart API
docker compose start api
```

### Full Reset (DANGEROUS — destroys all data)

```bash
# Stop all services
docker compose down

# Remove volume
docker volume rm uniserve_postgres_data

# Restart (fresh database)
docker compose up -d postgres

# Wait for healthy, then migrate
docker compose exec postgres pg_isready -U uniserve
alembic upgrade head
```

## Health Check

```bash
# Check PostgreSQL is accepting connections
docker exec uniserve_postgres pg_isready -U uniserve -d uniserve_prod

# Check table count
docker exec uniserve_postgres psql -U uniserve -d uniserve_prod -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
# Expected: 27

# Check connection count
docker exec uniserve_postgres psql -U uniserve -d uniserve_prod -c \
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
