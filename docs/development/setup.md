# UniServe — Development Setup Guide

## Prerequisites

Install the following on your development machine:

- **Python 3.11+** — Backend development
- **Node.js 18+** — Frontend development
- **Docker & Docker Compose** — Database and infrastructure
- **Git** — Version control
- **Code editor** — VS Code recommended with Python and TypeScript extensions

## Quick Start

### 1. Clone and enter the repository

```bash
git clone <repository-url>
cd UniServe
```

### 2. Start the database

```bash
docker compose up -d postgres redis
```

This starts PostgreSQL on port 5432 and Redis on port 6379.

### 3. Set up the backend API

```bash
cd apps/api

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env if needed (defaults work with Docker Compose)

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`.

### 4. Verify the API

```bash
# Health check
curl http://localhost:8000/api/v1/health

# API docs (in development mode)
# Open http://localhost:8000/api/docs in your browser
```

### 5. Set up the web app (optional)

```bash
cd apps/web
npm install
npm run dev
```

The web app is now running at `http://localhost:3000`.

### 6. Set up the mobile app (optional)

```bash
cd apps/mobile
npm install
npx expo start
```

## Development Commands

### Backend

```bash
cd apps/api

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Lint code
ruff check .

# Format code
ruff format .

# Type checking
mypy app/

# Create a new migration
alembic revision --autogenerate -m "description"
```

### Web

```bash
cd apps/web

# Development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Mobile

```bash
cd apps/mobile

# Start Expo development
npx expo start

# Type checking
npm run type-check
```

## Project Structure

```
UniServe/
├── apps/
│   ├── api/              # FastAPI backend (main application)
│   ├── mobile/           # React Native + Expo mobile app
│   └── web/              # Next.js web application
├── packages/
│   └── shared-types/     # Shared TypeScript types
├── infrastructure/
│   ├── docker/           # Docker configurations
│   ├── database/         # Database init scripts
│   └── deployment/       # Deployment configs (future)
├── docs/
│   ├── architecture/     # Architecture docs
│   ├── decisions/        # ADRs
│   └── development/      # Dev guides
├── scripts/              # Utility scripts
├── tests/
│   └── integration/      # Integration tests
├── docker-compose.yml
├── .env.example
└── README.md
```

## Troubleshooting

### Database connection refused
Ensure Docker is running and the PostgreSQL container is up:
```bash
docker compose ps
docker compose logs postgres
```

### Port already in use
Check what's using the port:
```bash
# Windows
netstat -ano | findstr :5432
# macOS/Linux
lsof -i :5432
```

### Migration errors
Reset the database (development only):
```bash
docker compose down -v
docker compose up -d postgres
alembic upgrade head
```
