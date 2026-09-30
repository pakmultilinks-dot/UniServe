# UniServe — Update & Rollback Procedure

> How to safely update a running production deployment.
> **Rule: Always backup before migrating.**

---

## Update Procedure

### 1. Backup Before Update

```bash
# Create a pre-update backup
./scripts/backup_database.sh ./backups

# Verify backup exists
ls -la backups/uniserve_*.pgdump | tail -1
```

### 2. Pull Latest Code

```bash
cd /opt/uniserve
git fetch origin
git log --oneline HEAD..origin/main  # Review what changed
git pull origin main
```

### 3. Review Migration Changes

```bash
# Check if there are new migrations
ls apps/api/migrations/versions/ | sort

# Compare with current head
docker compose -f docker-compose.prod.yml run --rm api alembic current
# vs
docker compose -f docker-compose.prod.yml run --rm api alembic heads
```

### 4. Rebuild API Image

```bash
docker compose -f docker-compose.prod.yml build api
```

### 5. Run Migrations (If Any)

```bash
# Only if new migrations exist
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Verify
docker compose -f docker-compose.prod.yml run --rm api alembic check
# Expected: "No new upgrade operations detected"
```

### 6. Rebuild Web (If Changed)

```bash
# Rebuild static export
docker compose -f docker-compose.prod.yml build caddy

# Or if using Next.js in a separate container:
# docker compose -f docker-compose.prod.yml build web
```

### 7. Restart Services

```bash
# Rolling restart — API first, then web
docker compose -f docker-compose.prod.yml up -d api
sleep 10
docker compose -f docker-compose.prod.yml up -d caddy
```

### 8. Verify Health

```bash
# Check API
curl -s https://api.example.com/api/v1/health | python3 -m json.tool

# Check all containers
docker compose -f docker-compose.prod.yml ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs --tail=20 api
```

---

## Rollback Procedure

### Code Rollback (No Migration Changes)

If the update only changed application code (no new migrations):

```bash
# Revert to previous commit
git checkout HEAD~1

# Rebuild and restart
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml up -d api
```

### Code + Migration Rollback

If the update included new migrations that need to be reverted:

```bash
# ⚠️ DANGEROUS: Only do this if you understand the data implications

# 1. Backup current state
./scripts/backup_database.sh ./backups

# 2. Revert migration
docker compose -f docker-compose.prod.yml run --rm api alembic downgrade -1

# 3. Revert code
git checkout HEAD~1

# 4. Rebuild and restart
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml up -d api
```

### Full Restore (Emergency)

If the database is corrupted or a migration caused critical issues:

```bash
# 1. Stop API (prevent writes)
docker compose -f docker-compose.prod.yml stop api

# 2. Restore database from backup
docker exec -i uniserve_postgres pg_restore \
  -U uniserve \
  -d uniserve_prod \
  --clean \
  --if-exists \
  < backups/uniserve_YYYYMMDD_HHMMSS.pgdump

# 3. Revert code to last known good state
git checkout <good-commit-hash>

# 4. Rebuild and restart
docker compose -f docker-compose.prod.yml build api
docker compose -f docker-compose.prod.yml up -d

# 5. Verify
curl -s https://api.example.com/api/v1/health
```

---

## Migration Safety Rules

1. **Never** drop a column or table in production without a backup
2. **Always** test migrations on a staging environment first
3. **Always** make migrations reversible (provide downgrade paths)
4. **Never** rename a column in place — create new, migrate data, drop old
5. **Never** change enum values by dropping and recreating — use ALTER TYPE ADD VALUE
6. **Always** run `alembic check` after migration to verify no drift
7. **Backup immediately** before any migration in production

## Deployment Checklist

- [ ] Pre-update backup created
- [ ] Code reviewed for breaking changes
- [ ] Migrations tested on staging
- [ ] API image rebuilt
- [ ] Migrations applied successfully
- [ ] Health endpoints returning 200
- [ ] No errors in logs
- [ ] Web app loads correctly
- [ ] Mobile app connects successfully
