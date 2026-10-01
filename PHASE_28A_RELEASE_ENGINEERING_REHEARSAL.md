# Phase 28A — Release Engineering & Production Rehearsal Report

**Status:** COMPLETE — rehearsal passed with 5 genuine fixes (all regression-covered)
**Starting commit:** `ae6fc6a` (`fix: resolve non-payment release readiness issues`)
**Rehearsal environment:** local Docker (Docker 29.8.0, Compose v5.5.1), Windows host, no VPS/DNS/HTTPS/domain changes
**Labels used:** `PASS` (verified working as-is) · `FIXED` (genuine issue found and remediated in this phase) · `OBSERVED` (noted, no change — out of scope or safe by design) · `BLOCKED EXTERNALLY` (cannot be resolved inside this repository)

> **Headline:** the production topology (Caddy → API → PostgreSQL 16) builds, migrates from an empty database, starts, backs up, survives total schema loss, and restores — all rehearsed locally. Five genuine release-engineering defects were found and fixed. **Full production readiness is NOT claimed:** online payments remain fail-closed and JazzCash integration is blocked externally.

---

## 1. Scope, starting state & constraints — PASS

- Starting tree clean at `ae6fc6a`; backend 597 tests, E2E 31/31, web tsc/build, mobile type-check all green from Phase 27.
- Constraints honored throughout: no JazzCash implementation, no payment credentials, no payment signing/webhook changes, no production online payments, no VPS deployment, no DNS/HTTPS/domain configuration changes, no developer-database destruction (dev volume `uniserve_postgres_data` preserved end-to-end), no fake or real secrets committed, no test weakening.
- Payment-provider code was **inspected only** (section 11) to confirm it remains safely fail-closed.
- Rehearsal secrets (`.env.production`, git-ignored) were generated locally, used only inside the disposable local stack, and are **not** included in any commit or document.

## 2. Environment & configuration audit — PASS

- `.env.production` is git-ignored (verified with `git check-ignore`); `.env.production.example` ships payment variables commented out with fail-closed notes; no real secrets exist in the repository.
- Mobile `app.json`/`eas.json`/`src/config.ts` and web `next.config.js`/`lib/api.ts` expose only public endpoint URLs — no backend secrets in client bundles.
- API `Dockerfile` (python:3.11-slim) installs the package non-editably; container healthcheck uses in-container `httpx` against `/api/v1/health`.
- `alembic.ini` carries a hardcoded dev URL but `migrations/env.py` overrides it with `settings.DATABASE_URL` — production-safe. `OBSERVED` (section 13).

## 3. Production build rehearsal — PASS

- `docker compose -f docker-compose.prod.yml build api` succeeded (image built; rebuilt again after the Phase 28A fixes — `BUILD_EXIT=0` both times).
- Web static export rebuilt after the section-9 fix (`npx next build`, exit 0) into `apps/web/out` (git-ignored).

## 4. Database migration rehearsal — PASS

- Fresh, empty production database (isolated volume, section 12): `alembic upgrade head` applied 10 migrations `0000 → 0009` with zero errors.
- `alembic current` → `0009 (head)` inside the production API container.
- Confirmed again after the backup/restore cycle (section 6).

## 5. Production stack startup & verification — PASS

- `up -d` (production compose): `uniserve_postgres` healthy → `uniserve_api` healthy (healthcheck green) → `uniserve_caddy` up.
- In-container verification: `GET /api/v1/health` → `200 healthy`; `GET /api/v1/health/ready` → `200 ready, database connected` (post-fix: also `schema: present`).
- Host-port audit: `docker port uniserve_postgres` → **empty** (database not exposed); API not published; only Caddy on 80/443.

## 6. Backup & restore rehearsal — PASS + FIXED

- `scripts/backup_database.sh` produced an 88 KB custom-format dump (`backups/uniserve_<ts>.pgdump`, git-ignored) with 30-day retention logic.
- **Disaster simulation:** `DROP SCHEMA public CASCADE` destroyed all 40 schema objects (tables, types, `alembic_version`, extensions) while PostgreSQL stayed running.
- **Gap found (`FIXED`):** no restore procedure or script existed — backup-only posture. Created `scripts/restore_database.sh` (`pg_restore --clean --if-exists --no-owner --no-acl`, with container/usage guards and documented stop-API-first requirement).
- **Restore verified:** API stopped → restore → `alembic current` = `0009 (head)` → pre-backup marker row `pre-backup-state` survived → API restarted → readiness `200 ready`. Full backup → destroy → restore → verify cycle passed on the first run.

