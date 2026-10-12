#!/bin/sh
set -e

# Run database migrations before starting the API.
# alembic upgrade head is idempotent and safe to run on every deploy.
echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Seed demo data on first deploy (only when SEED_DEMO_DATA=true).
# Both seed scripts are idempotent and safe to rerun.
if [ "$SEED_DEMO_DATA" = "true" ]; then
  echo "Seeding demo data..."
  python scripts/seed_student_cafeteria.py
  python scripts/seed_demo_users.py
  echo "Demo data seeded."
fi

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
