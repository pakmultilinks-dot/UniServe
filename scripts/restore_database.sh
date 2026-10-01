#!/usr/bin/env bash
#
# UniServe — PostgreSQL restore (production runbook companion to backup_database.sh)
#
# Restores a pg_dump custom-format backup into the running production database
# container. Designed for the docker-compose.prod.yml topology where PostgreSQL
# is NOT published on any host port (expose only) — restore runs inside the
# container via `docker exec`.
#
# Usage:
#   ./scripts/restore_database.sh backups/uniserve_20260101_120000.pgdump
#
# IMPORTANT:
#   1. Stop the API before restoring (writes must not race the restore):
#        docker compose -f docker-compose.prod.yml stop api
#   2. This REPLACES the current database contents with the backup snapshot
#      (--clean --if-exists drops and recreates objects present in the dump).
#   3. Requires the database container (uniserve_postgres) to be running.
#   4. After restore, restart the API and verify readiness:
#        docker compose -f docker-compose.prod.yml up -d api
#        curl -fsS http://localhost/api/v1/health/ready   # via Caddy on the VPS

set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup.pgdump>}"
CONTAINER_NAME="${CONTAINER_NAME:-uniserve_postgres}"
DB_USER="${DB_USER:-uniserve}"
DB_NAME="${DB_NAME:-uniserve_prod}"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "ERROR: container '$CONTAINER_NAME' is not running. Start it first:" >&2
    echo "  docker compose -f docker-compose.prod.yml up -d postgres" >&2
    exit 1
fi

echo "Restoring $BACKUP_FILE -> container=$CONTAINER_NAME db=$DB_NAME user=$DB_USER"
# --clean --if-exists : drop existing objects before recreate (full snapshot restore)
# --no-owner --no-acl  : avoid ownership/ACL assumptions from the dump environment
docker exec -i "$CONTAINER_NAME" \
    pg_restore --username="$DB_USER" --dbname="$DB_NAME" \
    --clean --if-exists --no-owner --no-acl < "$BACKUP_FILE"

echo ""
echo "Restore complete."
echo "Next steps:"
echo "  1. Verify schema version:  docker compose -f docker-compose.prod.yml run --rm api alembic current"
echo "  2. Restart API:            docker compose -f docker-compose.prod.yml up -d api"
echo "  3. Verify readiness:       curl -fsS <origin>/api/v1/health/ready"