## 7. Failure & recovery rehearsal — PASS + FIXED

- **API container restart:** `restart api` → healthy within seconds, readiness recovered (`200 ready`). Restart path verified.
- **Database loss:** during the section-6 disaster simulation, readiness still returned `ready` on a wiped schema — `SELECT 1` succeeds against an empty database. **Genuine observability gap (`FIXED`)**: readiness now also probes the core `users` table and reports `{"status":"degraded","schema":"missing"}` when the schema is gone (section 15).
- **Invalid/misconfigured environment (fail-closed verified on live images):**
  - `APP_ENV=production` + default secrets → startup **rejected** (`Secret key must be changed for production`) — pre-existing guard, works.
  - `APP_ENV=production` + custom secrets + `APP_DEBUG=true` → **accepted** on the pre-fix image — **genuine gap (`FIXED`)**: the rebuilt image now rejects it (`APP_DEBUG must be false when APP_ENV=production`), verified live post-fix.
  - Valid production config → constructs cleanly; container boots healthy.
- **Auth layer under failure conditions:** unauthenticated payment-initiation call → `401` (no stack traces, no schema leakage).

## 8. Observability & health-check audit — PASS + FIXED

- Structlog JSON confirmed active in the API container (`LOG_FORMAT=json`); Caddy access logs on stdout with JSON logs; container healthchecks wired for API (httpx) and PostgreSQL (`pg_isready`).
- **Log secret scan:** API, PostgreSQL, and Caddy container logs scanned for `password/secret/token/api_key/bearer` patterns → **0 matches**. No credential leakage.
- Readiness semantics upgraded (`FIXED`, section 7) with regression tests (section 15); liveness/`/health` semantics unchanged (compose healthcheck unaffected).

## 9. Static assets & reverse-proxy verification — PASS + FIXED + OBSERVED

- **Genuine defect (`FIXED`):** the exported `apps/web/out/index.html` was a Next.js error shell (`id="__next_error__"`) — the home page used `redirect()` from `next/navigation`, which throws during `output: "export"` prerendering and ships a broken landing page in production. All other pages exported correctly. Replaced with a static-export-safe client redirect (visible fallback link included). Re-export verified: `__next_error__` count `0` on host **and** inside the Caddy container mount (bind mount picks the fixed build up live).
- Caddy Host-header routing verified over HTTP: `Host: api.example.com` → `308` redirect to the HTTPS API origin (automatic-HTTPS behavior correct).
- Static assets confirmed mounted read-only in Caddy (`/srv` = 19 export items).
- `OBSERVED`: end-to-end HTTPS could not complete locally — Caddy attempted real Let's Encrypt issuance for the placeholder `example.com` domains and was refused by ACME policy (`rejectedIdentifier`). This is expected in a local rehearsal; configuring real certificates/domains is explicitly out of phase scope. On production with real domains, Caddy's automatic issuance applies. The Caddyfile was **not** modified.

## 10. Web & mobile production configuration audit — PASS

- Web: `output: "export"` (static hosting behind Caddy); production rewrites disabled; `NEXT_PUBLIC_API_URL` defaults to localhost only as a dev fallback; export contains no secrets.
- Mobile: `eas.json` channels (development/staging/production) select endpoint via `Constants.expoConfig.extra.eas.channel`; production maps to `api.uniserve.app`; no secrets in `app.json` or bundled config.

## 11. Payment-provider safety (inspect-only) — PASS + BLOCKED EXTERNALLY

- Live inspection inside the production container: `PAYMENT_PROVIDER=test`, provider instance `TestPaymentProvider`, blank credentials, and the production guard evaluated `guard_triggers_503 = True` (initiation would raise `ServiceUnavailableError` → 503).
- Payment code was not modified. No credentials were added anywhere. The fail-closed guard remains exactly as audited in Phase 27.
- `BLOCKED EXTERNALLY`: JazzCash (merchant onboarding, credentials, signing/webhook contract) remains unresolved. **Production online payments stay disabled; full production readiness is not claimed.**

## 12. Container, volume & secret isolation — FIXED + OBSERVED

