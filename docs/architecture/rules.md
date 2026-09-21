# UniServe — Architectural Rules

## Code Quality Rules

1. **No duplicated business logic** — Each business rule exists in exactly one place.
2. **No business rules in UI** — All business logic lives in the backend services.
3. **No frontend-only authorization** — All access control is enforced server-side.
4. **No global mutable state** — Use dependency injection and database for state.
5. **No magic constants** — Use named constants or configuration values.
6. **No giant files** — Split large files into focused modules.
7. **No giant functions** — Keep functions focused on a single responsibility.
8. **No circular dependencies** — Maintain clear dependency direction.
9. **No silent error swallowing** — Log and handle all errors appropriately.
10. **No fake production data** — Tests use realistic but clearly test data.

## Architecture Rules

11. **Modular boundaries are strict** — Modules communicate through defined interfaces.
12. **Database transactions are explicit** — Use context managers for all write operations.
13. **Atomic inventory operations** — Inventory changes are transactional.
14. **Server-side session management** — Authentication state is managed by the backend.
15. **API versioning** — All API endpoints are versioned (e.g., `/api/v1/`).

## Security Rules

16. **Secrets in environment variables only** — Never hard-code credentials.
17. **Input validation on all endpoints** — Use Pydantic models for request validation.
18. **SQL injection prevention** — Use parameterized queries (SQLAlchemy handles this).
19. **CORS is restrictive** — Only allow known origins.
20. **Passwords are hashed** — Never store plain-text passwords.

## Development Rules

21. **Type hints everywhere** — All Python functions use type hints.
22. **Mypy strict mode** — The backend passes mypy strict checks.
23. **Tests before features** — Write tests as part of feature implementation.
24. **Documentation with code** — Update docs when changing architecture.
25. **Dependencies are justified** — No libraries added without a clear reason.
