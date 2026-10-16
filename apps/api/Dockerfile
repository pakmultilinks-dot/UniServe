FROM python:3.11-slim-bookworm

WORKDIR /app

# System dependencies for PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Stream container logs unbuffered; skip bytecode writes in the image
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Python dependencies — install EXACTLY the committed lock (--no-deps: no
# resolution, no silent transitive upgrades) and gate completeness with
# pip check. Known-good tested pins; see requirements.lock.txt for the
# regeneration procedure. The app package is not present yet in this layer,
# so only dependencies are installed here; the layer stays cached across
# application code changes.
COPY pyproject.toml README.md requirements.lock.txt ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock.txt \
    && pip check \
    && pip install --no-cache-dir --no-deps . \
    && pip check

# Application code
COPY . .

# Startup script runs migrations, then starts the API
RUN chmod +x /app/start.sh

EXPOSE 8000

# uvicorn runs 2 worker processes; the in-process pickup-expiry worker is
# safe under multiple workers (SELECT ... FOR UPDATE SKIP LOCKED).
CMD ["/app/start.sh"]
