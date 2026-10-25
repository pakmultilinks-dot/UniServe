#!/bin/sh
set -e

# Run database migrations before starting the API.
# alembic upgrade head is idempotent and safe to run on every deploy.
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Production startup never creates demo users, resets passwords, or imports menus.
# Provisioning is an explicit operator task, separate from restarts/cold starts.

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