- **Genuine hazard (`FIXED`):** dev and prod compose shared the default project name, so the production PostgreSQL silently mounted the **development** volume (`uniserve_postgres_data`) — the first migration attempt failed with `password authentication for user "uniserve"` because the container held dev credentials while the API used production ones. On a machine that ever ran the dev stack, production would silently reuse the developer database. Fixed by pinning the production project name (`name: uniserve-prod` in `docker-compose.prod.yml`) → production volume `uniserve-prod_postgres_data`, fully isolated. Dev volume preserved untouched (verified present after every prod operation).
- `OBSERVED`: fixed container names (`uniserve_postgres` etc.) still collide if both stacks run at once — fails **loudly** on `up` (safe), documented in the runbook ("stop the dev stack first"). Not changed: scripts and docs reference these names; renaming is not required for correctness.
- No host port on API or PostgreSQL verified at every stage (section 5).

## 13. Reproducibility & documentation — PASS + OBSERVED

- `PRODUCTION_RUNBOOK.md` created: architecture, prerequisites, first deployment, migrations, backup, restore (rehearsed procedure), monitoring semantics, failure playbook, security posture, and the JazzCash external blocker — every procedure cross-checked against what was actually executed in this rehearsal.
- `OBSERVED` (documented, not changed): `alembic.ini` hardcodes a dev URL that `migrations/env.py` overrides at runtime (production-safe); Windows Git Bash rewrites POSIX paths passed to `docker exec`, so backup/restore scripts need `MSYS2_ARG_CONV_EXCL='*'` on Windows (irrelevant on Linux servers — noted in the runbook); the dev compose file carries an obsolete `version:` attribute (warning-only, dev-only).

## 14. Test validation summary — PASS

| Suite | Result |
|---|---|
| Backend pytest (full) | **608 passed** (597 baseline + 11 new regression tests), 0 failed |
| Targeted new tests | 23/23 (health + config guards + payment config) |
| E2E (`phase19_e2e_test.py`) | **31/31**, 100% |
| Web `tsc --noEmit` | exit 0 |
| Web `next build` (static export) | exit 0, fixed `index.html` verified in export |
| Mobile `type-check` | exit 0 |
| `git diff --check` | clean |

No existing test was modified except `test_health.py`, where existing cases were **extended** (not weakened) — liveness assertions unchanged; readiness assertions added.

## 15. Genuine fixes & regression coverage — FIXED

1. **`docker-compose.prod.yml` — pinned project name (`name: uniserve-prod`).** Prevents production from ever mounting the dev database volume (section 12). Verified: isolated volume created, dev volume untouched.
2. **`apps/api/app/core/config.py` — `APP_DEBUG` production guard.** `model_validator` rejects `APP_DEBUG=true` when `APP_ENV=production` (mirrors `reject_default_secrets`): misconfiguration now fails at boot instead of exposing `/api/docs`, `/api/redoc`, `/api/openapi.json`. Verified live on the rebuilt image (CASE2 post-fix rejected). Covered by `tests/test_config_production_guards.py` (7 tests, incl. locked-in regressions for the pre-existing secret guard and payment fail-closed config).
3. **`scripts/restore_database.sh` — restore procedure (new).** Closes the backup-without-restore gap; rehearsed end-to-end with data-survival verification (section 6).
4. **`apps/api/app/api/health.py` — schema-aware readiness.** Readiness now probes a core application table (`users`, present under both migrations and `create_all`) and reports `degraded` + `schema: missing` on a wiped schema — the exact disaster state observed live in rehearsal. Covered in `tests/test_health.py` (ready/degraded/disconnected cases, +4 tests).
5. **`apps/web/src/app/page.tsx` — static-export-safe home redirect.** Fixes the broken production landing page (`__next_error__` error shell) without changing routing behavior; verified in the rebuilt export and via web build/tsc.

## 16. Remaining limitations & external blockers — BLOCKED EXTERNALLY

- **JazzCash: BLOCKED EXTERNALLY.** No credentials, merchant onboarding, or confirmed signing/webhook contract. Online payments remain fail-closed (503) by design. **Full production readiness is not claimed** until a real provider is integrated and audited in a dedicated phase (after external access is granted). "STOP after Phase 28A" was honored — no provider work was attempted.
- Domain/DNS/TLS issuance for the production hosts is environment-specific and out of phase scope (local HTTPS rehearsal limited to HTTP routing + in-network verification, section 9).
- Backups produced during rehearsal are local and disposable; production backups must be shipped off-server per the runbook (operational practice, not a code issue).
- The production container-name collision with dev (loud-failure behavior) remains by design; resolved operationally via the runbook, not by renaming containers.
