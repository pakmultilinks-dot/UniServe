# Phase 61A — Deployed API Image Synchronization and Runtime Verification

**Phase:** 61A (operational remediation of Phase 61 finding F-61-01)
**Date:** 2026-10-07
**Scope:** Rebuild the deployed API image from the current repository state, redeploy **only** the API container, prove the notifications HTTP 500 blocker is fixed, run the Phase 60/61 regression gates, verify data/git integrity, and issue one final operational decision.
**Explicitly out of scope:** Phase 62, any redesign/refactor, schema or product-data changes, DB reset, removal of `admin_announcement` rows, source changes, dependency changes, lock-file changes, destructive Docker/DB cleanup, commit/push, unrelated fixes (e.g., stopping the stale host uvicorn on port 8001), and execution of P2/P3 remediation items.

---

## 1. Original Phase 61 Blocker

Phase 61 (Post-Phase-60 Stability and Release Readiness Audit) issued decision **NOT READY** with exactly one P1 finding:

- **F-61-01 — Deployed API artifact drifts from repository source.** The deployed production API image was built on **2026-10-04T06:52:18Z**, before the `ADMIN_ANNOUNCEMENT` value was added to the `NotificationType` enum in the repository. The production PostgreSQL database (unchanged since) contains **14 `admin_announcement` notification rows** (inserted 2026-10-05..06 by host-side verification scripts). The `Notification.notification_type` column is a VARCHAR populated by a non-native SQLAlchemy `StrEnum` (`create_type=False, native_enum=False`), so the stale image passes DB schema validation but raises a Python `LookupError` when **hydrating** any row whose type is `admin_announcement`. Live effect: `GET /api/v1/notifications` as an authenticated admin → **HTTP 500** (SQLAlchemy enum `LookupError`), visible in container logs; the admin dashboard Notifications widget consequently failed.

Remediation prescribed by Phase 61: operational image rebuild + API-only redeploy + re-verification. No repository change was warranted, and none was made.

## 2. Root Cause Confirmation

Diagnosis was re-verified empirically before touching anything:

| Check | Result |
|---|---|
| Repository `apps/api/app/modules/notifications/models.py` enum | `ADMIN_ANNOUNCEMENT = "admin_announcement"` **present** (Phase 50 comment) — repository is CORRECT |
| Repository router/tests | `router.py` broadcast/list/mark endpoints present; `tests/test_notifications.py` + `tests/test_phase50_admin_notifications.py` present |
| Old image functional enum import (`docker run --rm --entrypoint python uniserve-prod-api:pre-phase61a -c "..."`) | `old_enum_count=13 has_admin_announcement=False` → hydration of `admin_announcement` rows **must** raise `LookupError` |
| New image functional enum import (same probe, current image) | `new_enum_count=15 has_admin_announcement=True` |
| DB rows (read-only psql) | 14 `admin_announcement` rows, all valid recipient user_ids, 0 orphans (11 student / 1 cafeteria_staff / 2 university_admin) |

**Root cause: deployed-artifact drift only.** The repository and tests were already correct; the 2026-10-04 image simply predates the enum addition. The mandate-preferred path (image rebuild, no source edits) was therefore the correct and only required fix. **No source, test, config, lock, or env file was modified at any point.**

## 3. Old Deployed Image Identity

| Attribute | Value |
|---|---|
| Image digest | `sha256:7114ba3c29ebc7f3efa0604da582634250bdda7b13561c7b55ae628f6747862a` |
| Short ID | `7114ba3c29eb` |
| Image created | 2026-10-04T06:52:18Z (PKT 2026-10-04 11:52:18) |
| Container | `462134406e12` (project `uniserve-prod`, compose service `api`) |
| Enum probe | 13 values, **no** `admin_announcement` |
| Post-remediation state | **Retained** as rollback tag `uniserve-prod-api:pre-phase61a` (non-destructive `docker tag`; nothing deleted) |

## 4. New Image Identity

