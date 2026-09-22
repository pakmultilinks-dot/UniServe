# UniServe — Architecture Overview

## System Architecture

UniServe is a university cafeteria management and online ordering platform built as a **modular monolith** with clean domain boundaries designed for future service extraction.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Applications                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Mobile App   │  │ Web App      │  │ Future Apps  │  │
│  │ (React Native│  │ (Next.js)    │  │              │  │
│  │  + Expo)     │  │              │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI       │
                    │   REST API      │
                    │   (Modular      │
                    │    Monolith)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
     │  PostgreSQL   │ │  Redis   │ │  Future     │
     │  Database     │ │  Cache   │ │  Services   │
     └───────────────┘ └──────────┘ └─────────────┘
```

### Backend Architecture (Modular Monolith)

The backend is organized by business domains:

```
FastAPI Application
├── Core (cross-cutting concerns)
│   ├── Configuration
│   ├── Database
│   ├── Logging
│   └── Security
├── API Layer (routing, dependencies)
└── Modules (business domains)
    ├── Auth
    ├── Users
    ├── Cafeterias
    ├── Menus
    ├── Inventory
    ├── Orders
    ├── Payments
    ├── Refunds
    ├── Notifications
    ├── Reports
    └── Administration
```

Each module follows a consistent internal structure:
```
module/
├── __init__.py
├── router.py       # API endpoints
├── schemas.py      # Pydantic models (request/response)
├── service.py      # Business logic
├── models.py       # SQLAlchemy models
└── dependencies.py # Module-specific dependencies
```

### Key Architectural Decisions

1. **Server-side authorization** — All access control is enforced by the backend
2. **Atomic operations** — Critical business logic uses database transactions
3. **Two independent cafeterias** — Student and Faculty cafeterias with distinct access rules
4. **REST-first API** — REST for normal operations, real-time only where genuinely needed
5. **Environment-based configuration** — All secrets via environment variables

### Data Flow

1. Client sends request to API
2. API validates input (Pydantic)
3. Authentication/Authorization middleware
4. Module service processes business logic
5. Database operations (with transactions)
6. Response serialization and return

### Security Model

- JWT-based authentication (access tokens + refresh tokens with rotation & reuse detection)
- Role-based access control (RBAC) via `RequireRole` dependency
- Cafeteria-scoped permissions via `RequireCafeteriaScope` dependency
- Backend-enforced authorization (never trust frontend)
- Argon2 password hashing (bcrypt fallback)
- PBKDF2 PIN hashing with constant-time comparison
- Hashed OTPs with expiry, max attempts, and rate limiting
- Brute-force protection (login lockout, PIN lockout)
- Comprehensive audit logging (24+ event types)
- Generic error messages (no user enumeration)
- Biometric authentication handled client-side only (see `biometric-boundary.md`)
