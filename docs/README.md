# UniServe

## Overview

UniServe is a university cafeteria management and online ordering platform designed to serve both students and faculty through independent cafeteria systems.

### Cafeteria Access Rules

| Cafeteria | Students | Faculty |
|-----------|----------|---------|
| Student Cafeteria | ✅ Allowed | ✅ Allowed |
| Faculty Cafeteria | ❌ Not Allowed | ✅ Allowed |

These permissions are **enforced by the backend**, not just the frontend UI.

## Repository Structure

```
UniServe/
├── apps/
│   ├── api/          # FastAPI backend
│   ├── mobile/       # React Native + Expo mobile app
│   └── web/          # Next.js web application
├── packages/
│   └── shared-types/ # Shared TypeScript types
├── infrastructure/
│   ├── docker/       # Docker configurations
│   ├── database/     # Database init scripts
│   └── deployment/   # Deployment configs
├── docs/
│   ├── architecture/ # Architecture documentation
│   ├── decisions/    # Architecture Decision Records
│   └── development/  # Development guides
├── scripts/          # Development utility scripts
├── tests/
│   └── integration/  # Integration tests
├── docker-compose.yml
└── README.md
```

## Getting Started

See [Development Setup](docs/development/setup.md) for detailed instructions.

**Quick start:**
```bash
# Start infrastructure
docker compose up -d

# Set up and run the API
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Technology Stack

- **Backend:** Python, FastAPI, PostgreSQL
- **Mobile:** React Native, Expo, TypeScript
- **Web:** Next.js, TypeScript
- **Infrastructure:** Docker

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Architecture Decision Records](docs/decisions/)
- [Development Phases](docs/architecture/phases.md)
- [Architectural Rules](docs/architecture/rules.md)
