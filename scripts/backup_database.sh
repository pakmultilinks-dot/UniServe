#!/usr/bin/env bash
# UniServe — PostgreSQL Backup Script
# Run daily via cron or manually.
#
# Usage:
#   ./scripts/backup_database.sh
#   ./scripts/backup_database.sh /custom/backup/dir
#
# Cron (daily at 2 AM):
#   0 2 * * * /path/to/UniServe/scripts/backup_database.sh /path/to/backups

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="uniserve_postgres"
DB_USER="${POSTGRES_USER:-uniserve}"
DB_NAME="${POSTGRES_DB:-uniserve_prod}"
BACKUP_FILE="uniserve_${TIMESTAMP}.pgdump"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup: $DB_NAME → $BACKUP_DIR/$BACKUP_FILE"

# Run pg_dump inside the container
docker exec "$CONTAINER_NAME" pg_dump \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --format=custom \
  --compress=9 \
  -f "/tmp/$BACKUP_FILE"

# Verify the dump is readable BEFORE copying it out or deleting the temp file
docker exec "$CONTAINER_NAME" pg_restore --list "/tmp/$BACKUP_FILE" > /dev/null
echo "[$(date)] Backup verified (pg_restore --list succeeded)"

# Copy to host
docker cp "$CONTAINER_NAME:/tmp/$BACKUP_FILE" "$BACKUP_DIR/$BACKUP_FILE"

# Remove temp file from container
docker exec "$CONTAINER_NAME" rm "/tmp/$BACKUP_FILE"

# Get file size
FILE_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)

echo "[$(date)] Backup complete: $BACKUP_DIR/$BACKUP_FILE ($FILE_SIZE)"

# Retention: remove backups older than 30 days
find "$BACKUP_DIR" -name "uniserve_*.pgdump" -mtime +30 -delete 2>/dev/null || true
REMOVED=$(find "$BACKUP_DIR" -name "uniserve_*.pgdump" -mtime +30 2>/dev/null | wc -l)
if [ "$REMOVED" -gt 0 ]; then
  echo "[$(date)] Cleaned $REMOVED backups older than 30 days"
fi

echo "[$(date)] Done."
