FROM python:3.11-slim-bookworm

WORKDIR /app

# System dependencies for PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies — install only production extras
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."

# Application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
