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

# Python dependencies — install from pyproject.toml (base dependencies).
# The app package is not present yet in this layer, so only dependencies
# are resolved here; the layer stays cached across application code changes.
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Application code
COPY . .

EXPOSE 8000

# uvicorn runs 2 worker processes; the in-process pickup-expiry worker is
# safe under multiple workers (SELECT ... FOR UPDATE SKIP LOCKED).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
