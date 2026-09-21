# UniServe

A university cafeteria management and online ordering platform.

## Overview

UniServe is a comprehensive system designed for university cafeteria operations, supporting:

- **Student Cafeteria** — accessible to students and faculty
- **Faculty Cafeteria** — accessible to faculty only

The platform provides mobile ordering, cafeteria management, and university administration capabilities.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, PostgreSQL |
| **Mobile** | React Native, Expo, TypeScript |
| **Web** | Next.js, TypeScript |
| **Infrastructure** | Docker, university-controlled private cloud |

## Repository Structure

```
UniServe/
├── apps/
│   ├── api/              # FastAPI backend
│   ├── mobile/           # React Native + Expo mobile app
│   └── web/              # Next.js web application
├── packages/
│   └── shared-types/     # Shared TypeScript type definitions
├── infrastructure/
│   ├── docker/           # Docker configurations
│   ├── database/         # Database setup and migrations
│   └── deployment/       # Deployment configurations
├── docs/
│   ├── architecture/     # Architecture documentation
│   ├── decisions/        # Architecture Decision Records (ADRs)
│   └── development/      # Development guides
├── scripts/              # Development and utility scripts
├── tests/
│   └── integration/      # Integration tests
├── .gitignore
├── .env.example
├── docker-compose.yml
└── README.md
```

## Architecture

UniServe follows a **modular monolith** architecture:

- Clean domain boundaries within the backend
- Designed for future service extraction if needed
- Server-side authorization enforcement
- Atomic operations for critical business logic

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL (or use Docker)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd UniServe
   ```

2. **Start infrastructure**
   ```bash
   docker compose up -d
   ```

3. **Set up backend**
   ```bash
   cd apps/api
   python -m venv .venv
   .venv/Scripts/activate  # Windows
   pip install -e ".[dev]"
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

5. **Run database migrations**
   ```bash
   cd apps/api
   alembic upgrade head
   ```

6. **Start the API server**
   ```bash
   cd apps/api
   uvicorn app.main:app --reload
   ```

7. **Verify**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

## Development Phases

This project is developed in controlled phases:

1. **Phase 1 — Foundation & Structural Architecture** ← *Current*
2. Phase 2 — Authentication & Authorization
3. Phase 3 — Menu & Cafeteria Management
4. Phase 4 — Ordering System
5. Phase 5 — Payments & Refunds
6. Phase 6 — Notifications & Real-time
7. Phase 7 — Reporting & Analytics
8. Phase 8 — Polish & Production Readiness

## Contributing

- Follow the architectural decisions documented in `docs/decisions/`
- Write tests for new functionality
- Use type hints and proper validation
- Never commit secrets or credentials

## License

Proprietary — University use only.
