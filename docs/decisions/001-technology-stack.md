# UniServe — Technology Decisions

## Backend

### Decision: FastAPI + PostgreSQL + Modular Monolith

**Context:** UniServe needs a robust backend for cafeteria management, ordering, and payment processing.

**Decision:** Use FastAPI with PostgreSQL in a modular monolith architecture.

**Rationale:**
- FastAPI provides excellent async performance, automatic OpenAPI docs, and type safety
- PostgreSQL offers reliability, JSON support, and strong consistency for transactions
- Modular monolith avoids premature microservices complexity while maintaining clean boundaries
- Designed for future extraction into services if scaling requires it

**Consequences:**
- Single deployment unit simplifies operations
- Module boundaries must be strictly maintained
- Database migrations affect a single schema

---

## Frontend (Mobile)

### Decision: React Native + Expo + TypeScript

**Context:** Need a cross-platform mobile app for student and faculty ordering.

**Decision:** Use React Native with Expo and TypeScript.

**Rationale:**
- Single codebase for iOS and Android
- Expo simplifies build and deployment
- TypeScript ensures type safety across the stack
- Large ecosystem and community support

---

## Frontend (Web)

### Decision: Next.js + TypeScript

**Context:** Need web dashboards for cafeteria operations and university administration.

**Decision:** Use Next.js with TypeScript.

**Rationale:**
- Server-side rendering for performance
- File-based routing for intuitive structure
- TypeScript for type safety
- API routes available if needed for BFF pattern

---

## Communication

### Decision: REST API

**Context:** Need stable API architecture for client-server communication.

**Decision:** Use REST for normal operations. Real-time (WebSockets) only where genuinely valuable (order status tracking).

**Rationale:**
- REST is well-understood, cacheable, and widely supported
- Real-time adds complexity — only introduce when user experience requires it
- OpenAPI/Swagger auto-generation from FastAPI

---

## Authentication

### Decision: JWT with Access/Refresh Token Pattern

**Context:** Need secure authentication for multiple client types (mobile, web).

**Decision:** JWT tokens with short-lived access tokens and longer-lived refresh tokens.

**Rationale:**
- Stateless authentication scales well
- Refresh tokens allow session management
- Works across mobile and web clients
- Can be validated without database lookups for performance

---

## Database Migrations

### Decision: Alembic

**Context:** Need reliable database schema evolution.

**Decision:** Use Alembic for PostgreSQL migrations.

**Rationale:**
- Standard tool for SQLAlchemy-based projects
- Supports both autogeneration and manual scripts
- Async support available
- Well-tested and widely used

---

## Configuration

### Decision: Environment Variables + Pydantic Settings

**Context:** Need secure, environment-specific configuration.

**Decision:** Use `.env` files for local development with Pydantic validation.

**Rationale:**
- Secrets never committed to Git
- Type-safe configuration with validation
- Clear separation of environments
- Fail-fast on missing required values

---

## Future Decisions (Deferred)

- Caching strategy (Redis)
- Background task processing
- Real-time notification system
- Payment gateway selection
- Push notification provider
- Monitoring and observability