| Attribute | Value |
|---|---|
| Image digest | `sha256:f4e14ce511aed4327e54d6869ce7ef104beb38338f9d96d0b872b3e7669ea50c` |
| Short ID | `f4e14ce511ae` |
| Image created | 2026-10-07T20:16:41Z |
| Build command | `docker compose -f docker-compose.prod.yml -f <temp override> build api` |
| Build provenance | Dockerfile unchanged (python:3.11-slim-bookworm; deps from `requirements.lock.txt` with `--no-deps` + pip check ×2; `COPY . .` last) |
| Dependency layers | **All CACHED** (apt / pip / lock COPY reused verbatim) — only the app-code COPY re-ran (≈2.3 s) ⇒ zero dependency changes |
| Functional proof | `new_enum_count=15 has_admin_announcement=True` (enum import inside the new image) |
| Serving container | `75471889f4d724f489e1bcc247e858804d7ee5a809633b605f1ccb06b6c26415` (short `75471889f4d7`), created 2026-10-07T20:16:41Z, started 2026-10-07T20:16:43Z, status **Up / healthy** |

## 5. Repository HEAD Used

| Attribute | Value |
|---|---|
| HEAD | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (branch `main`) |
| Commits made this phase | **None** (no `git add`/`commit`/`push`) |
| Source/test/config/lock/env modifications | **None** |
| Working-tree dirty count | 157 at Phase 61A start → **158 after this report**, with `PHASE_61A_DEPLOYED_API_RUNTIME_REMEDIATION.md` as the **only new untracked entry** (plus the pre-existing untracked Phase 61 audit report) |
| `git diff --stat` | Matches the pre-Phase-61 baseline (98 tracked files already dirty from prior phases; no new tracked-file edits by this phase) |
| `package-lock.json` SHA256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` — **byte-identical before and after** |
| API identity | `apps/api/pyproject.toml` `version = "0.1.0"` (prod container serves no OpenAPI schema with `APP_DEBUG=false`; identity = image digest + pyproject) |

## 6. Database State Before/After

Read-only `psql` census before redeploy and after all verification (DB `uniserve_prod` on `uniserve_postgres`, exposed at localhost:5433):

| Table / metric | Before | After | Verdict |
|---|---|---|---|
| `notifications` total | 148 | 148 | **Unchanged** |
| `notifications` where `notification_type='admin_announcement'` | **14** | **14** | **PRESERVED — none deleted or rewritten** |
| `order_created` | 49 | 49 | Unchanged |
| `order_cancelled` | 26 | 26 | Unchanged |
| `order_confirmed` | 18 | 18 | Unchanged |
| `preparation_started` | 13 | 13 | Unchanged |
| `order_ready` | 10 | 10 | Unchanged |
| `refund_requested` | 4 | 4 | Unchanged |
| `cafeteria_closed` | 3 | 3 | Unchanged |
| `order_rejected` | 3 | 3 | Unchanged |
| `order_delayed` | 3 | 3 | Unchanged |
| `payment_confirmed` | 3 | 3 | Unchanged |
| `refund_processed` | 1 | 1 | Unchanged |
| `refund_rejected` | 1 | 1 | Unchanged |
| `orders` | 52 | 52 | Unchanged |
| `payments` | 39 | 39 | Unchanged |
| `refunds` | 4 | 4 | Unchanged |
| `cafeterias` | 5 | 5 | Unchanged |
| `daily_menus` | 16 | 16 | Unchanged |
| `users` | 18 | 18 | Unchanged |
| `sessions` | 361 | **364** | +3 — auth/session side effect of mandated verification logins (permitted) |
| `security_audit_events` | 800 | **806** | +6 — audit side effect of the same logins (permitted) |
| `alembic_version` | 0013 | 0013 | **No schema changes; no migrations ran** |

No DB reset. No product-data modification. No fake production data introduced. The runtime DB password is never recorded in this report.

## 7. API Restart / Replacement Details

**Restart scope: the `uniserve_api` container only.**

- Command: `docker compose -f docker-compose.prod.yml -f <temp override> up -d --no-deps api`
- Compose log showed `Recreate` → `Recreated` → `Starting` → `Started` for the `api` service only.
- Old container `462134406e12` → new container `75471889f4d7…26415` (same service name `uniserve_api`, same project `uniserve-prod`).
- `--no-deps` guaranteed PostgreSQL was untouched: `uniserve_postgres` container ID `492b8b8a2122…` and `State.StartedAt=2026-10-07T04:23:14.719875157Z` are **byte-identical before and after** (container reports Up 16 h at capture time — untouched by this phase).
- Volumes, network, and environment preserved: container env keys read from the unchanged `docker-compose.prod.yml` + `.env.production` wiring (internal `POSTGRES_HOST=postgres`, `POSTGRES_DB=uniserve_prod`, `APP_ENV=production`, `APP_DEBUG=false` — key names verified in container inspect; **no config material changed**).
- The temporary compose override (port mappings `api 8000:8000`, `postgres 5433:5432`) exists only outside the repo (per its own comment) and was used as-is — not edited this phase.
- Unrelated containers (e.g., n8n) present in the host were **not touched**.
- Rollback preserved: old image retained at `uniserve-prod-api:pre-phase61a` (`7114ba3c29eb`). Rollback procedure if ever needed: retag/point compose at the pre-phase61a image and `up -d --no-deps api` again. No rollback was executed — none was required.
- Post-deploy liveness: `GET /api/v1/health` → **200** `{"status":"healthy","service":"uniserve-api",…}`; `GET /api/v1/health/ready` → **200** `{"status":"ready","database":"connected","schema":"present",…}`.

## 8. Original Failing Endpoint

`GET /api/v1/notifications` (list; also relevant: `GET /api/v1/notifications/unread-count`) as an authenticated university admin, against the **old** deployed image:

- Listing: **HTTP 500** — SQLAlchemy enum `LookupError` raised while hydrating `admin_announcement` rows; the error appeared in container logs. The admin dashboard Notifications widget was the user-visible casualty (Phase 61 evidence).
- The old image's enum probe (`13 values, no admin_announcement`) confirms the failure is deterministic for any row of that type — not intermittent.

## 9. Post-Remediation Response

Against the **new** image (container `75471889f4d7`), admin account (demo admin by project convention — credentials not reproduced here):

- `GET /api/v1/notifications?limit=50` → **200 OK**. Payload: `total=2`, `unread_count=2`, `items=2` — **both rows are `admin_announcement` and fully hydrated**, e.g. title `"Phase 50 E2E - Idempotency proof"`, description `"Replay-safe broadcast verification."`, `is_read=false`, complete `NotificationResponse` shape (`is_read`, `delivery_status`, `created_at`, `read_at`, …).
- `GET /api/v1/notifications/unread-count` → **200 OK** `{"unread_count":2}`.
- Container logs since restart: **no `LookupError` / enum errors** (scan of last 400 log lines clean; historical error absent after restart).
- Browser path (mandate Step 7): admin dashboard at `http://localhost:3000/dashboard` — session active, Notifications badge shows **"2"**, stat card shows **"2 Unread Notifications"**, and the Notifications widget renders **both `admin_announcement` rows live** ("Phase 50 E2E - Idempotency proof" / "Phase 50 E2E — Error state test" with timestamps). This is the exact UI path that previously failed. Screenshot captured during verification.

