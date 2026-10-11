# Phase 50 — Admin Notifications & Broadcast

**Date:** 2026-10-05
**Branch:** `main`
**HEAD (before == after):** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee`
**Deployment:** None. No commit, no push, no new branch, no lockfile/dependency changes.

---

## 1. Objective

Implement the next major Admin Console capability: allow an authorized University Admin to compose and **send a real in-app notification/broadcast** to supported audiences through the **existing UniServe notification infrastructure**, with audience targeting, content validation, a review/confirmation step, duplicate-submission protection, real success/error states, and visibility in the existing notification center — without introducing push providers, email/SMS channels, or unrelated refactors.

---

## 2. Architecture Discovered (before any source changes)

| Area | Finding |
|---|---|
| Notification model | `apps/api/app/modules/notifications/models.py` — `Notification` table with `user_id`, `notification_type`, `title`, `body`, `cafeteria_id`, `reference_type`, `reference_id`, `source_event_type`, `source_event_id`, `is_read`, `read_at`, `delivery_status`. |
| DeliveryStatus | Enum docstring marks **push delivery as future work** ("Future: Push delivery via FCM/APNs"). All rows stay `PENDING`. No delivery pipeline exists. |
| NotificationService | Creates rows via a single internal `_create_notification`; used by order workflows (order_created, order_confirmed, order_cancelled, order_ready, etc.). |
| API surface | `GET /api/v1/notifications`, `GET /api/v1/notifications/unread-count`, `PATCH /api/v1/notifications/{id}/read`, `PATCH /api/v1/notifications/read-all`, mounted at `/api/v1/notifications`. |
| Web UI | `apps/web/src/app/dashboard/notifications/page.tsx` — the existing notification center (list, unread filter, mark read, mark all read, per-type icons with a safe generic fallback). |
| Mobile UI | **No notification screen exists.** The home bell is a decorative `Pressable` with **no `onPress`**. `apps/mobile/src/services/data.ts` defines `getNotifications`/`getUnreadNotificationCount` client functions against the same endpoints, but **no mobile screen consumes them**. |
| Push infra | **None.** No device-token model, no FCM/APNs imports, no push/email/SMS provider code anywhere in `apps/api`. |
| Authorization | `RequireRole` dependency + role enum; `university_admin` is the admin role. Existing exception mapping: NotFound→404, AlreadyExists→409, ValidationError→400, AuthorizationError→403, AuthenticationError→401, pydantic Field violations→422. |

**Conclusion (Channel):** the system supports **in-app notifications only**. Phase 50 reuses this infra end-to-end and does **not** implement or claim push delivery.

---

## 3. Supported Channels

- **A. In-app notifications only** — confirmed by discovery and re-confirmed at report time (see §16).

## 4. Supported Audiences

Seven targeting audiences, all resolved server-side against **active** users (`status = ACTIVE AND deleted_at IS NULL`):

| Audience value | Meaning |
|---|---|
| `all_users` | Every active user, regardless of role. |
| `students` | Active users with role `STUDENT`. |
| `faculty` | Active users with role `FACULTY`. |
| `cafeteria_staff` | Active users with role `CAFETERIA_STAFF`. |
| `cafeteria_managers` | Active users with role `CAFETERIA_MANAGER`. |
| `university_admins` | Active users with role `UNIVERSITY_ADMIN`. |
| `cafeteria` | Active users with a `CafeteriaAssignment` for the given `cafeteria_id` (staff or manager assigned to that cafeteria). Requires `cafeteria_id`. |

`cafeteria_id` is **required if and only if** `audience = "cafeteria"` and **rejected** for every other audience. Verified live audience counts before sending: students = 3, all_users = 8 (active only).

---

## 5. Files Changed

**Backend (apps/api):**
- `app/modules/notifications/models.py` — `NotificationType.ADMIN_ANNOUNCEMENT = "admin_announcement"`; new `AdminBroadcast` model.
- `app/modules/notifications/schemas.py` — `BroadcastAudience`, `BroadcastCreateRequest`, `BroadcastResponse`, `BroadcastListResponse`, `BroadcastAudienceCountResponse`.
- `app/modules/notifications/service.py` — new `BroadcastService` (audience resolution, counting, transactional creation, idempotent replay, history listing). Existing `NotificationService` untouched.
- `app/modules/notifications/router.py` — 3 admin-only endpoints (`POST /broadcast`, `GET /broadcasts`, `GET /broadcasts/audience-count`). Existing endpoints untouched.
- `migrations/versions/0012_admin_broadcasts.py` — **new** migration creating `admin_broadcasts` + indexes; does not touch `notifications`.
- `migrations/env.py` — imports `AdminBroadcast` for autogenerate metadata.
- `tests/test_phase50_admin_notifications.py` — **new**, 26 tests.

**Shared + Web:**
- `packages/shared-types/src/index.ts` — `admin_announcement` added to `NotificationType` union; ADMIN BROADCAST types added; dist rebuilt (tsc, clean).
- `apps/web/src/lib/api.ts` — `broadcastNotification`, `getBroadcastAudienceCount`, `getAdminBroadcasts` wrappers.
- `apps/web/src/components/Sidebar.tsx` — "Broadcasts" nav entry (`/dashboard/admin/broadcasts`, university_admin only, megaphone icon).
- `apps/web/src/app/dashboard/notifications/page.tsx` — `admin_announcement` megaphone icon in `TYPE_ICONS` (existing generic fallback kept).
- `apps/web/src/app/dashboard/admin/broadcasts/` — **new** admin broadcast page (compose → review → send → history).

**Docs:** `PHASE_50_ADMIN_NOTIFICATIONS_AND_BROADCAST.md` (this report).

**Not changed:** mobile app (no notification UI exists to change — see §8), Notification model/behavior, order workflows, refunds, settings, profile, reports, cafeteria/menu management, member management, deployment configs, dependencies, lockfile.

---

## 6. Backend Implementation

**Model — `AdminBroadcast` (`admin_broadcasts`):** `id` (String36 pk, explicit UUID), `created_by_id` (FK users, SET NULL), `created_by_name` (snapshot, NOT NULL), `title` (255), `message` (Text), `audience` (50), `cafeteria_id` (FK cafeterias, SET NULL, nullable), `recipient_count` (Integer NOT NULL), `idempotency_key` (String255 NOT NULL, **unique index** `idx_admin_broadcast_idempotency_key`), `created_at` (tz, default now, index).

**`BroadcastService`:**
- `_resolve_recipient_ids(audience, cafeteria_id)` — lazy imports; base query active users; role map per audience; `cafeteria` joins `CafeteriaAssignment`; unknown cafeteria → `NotFoundException`; `cafeteria` without `cafeteria_id` → `ValidationError`. Recipients ordered by `User.id` for determinism.
- `count_audience(...)` — preview counts using the same resolution.
- `create_broadcast(...)` — strips title/message (empty → `ValidationError`); validates `cafeteria_id` rule; checks idempotency replay → returns `(existing, True)`; resolves recipients (empty → `ValidationError "…has no active recipients — nothing sent"`); **generates the broadcast UUID explicitly up front** (column `default=` is flush-time — reading `id` pre-flush returns None); adds one `AdminBroadcast`; creates exactly **one `Notification` per recipient** via the existing `NotificationService._create_notification` with `notification_type=ADMIN_ANNOUNCEMENT`, `reference_type="broadcast"`, `reference_id=<broadcast id>`, `source_event_type="admin_broadcast"`, `source_event_id=None` (required because of the global unique `(source_event_type, source_event_id)` index); single `flush()` — transactionally safe, no duplicate recipient rows per request.
- `list_broadcasts(limit, offset)` — count + newest-first history.

**Router:** `POST /broadcast` → 201 (`BroadcastResponse`, `duplicate=false`) or **200 when replaying an existing idempotency key** (`duplicate=true`); `GET /broadcasts` → `BroadcastListResponse` (limit 1–50, offset); `GET /broadcasts/audience-count?audience=…&cafeteria_id=…` → count preview. All three require `RequireRole(Role.UNIVERSITY_ADMIN)`.

**Migration 0012:** upgrade creates `admin_broadcasts` (FK users/cafeterias SET NULL, `created_at server_default now()`) + the two indexes; downgrade drops indexes then table. Applied **only to the local dev Postgres container** (`0011→0012`, exit 0). `main.py` does not auto-run migrations.

---

## 7. Frontend Implementation

**`/dashboard/admin/broadcasts` (new page):**
- **Compose:** title (≤255 with live counter), message (≤5000 with counter), audience select (7 options), conditional cafeteria select (loaded via `getCafeterias` only when audience = "cafeteria", with retry state). Client-side validation mirrors the backend (empty title/message, >length, cafeteria without selection) but the backend stays authoritative.
- **Review modal (confirmation):** shows exact title, message, audience label, cafeteria (if any), and a **live recipient count** fetched from `GET /broadcasts/audience-count`. Send button is **disabled** while: submitting, count loading, count unavailable, or count = 0 ("No active recipients — the server will reject this send."). Cancel closes without sending.
- **Safe send:** `if (sending) return` double-click guard; fresh idempotency key per attempt unless a previous attempt failed (key kept for retry); form values trimmed.
- **Success state (only after backend confirms):** green panel — "Broadcast sent", delivered-to-recipient line, timestamp, and the explicit note **"in-app notifications only — no push/SMS/email channel was used."**; toast with recipient count; history refreshed; form reset.
- **Error states:** inline `formError` alert (role="alert"); preview count error + Retry; send failure keeps the modal open with a red **"Broadcast not sent"** banner + message and a **"Try again"** button (same key); history `LoadErrorState`; cafeteria options error + Retry; 403 → amber "Admin access required" panel + redirect (backend still enforces 403 independently).
- **History:** last 20 broadcasts — title, "Duplicate replay" badge when `duplicate=true`, message (2-line clamp), audience label, cafeteria name, recipient count, datetime, Refresh button; loading skeleton; `EmptyState` when none.
- **Non-admin:** page body replaced with an "Admin access required" EmptyState + `router.push("/dashboard")` — UI hiding is **not** the security boundary; the API rejects non-admins regardless (§9).

**Existing notification center:** only additive change is the `admin_announcement` megaphone icon; read/unread logic untouched. **Sidebar:** additive "Broadcasts" entry.

---

## 8. Mobile Verification

- The mobile app has **no notification screen**: the home bell is a `Pressable` with **no `onPress`** handler; nothing renders notification lists.
- `apps/mobile/src/services/data.ts` already exposes `getNotifications` / `getUnreadNotificationCount` against the **same endpoints** the broadcast rows are written to — so any future mobile consumer will receive broadcast rows with no backend change.
- Student-recipient visibility was therefore verified at the **API level** only (ayesha.khan's `GET /notifications` contains her `admin_announcement` row). Web dashboard is not reachable for students (RoleGuard → `/mobile-required`).
- **No mobile code was changed in Phase 50** (out of scope). **Push was not tested — push does not exist.**

---

## 9. Authorization Behavior

| Caller | `POST /broadcast` | `GET /broadcasts` | `GET /broadcasts/audience-count` |
|---|---|---|---|
| Unauthenticated | 401 (unit test) | 401 (unit test) | 401 (unit test) |
| Student | 403, **no rows created** (unit test) | 403 (unit test) | 403 (unit test) |
| Cafeteria manager | 403, **no rows created** (unit test) | 403 (unit test) | 403 (unit test) |
| Cafeteria staff | 403, **no rows created** (unit + **live E2E H**) | 403 (unit + live) | 403 (unit + live) |
| University admin | 201 (or 200 duplicate replay) | 200 | 200 |

Live E2E H with `ahmed.raza` (cafeteria_staff): POST → 403, GET history → 403, GET audience-count → 403, and the broadcast total stayed unchanged (no rows created). Rejected attempts never create `AdminBroadcast` or `Notification` rows.

---

## 10. Validation Rules (backend authoritative; frontend mirrors them)

| Condition | Backend result |
|---|---|
| Title empty / whitespace-only (after strip) | 400 (`ValidationError`) |
| Title missing or `""` (pydantic `min_length=1`) | 422 |
| Title > 255 / message > 5000 chars | 422 |
| Message empty / whitespace-only | 400; missing/"" → 422 |
| Unknown audience value | 422 (enum violation) |
| `cafeteria_id` supplied with a non-cafeteria audience | 400 |
| `audience = cafeteria` without `cafeteria_id` | 400 |
| Unknown `cafeteria_id` (valid UUID, not found) | 404 |
| Malformed `cafeteria_id` (`"not-a-valid-id"`) | 404 |
| Audience resolves to zero active recipients | 400 — `"Audience 'X' has no active recipients — nothing sent"` |
| `idempotency_key` missing / empty | 422 |

All invalid-request probes left the broadcast history empty (history stayed 0 through the whole validation battery).

---

## 11. Test Results

- **Phase 50 suite:** `apps/api/tests/test_phase50_admin_notifications.py` — **26 / 26 passed** (categories: Authorization, Validation, Targeting, Creation & persistence, Duplicate safety, Existing behavior — recipient center shows `admin_announcement` unread with correct unread-count; PATCH read sets `read_at`; mark-all-read marks all broadcast rows; admin history endpoint returns broadcasts).
- **Full backend suite:** **769 passed** (743 baseline + 26 new) — **zero regressions**; existing tests not weakened.
- Notable coverage details: per-recipient rows carry `reference_type="broadcast"`, `reference_id=<broadcast.id>`, `source_event_type="admin_broadcast"`, `source_event_id=None`, `is_read=False`, `delivery_status=PENDING`; multiple recipients each receive exactly one row; same idempotency key twice → same broadcast id, `duplicate=True`, exactly one recipient row; distinct keys → distinct broadcasts; cafeteria audience reaches only the assigned active staff of that cafeteria (model requires `CafeteriaAssignment.role` NOT NULL — tests pass it explicitly).

## 12. Manual E2E Results (live API :8001 + web UI :3000 + dev Postgres)

| # | Scenario | Result |
|---|---|---|
| A | Admin opens Broadcasts via Sidebar nav | **PASS** — page loads; 7 audiences; empty history "0 most recent". |
| B | Validation (frontend + backend independently) | **PASS** — UI: empty title → "Title is required."; cafeteria without selection → "Choose a cafeteria before reviewing this broadcast."; nothing sent. Backend: 422/400/404 as per §10, history unchanged. |
| C | Review/preview | **PASS** — modal shows exact title, message, "Students", live "3 recipients". |
| D | Cancel confirmation | **PASS** — modal closed, form data retained, nothing created. |
| E | Real sends | **PASS** — students "Phase 50 E2E — Library hours change" → success panel "3 recipients (Students) … in-app notifications only — no push/SMS/email channel was used.", toast, history "1 most recent"; cafeteria_staff "Phase 50 E2E — Staff notice" → "1 recipient (Cafeteria staff)", history "2 most recent". |
| F | Recipient verification (API + web UI) | **PASS** — API: `ahmed.raza` (staff) has 1 unread `admin_announcement` "Phase 50 E2E — Staff notice"; `ayesha.khan` (student) has "Phase 50 E2E — Library hours change"; 2 `AdminBroadcast` rows persisted (`7a53a190…` students count=3, `af5831e0…` cafeteria_staff count=1), `duplicate=False`. Web UI as ahmed: dashboard "1 Unread Notifications" + bell badge; `/dashboard/notifications` shows the broadcast unread with the new megaphone icon. Student UI path not reachable (documented in §8). |
| G | Read state | **PASS** — clicking the row → UI "0 unread notifications", bell cleared; API: `is_read=true`, `read_at` set, `/unread-count` → 0. Existing read/unread behavior intact with broadcast rows. |
| H | Non-admin security | **PASS** — live 403 on all three endpoints for cafeteria_staff; broadcast total unchanged; unit tests cover 401 + role rejections + no-row guarantees. |
| I | Error state + safe retry | **PASS** — routed POST aborted (`net::ERR_FAILED`) → modal "Broadcast not sent / Unable to reach the server. Check your connection and try again." + "Try again", **no success panel, no toast**, history unchanged; unroute → "Try again" (same idempotency key) → real success "delivered to 1 recipient (University admins)", history "3 most recent". **Live idempotency proof:** fresh key → 201 `duplicate=false` (`a7224c81…`); exact replay → 200 `duplicate=true`, same id, **no new broadcast row**. |

## 13. Data Integrity (live dev DB, before → after)

| Table | Before | After | Verdict |
|---|---|---|---|
| users | 15 | 15 | unchanged |
| orders | 47 | 47 | unchanged |
| cafeterias | 3 | 3 | unchanged |
| menu_items | 32 | 32 | unchanged |
| order_items | 46 | 46 | unchanged |
| refunds | 0 | 0 | unchanged |
| menu image URLs | 27 | 27 | unchanged |
| **notifications** | 114 | **120** | +6 — exactly the 6 E2E `admin_announcement` rows (3 students + 1 staff + 1 error-state + 1 idempotency-proof); all other type counts unchanged (order_created 44, order_confirmed 18, order_cancelled 25, order_delayed 3, order_ready 10, order_rejected 1, preparation_started 13 = the original 114) |
| **admin_broadcasts** | 0 | **4** | new table, Phase 50 E2E records only |
| notifications `is_read=true` | 0 | 1 | only ahmed's staff notice, flipped by E2E G; `false` = 119 (114 original + 5 new unread) |

**Core business data is byte-for-byte untouched.** Only notifications + admin_broadcasts grew, exactly matching the Phase 50 E2E activity.

## 14. Build / Type-Check / Lint

- **Type-check:** `npm run type-check:web` — **clean**. Shared-types dist rebuilt via tsc — clean.
- **Lint:** eslint on the 4 changed/new web files — **exit 0** (pre-existing warnings only: TS-version notice, pages-directory notice).
- **Build:** `npm run build --workspace=apps/web` — exit 1, **identical to the recorded baseline failure** (dual React 19 root / React 18 web dependency mismatch; styled-jsx crash prerendering stock `/404`,`/500`; lockfile-patch TypeError). **Pre-existing, not caused by Phase 50, intentionally not fixed** (per prior-phase constraint).

## 15. Known Limitations

1. **Idempotency** is application-level replay detection backed by the **unique DB index** `idx_admin_broadcast_idempotency_key` — concurrent duplicate same-key requests are safe at the DB level.
2. Broadcast rows are created with `delivery_status = PENDING` — **no delivery pipeline exists** (in-app rows are the deliverable; push is future work).
3. **Mobile has no notification UI** — broadcast rows are served by the shared endpoints, but no mobile screen displays them yet; student visibility is API-verified only.
4. **No push/SMS/email** — channel A only; UI copy states this explicitly on success.
5. Audience counts reflect **active users at send time**; later account/assignment changes do not re-deliver past broadcasts.
6. Web production build failure is pre-existing and out of Phase 50 scope.
7. `POST /broadcast` replay returns **200 + `duplicate=true`** (not 409) — intentional, mirrors the payments idempotency convention.

## 16. Explicit Push-Existence Statement

**Channel: A — In-app notifications only.**

Phase 50 creates real `Notification` rows through the existing `NotificationService` and they are delivered/visible through the existing in-app notification center. **It does not implement, claim, or simulate push notifications.** Evidence: `DeliveryStatus` marks push as future work; no device tokens, FCM/APNs, or provider code exist anywhere; the mobile app has no notification screen; the success UI explicitly says "in-app notifications only — no push/SMS/email channel was used."

## 17. Git Status

- **HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` — **unchanged** before/after. Top commit remains "fix: close Phase 42 product acceptance defects". **No commits, no push, no new branch, no reset, no history rewrite.**
- **Branch:** `main`.
- **Lockfile:** `package-lock.json` sha256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A` — **unchanged**. No new dependencies.
- `git diff --check` — exit 0 (only the pre-existing LF→CRLF warning on `apps/mobile/package.json`).
- **Phase 50 working-tree files:** `M` notifications/{models,router,schemas,service}.py, `M` migrations/env.py, `??` migrations/versions/0012_admin_broadcasts.py, `??` tests/test_phase50_admin_notifications.py, `M` packages/shared-types/src/index.ts, `M` apps/web/src/lib/api.ts, `M` apps/web/src/components/Sidebar.tsx, `M` apps/web/src/app/dashboard/notifications/page.tsx, `??` apps/web/src/app/dashboard/admin/broadcasts/, `??` PHASE_50_ADMIN_NOTIFICATIONS_AND_BROADCAST.md. All other dirty entries are inherited from Phases 43–49 and were not touched by this phase. Temp notes (`.claude-phase50-notes.md`, `.p50_tok.txt`) deleted.

## 18. No-Deployment Confirmation

No Docker image rebuild, no `docker-compose` change, no production deployment, no server/provisioning action. Migration 0012 was applied **only to the local dev Postgres container** (`uniserve_postgres`, port 5433) via manual `alembic upgrade head`. Local uvicorn (:8001) and web dev (:3000) servers were started solely for live E2E verification.
