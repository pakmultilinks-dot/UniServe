# Phase 7 — Task 6: E2E Acceptance Test Plan (isolated environment)

Executable against the **isolated** test stack — never production:
- API: `http://127.0.0.1:8001/api/v1` (isolated uvicorn, `APP_ENV=development`, separate signing key)
- DB: `uniserve_test_phase7` on `127.0.0.1:5433` (production `uniserve_prod` untouched)
- Test account (isolated DB only): `phase7.qa.132874@lgu.edu.pk`, university_id `QA-132874`,
  role `faculty`, status `active`, email_verified `true`.
- Token: login returns it **nested** at `response.tokens.access_token` (NOT top-level). Save to
  `artifacts/phase-7/token.txt`. Access token TTL is short — **re-login before any long gap**.

## Testing gotchas (learned this phase — apply to every step)

1. **Trailing slash + PowerShell.** Routes registered as `@router.get("/")` (e.g. `/orders`,
   `/cafeterias`, `/menu-search`, `/favorites`) live at the **slashed** path (`/orders/`). Requesting
   the un-slashed path returns **307**, and PowerShell's `Invoke-WebRequest` **drops the
   `Authorization` header on redirect** → spurious `401 "Invalid authorization header"`. This is a
   **client artifact, not a defect** (verified: slashed paths return 200 with the same token). Always
   probe with the exact/sashed path, or use `-SkipHttpErrorCheck` and read `StatusCode` directly.
2. Docs are disabled in this mode (`APP_DEBUG=false` → no `/openapi.json`). Route map comes from
   `apps/api/app/api/router.py`.
3. `POST` bodies: login response token path is `.tokens.access_token`; `/me` needs
   `Authorization: Bearer <token>`.

## Route map (from `apps/api/app/api/router.py`)

`/health`, `/auth`, `/users`, `/cafeterias`, `/cafeterias/{id}/menu-items`,
`/cafeterias/{id}/daily-menus`, `/cafeterias/{id}/inventory`, `/favorites`, `/menu-search`,
`/cafeterias/{id}/cart`, `/orders`, `/payments`, `/refunds`, `/notifications`, `/reports`,
`/administration`.

---

## Step checklist

| # | Step | Endpoint (method path) | Expected | Status |
|---|------|------------------------|----------|--------|
| 1 | Register | POST `/auth/register` | 201, user created (email_verified=false) | **PASS (executed)** |
| 2 | Resend OTP | POST `/auth/otp/resend` | 200; OTP logged (dev provider) | **PASS (executed)** |
| 3 | Verify OTP | POST `/auth/otp/verify` | 200 "OTP verified successfully" | **PASS (executed)** |
| 4 | Login | POST `/auth/login` | 200, `.tokens.access_token` + user | **PASS (executed)** |
| 5 | Auth'd profile | GET `/auth/me` | 200, role=faculty, email_verified=true | **PASS (executed)** |
| 6 | Notifications | GET `/notifications/` | 200 `{items:[],total:0,unread_count:0}` | **PASS (executed)** |
| 7 | List orders | GET `/orders/` | 200 `{orders:[],total:0}` | **PASS (executed)** |
| 8 | List cafeterias | GET `/cafeterias/` | 200 `{cafeterias:[],total:0}` | **PASS (executed)** |
| 9 | Menu search | GET `/menu-search/?q=…` | 200 `{items:[],total:0}` (empty DB) | **PASS (executed)** |
| 10 | Favorites | GET `/favorites/` | 200 `{favorites:[],total:0}` | **PASS (executed)** |
| 11 | RBAC control | GET `/users/me` as faculty | 403 "requires … university…" | **PASS (executed)** |
| — | Unauth control | GET `/auth/me` w/o token | 401 | **PASS (executed)** |

Steps 1–11 are **executed and passing** against `:8001` (see evidence below). They prove safe,
authenticated end-to-end access in an isolated environment — the Phase 6 blocker is removed.

## Transactional flow (requires seed data — ready to run, not yet executed)

The isolated DB is intentionally empty (0 cafeterias / 0 menu items / 0 orders), so the shopping flow
needs seed data first. To execute without touching production:

1. **Seed the isolated DB only** — run `scripts/seed_realistic_data.py` (or the API's admin/cafeteria
   endpoints) with env pointing at `uniserve_test_phase7` (`POSTGRES_DB=uniserve_test_phase7`,
   `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5433`, fresh signing key). This writes **only** the test DB.
2. Browse — GET `/cafeterias/` → items; GET `/cafeterias/{id}/menu-items/` → products.
3. Add to cart — POST `/cafeterias/{id}/cart/` (menu_item_id, quantity).
4. Checkout — POST `/orders/` (create order; idempotency key header).
5. Schedule — set scheduled slot on the order (scheduled-orders flow).
6. Admin assigns staff — admin-role account → POST `/administration/…` assign.
7. Pickup — staff/customer confirm pickup; auto-pickup/no-show expiry window.
8. Payment — POST `/payments/` (online/manual); refund via POST `/refunds/` (admin).
9. Notifications — GET `/notifications/` reflects order/payment/refund events.
10. Reports — GET `/reports/…` (role-gated) aggregates the created order.

Each step's exact request/response schema is in the module routers under `apps/api/app/modules/`.
The **same scripts** (`live_verify_*.py`, `e2e_verification.py`) already target these routes and can
be repointed at `:8001` + the test account by overriding base URL and credentials.

## Isolation guarantees (why this is safe)

- Separate DB (`uniserve_test_phase7`), separate port (`:8001`), separate signing key, dev email
  provider (OTP logged, never emailed). Production `uniserve_prod` row counts verified unchanged
  throughout (users=36, menu_items=55, orders=59, …).
- No production container, Compose file, lockfile, or dependency modified.

**Single safest next action:** seed the isolated test DB, then run steps 2–10 of the transactional
flow against `:8001` to produce a full green checkout→pickup→refund E2E — still zero production risk.