**Verdict: original blocker empirically FIXED — 500 → 200, rows hydrate in API and UI.**

## 10. Notification Regression Results

Live end-to-end probes (read/write where the mandate requires) plus focused test suites:

| Check | Result |
|---|---|
| Admin listing | **200**, 2× `admin_announcement` rows hydrate |
| Admin unread-count | **200**, `{"unread_count":2}` |
| `admin_announcement` visibility by role | Admin **2**; student (bilal.hussain@student…): **3** of 11 items; faculty (dr.sana.malik@…): **0 by design** (64 items: order_created 18, order_cancelled 12, order_confirmed 8, preparation_started 5, cafeteria_closed 2, order_rejected 2, order_ready 3 — no admin_announcement rows addressed to faculty) |
| Student inbox | **200**, 11 items (order_created 3, payment_confirmed 2, refund_processed 1, refund_requested 2, admin_announcement 3) |
| Mark one read `PATCH /notifications/{id}/read` | **200** `{"is_read":true,"read_at":"2026-10-07T20:19:08.316096Z"}`; unread 11 → 10 |
| Mark all read `PATCH /notifications/read-all` | **200** `{"marked_count":10}`; unread → 0 |
| Cross-user mark (admin PATCH on student's notification id) | **404 NOT_FOUND** — user scoping intact (IDOR guard works) |
| Student `POST /notifications/broadcast` | **403 AUTHORIZATION_ERROR** — university-admin-only gate intact |
| Focused suites `test_notifications.py` + `test_phase50_admin_notifications.py` | **90 passed** (22.57 s) |

## 11. Backend / Web / Mobile Regression Results

All gates run sequentially on the same host (never concurrent heavy suites — F-61-14 lesson); integration-gate env vars empty/cleared:

| Gate | Command / location | Result | Baseline match |
|---|---|---|---|
| Backend full suite | `pytest tests/ -q` from `apps/api` | **872 passed, 5 skipped** (381.90 s) | ✅ exact Phase 60/61 |
| Backend focused (notifications) | `pytest tests/test_notifications.py tests/test_phase50_admin_notifications.py -q` | **90 passed** | ✅ |
| Web TypeScript | `npx tsc --noEmit` (`apps/web`) | **0 errors** (exit 0) | ✅ |
| Web unit tests | `npx vitest run` (`apps/web`) | **40/40 passed, 8 files** (exit 0) | ✅ |
| Web ESLint | `npx eslint . --ext .ts,.tsx` (`apps/web`) | **0 errors / 95 warnings** (exit 0) | ✅ warning baseline unchanged |
| Mobile TypeScript | `npx tsc --noEmit` (`apps/mobile`) | **0 errors** (exit 0) | ✅ |
| Mobile unit tests | `npx jest --runInBand` (`apps/mobile`) | **34/34 passed, 6 suites** (51.5 s, exit 0) | ✅ |
| Mobile ESLint | `npx eslint src --ext .ts,.tsx` (`apps/mobile`) | **0 errors / 61 warnings** (exit 0) | ✅ warning baseline unchanged |

Known lint warning counts were **not** turned into cleanup work, per mandate. `ruff` was not invoked this phase (and plain `ruff check app` remains forbidden by repo convention).

## 12. Data-Integrity Verification

- **Product data unchanged:** every census in §6 is identical before/after except the mandate-permitted auth side effects (`sessions` 361→364, `security_audit_events` 800→806, caused solely by the mandated Step 8 verification logins).
- **`admin_announcement` rows preserved:** all **14** rows intact — none deleted, rewritten, or hidden to "fix" the error (explicitly forbidden; explicitly verified).
- **Read-receipt transitions:** the test student's 11 rows showed `is_read` transitions during the mandated Step 8 mark-one/mark-all verification — this is the application's normal read-receipt function being exercised, with no deletions and no data masking.
- **Schema:** `alembic_version` stays `0013`; no migrations executed; no DDL.
- **No reset, no seed, no fake data.** Demo credentials referenced by convention only.
- **Secrets:** the runtime DB password never appears in this report, in logs captured for it, or in any user-facing text this phase.

## 13. Git-Integrity Verification

| Check | Expected | Actual |
|---|---|---|
| `git rev-parse HEAD` | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` | ✅ identical — **no commits, no push** |
| `git status --short` count | 157 → 158 with this report as sole new entry | ✅ 158; new `?? PHASE_61A_DEPLOYED_API_RUNTIME_REMEDIATION.md` |
| `git diff --stat` | No new tracked modifications vs pre-Phase-61 baseline | ✅ unchanged (98 files dirty from prior phases only) |
| `package-lock.json` SHA256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` | ✅ byte-identical |
| New dependencies | None | ✅ none added; Dockerfile/requirements untouched (dependency layers cached) |

No unexpected source changes appeared — no STOP condition triggered on this axis.

## 14. Remaining Known Limitations

Carried over **unchanged** from the Phase 61 audit — all P2/P3, none blocking demo preparation, none executed or modified this phase (outside mandate):

| ID | Limitation | Status |
|---|---|---|
| F-61-02 | No automated image-vs-DB drift gate (a future deploy could reintroduce stale-artifact drift; recommend a post-deploy enum smoke check in the deploy pipeline) | Open (process gap) |
| F-61-03 | Dual-React workspace (root React 19.2.3 vs `apps/web` React 18.3.1 + next 14.2.35 — never hoist next) blocks the **static-web build/deploy path only**; dev server path fine | Open (deploy-path only) |
| F-61-04 | Stale pending payments in prod DB (19 → 27 since earlier phases) — reconcile job not executed | Open (P3) |
| F-61-05 | `fixture_hygiene` R6 census pattern mismatch in test infra | Open (P3) |
| F-61-06 | E2E test cafeteria ("Phase 56 E2E Cafeteria") active in prod DB | Open (P3, demo-visible) |
| F-61-07 | Duplicate daily menus in DB | Open (P3) |
| F-61-08 | Three itemless orders in DB | Open (P3) |
| F-61-09 | User sessions un-reaped (count grows with use) | Open (P3) |
| F-61-10 | Dietary fields 3/35 populated, allergens 2/35 — demo content thinness | Open (P3) |
| F-61-11 | Stale host uvicorn pid 4772 on port 8001 (host-side residue; container API on 8000 unaffected) | Open (P3) |
| F-61-12 | Repo `apps/api/.env` stale vs live env (container reads `.env.production`; repo file not modified) | Open (P3) |
| F-61-13 | Lint warning baselines (95 web / 61 mobile warnings; 0 errors) | Baseline accepted |
| F-61-14 | Mobile cold-start test flake under concurrency — this phase ran all suites **sequentially**, all green | Mitigated by practice |
| F-61-15 | Compose dev defaults diverge from prod override (ports/host) | Open (P3) |
| F-61-16 | Residue test/demo accounts and E2E entities in prod DB | Open (P3) |

**This phase resolved only F-61-01.** All other findings remain exactly as documented in the Phase 61 audit.

## 15. Final Operational Decision

**BLOCKER RESOLVED — READY FOR DEMO PREPARATION**

Justification:

1. The single P1 blocker (F-61-01) was remediated **operationally** — image rebuilt from correct repository HEAD, API container alone redeployed — with **zero** source/test/config/lock/env changes and **zero** product-data changes.
2. The fix is empirically proven at artifact, API, and UI levels: old image enum 13 values (no `admin_announcement`) → new image 15 values (has it); `GET /api/v1/notifications` 500 → **200** with both `admin_announcement` rows hydrating; dashboard Notifications widget renders live rows; no `LookupError` in logs; health/ready 200.
3. All **14** existing `admin_announcement` records preserved (none deleted/rewritten).
4. All regression gates green at exact Phase 60/61 baselines: backend **872 passed / 5 skipped** · web tsc **0** / Vitest **40/40** / ESLint **0 errors (95 warnings)** · mobile tsc **0** / Jest **34/34** / ESLint **0 errors (61 warnings)** · focused notifications **90 passed**.
5. Git integrity: HEAD unchanged, no commits, lock file byte-identical; only new artifact is this report. Database product data unchanged (auth side effects documented). API confirmed running from the intended new image (`f4e14ce511ae…`); PostgreSQL container untouched.
6. Rollback remains available (`uniserve-prod-api:pre-phase61a`) without any destructive action having been taken.

**Next phase: demo preparation** (rehearsal, credential/account hygiene decisions, deployment planning for the known P2/P3 items). Phase 62 has **not** been started and must not be inferred from this report.

---

*Phase 61A — investigation and remediation evidence only. No commit, no push, no schema change, no product-data change, no dependency change, no secret material.*
