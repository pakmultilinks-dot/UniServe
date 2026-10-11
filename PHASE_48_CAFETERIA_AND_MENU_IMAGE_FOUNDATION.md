# Phase 48 — Cafeteria Management + Menu Image Foundation

**Date:** 2026-10-05
**Scope:** 48A — Admin cafeteria management through the real UI/API where backend support exists. 48B — Menu-item image management + host-independent image-URL infrastructure.
**Phase 47 is COMPLETE and was NOT redone.**

---

## 1. Starting HEAD

`bc967b35fccaf7bb6c1b3a4b31e356000bd788ee`

## 2. Ending HEAD

`bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (unchanged — no commit)

## 3. Branch

`main` (unchanged, no branch operations performed)

## 4. Files Changed

**Backend (apps/api):**
- `app/modules/menus/service.py` — modified: image constants (`MENU_IMAGE_URL_PREFIX`, `MENU_IMAGE_DIR`, `MAX_MENU_IMAGE_BYTES`), magic-byte detection, traversal-safe path resolution, orphan-safe file cleanup, `set_menu_item_image`, `remove_menu_item_image`.
- `app/modules/menus/router.py` — modified: `POST /{menu_item_id}/image` + `DELETE /{menu_item_id}/image` (raw-binary upload, docstring rationale).
- `migrations/versions/0011_normalize_menu_image_urls.py` — new: data-only normalization of seeded `image_url` values to host-independent `/api/v1/static/food/*`.
- `tests/test_phase48_cafeteria_and_images.py` — new: backend tests A–F (cafeteria) + G–P (images).

**Shared (packages/shared-types):**
- `src/index.ts` — modified: additive `ApiClient.uploadBinary()` (raw body, caller Content-Type, identical auth/refresh/timeout/error semantics). `dist/` rebuilt via workspace `tsc` build (required because web runtime resolves `dist/` via package exports — not a dependency change).

**Web (apps/web):**
- `src/lib/api.ts` — modified: `createCafeteria`, `uploadMenuItemImage`, `removeMenuItemImage`.
- `src/lib/imageUrl.ts` — new: `resolveApiImageUrl()` host-independent resolver.
- `src/app/dashboard/cafeterias/page.tsx` — modified (48A): Add Cafeteria modal, inline Edit, Close/Open toggle, Deactivate confirm modal + Activate, Active/Inactive badges.
- `src/app/dashboard/menu/page.tsx` — modified (48B): thumbnails via resolver, Add/Replace Image modal, Remove Image confirm modal.

**Mobile (apps/mobile):**
- `src/config.ts` — modified: exported `resolveApiImageUrl()`.
- `src/components/FoodImage.tsx` — modified: resolver applied before category fallback (covers all call sites).

**Not touched:** cafeteria module backend (already complete from earlier phases — 48A was UI+tests only), daily-menu publish/unpublish, student/faculty ordering, reports/notifications/refunds/settings/audit UI, Phase 47 files.

## 5. Cafeteria Functionality (48A)

Backend endpoints reused as-is (no backend changes required for cafeterias):
- `POST /api/v1/cafeterias/` — admin-only create, 201; duplicate name → 409 `Cafeteria already exists: <name>`.
- `GET /api/v1/cafeterias/` — role-filtered list.
- `PUT /api/v1/cafeterias/{id}` — UNIVERSITY_ADMIN only, including `is_active`.
- `PATCH /api/v1/cafeterias/{id}/status` — ADMIN/MANAGER operational status.
- **No DELETE endpoint exists** (documented gap — deactivation is the only lifecycle action).

Web UI delivered: "+ Add Cafeteria" modal (name/type/location/description, error-aware), inline Edit, Close/Open operational toggle, Deactivate with named confirm modal ("Deactivate {name}?" + accurate preservation wording — menu items, orders, staff assignments preserved), Activate, Active/Inactive badges alongside operational status.

`Cafeteria.is_active` is consumed ONLY by admin overview counts + list filter — **no cascade** to menu items, orders, assignments, or users (verified in backend test_e + E2E).

## 6. Image Functionality (48B)

- **Upload:** `POST /api/v1/cafeterias/{cid}/menu-items/{mid}/image` (raw binary body, `image/*` Content-Type, ADMIN/MANAGER scope via `RequireCafeteriaWriteScope` + cross-cafeteria `verify_resource_cafeteria` 403/404).
- **Remove:** `DELETE .../image` — clears `image_url`, orphan-safe cleanup, idempotent.
- **Validation (authoritative, server-side):** magic bytes decide stored format (JPEG `\xff\xd8\xff`, PNG `\x89PNG\r\n\x1a\n`, WEBP `RIFF....WEBP`); declared Content-Type must be `image/*` and must match detected format (else 400 "File content does not match its declared image type"); MAX 5MB (400 "Image must be..."); server-generated `uuid4().hex+ext` filenames.
- **Orphan-safe cleanup:** old file deleted ONLY when no other `menu_item` references it (ref-count after flush). Verified live: replacement deleted old file from disk; removal deleted last-referenced file; shared-reference test (test_o) proves multi-reference safety.
- **Web UI:** thumbnails with dashed placeholder when absent; Add/Replace modal (client-side type/size validation, object-URL preview, **no auto-upload** — upload only on explicit confirm, modal closes on success, stays open on error with ApiErrorInfo banner); Remove with named confirm modal.

## 7. URL Strategy (Host-Independent Foundation)

- **Persisted value:** always host-independent `/api/v1/static/food/<file>` — NEVER `localhost`, `127.0.0.1`, `api.localhost`, or `http(s)://`.
- **Render time:** frontends attach the configured API origin via `resolveApiImageUrl()`:
  - Web: `apps/web/src/lib/imageUrl.ts` — `API_ORIGIN = NEXT_PUBLIC_API_URL minus /api/v1 suffix`; relative path → `API_ORIGIN + path`; `http(s)://` passed through; bare filename defensively prefixed.
  - Mobile: `apps/mobile/src/config.ts` — same logic; applied in `FoodImage.tsx` before category fallback.
- **Static serving:** `main.py` mounts `/api/v1/static` → `app/static/food/` (27 real JPGs baked).
- **Migration 0011** (data-only, Postgres; SQLite test suite uses `create_all` so migrations never run in tests; downgrade no-op): normalized seeded `%host%/api/v1/static/food/x` → `/api/v1/static/food/x`. Applied to live DB: 27 rows normalized, 0 host-specific rows remained.

## 8. Backend Endpoints Added/Modified

| Endpoint | Change | Auth scope |
|---|---|---|
| `POST /api/v1/cafeterias/{cid}/menu-items/{mid}/image` | **NEW** — raw-binary body upload | ADMIN/MANAGER (`RequireCafeteriaWriteScope`) + `verify_resource_cafeteria` |
| `DELETE /api/v1/cafeterias/{cid}/menu-items/{mid}/image` | **NEW** — remove image + orphan cleanup | same as above |
| All other endpoints | **UNCHANGED** (cafeterias, menu CRUD, daily-menus publish/unpublish, orders) | unchanged |

**Raw-binary upload rationale (important):** `python-multipart` is NOT installed in the environment (ModuleNotFoundError verified) and dependency/lockfile changes are forbidden by mission constraints — so multipart/form-data upload was impossible without violating constraints. The endpoint therefore accepts raw image bytes in the request body with an `image/*` `Content-Type` header. Server-side validation (magic bytes, size, declared-type match) is identical in rigor to a multipart path. This is documented in the router docstring and justified as the minimal dependency-free path.

## 9. Tests Added

Backend: `apps/api/tests/test_phase48_cafeteria_and_images.py`
- **Cafeteria A–F:** A admin create 201; B invalid payloads → 422; C duplicate → 409 exact message; D non-admin (student/staff/manager) → 403; E deactivation preserves assignments + menu items + user rows + listing intact; F PUT admin-only (manager 403) + rename + PATCH status regression.
- **Images G–P:** G valid PNG upload → 200, host-independent `image_url`, file on disk, persists on fresh GET; H invalid content (HTML-as-PNG, text/plain, magic/declared mismatch) → 400, nothing stored; I oversized → 400; J student + unassigned staff → 403; J2 assigned manager uploads OK + cross-cafeteria path → 403/404; L replacement (old orphan deleted); O shared-reference safety (two items same cafeteria — shared file survives first replacement, deleted when last reference removed); M/N remove → null + item intact + orphan cleaned + idempotent re-remove; P no host-specific origins written; seeded-data survival (pre-existing cafeteria/item survive image flow).
- Test DB has NO seed data (fresh SQLite per test) — survival tests create their own pre-existing data within the test.

## 10. Backend Test Results

- Full suite: **`719 passed`** in 339.39s (run from `apps/api`).
- Phase 48 test file: all tests passing after fixes (fixture data creation, same-cafeteria shared-reference constraint, `manager_user` fixture param, Role enum import).

## 11. Type-Check

**PASSED** — `npm run type-check:web` clean. (Shared-types `dist/` rebuilt first; type-check uses `src/` via tsconfig paths, runtime resolves `dist/` via package exports — documented lesson, not a dependency change.)

## 12. Lint

**PASSED** (warnings only, no errors): 3 NEW `@next/next/no-img-element` warnings in `menu/page.tsx` (same acceptable class as pre-existing `Avatar.tsx` warning — thumbnails are intentionally `<img>` for dynamic remote-resolved URLs); pre-existing `orders` useCallback/useFetch warnings unchanged. No lint errors introduced.

## 13. Build

**FAILED with the PRE-EXISTING dual-React failure** (documented since Phase 46, NOT fixed, NOT caused by Phase 48): styled-jsx crash prerendering stock `/_error` → `/404`, `/500`; all 24 pages compiled successfully; harmless lockfile-patch `TypeError` (Cannot read 'os') from Next's `patch-incorrect-lockfile` in the workspace setup. Fixing this would require React/lockfile changes — explicitly forbidden. Left as-is.

## 14. Manual E2E A–H (Real UI)

Environment: local uvicorn `:8001` (root venv Python 3.13.7) + Next dev `:3000` with `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1`; real Postgres (`uniserve_prod`, container `uniserve_postgres`, host port 5433) after `alembic upgrade head` → 0011. Admin logged in through the real login page.

- **A — Create cafeteria:** "+ Add Cafeteria" modal → duplicate name "Student Cafeteria" rejected with 409 toast `Cafeteria already exists: Student Cafeteria` + modal stayed open; valid create ("Phase48 Test E2E", student, "Test Annex Block") → modal auto-closed, card rendered with Active badge; **page reload → card persisted**.
- **B — Edit + deactivate/activate:** inline Edit changed location → "Test Annex Block - Edited" persisted after reload; Deactivate → named confirm modal ("Deactivate Phase48 Test E2E?" + preservation wording) → Inactive badge + button flipped to Activate; Activate → Active badge restored; Student/Faculty cafeterias untouched throughout.
- **C — Image upload:** "Phase48 Image Test Dish" created (main course, PKR 250) → Add Image modal → file selected (`chicken-biryani.jpg`) → preview shown (182 KB), **no auto-upload** → confirm Upload → thumbnail rendered with resolved src `http://localhost:8001/api/v1/static/food/635a1dd2….jpg` (resolver proof: persisted value host-independent, origin attached at render) → **reload + re-select → thumbnail persisted**.
- **D — Replace:** Replace Image modal (current image shown) → `fries.jpg` → new thumbnail `67e12db8….jpg` after reload; **old file deleted from disk** (orphan cleanup live-verified); DB `image_url` = new relative path.
- **E — Remove:** confirm modal ("Remove image from Phase48 Image Test Dish?" + "menu item stays fully available — only its photo is removed") → placeholder returned; card fully intact (name/category/price/description/active/prep-time) and still orderable; **reload → stays removed**; DB `image_url` = NULL; orphan file deleted from disk.
- **F — Seeded images:** Student Cafeteria — 15 thumbnails render (`omelette.jpg`, `paratha.jpg`, `chicken-burger.jpg`, `pizza-slice.jpg`, …) all resolved to `http://localhost:8001/api/v1/static/food/*`; Faculty Cafeteria seeded items render thumbnails with Replace/Remove actions; static files served 200; student web role redirects to `/mobile-required` (preserved behavior — student ordering is the mobile app; mobile resolver applied in code).
- **G — Android/LAN maximum verification:** API restarted bound to `0.0.0.0:8001`; LAN IPv4 `192.168.18.79`; probes: seeded static file → **200 via LAN**; fresh raw-binary API upload (`135aed1f….jpg`) → **200 via LAN AND localhost**; resolver attaches configured origin at render time. **Honest limits:** no physical Android device is controllable by the agent (web student view is mobile-required by design); production container `uniserve_api` (:8000) runs baked pre-Phase-48 code with no bind mounts — new uploads land on host disk and are served only by the local :8001 process; deployment is forbidden this phase → physical-device + production-container image verification is deferred to the next deploy. The mobile app will render new images once `NEXT_PUBLIC_API_URL`/API origin points at the server that owns the uploads.
- **H — No host-specific URLs:** API inspection across all three cafeterias: Faculty 13 items (12 with image), Student 18 (15 with image), test 1 — **bad = 0 everywhere**; docker psql: 27 rows `/api/v1/static/food/%`, 0 rows containing localhost/127.0.0.1/api.localhost/http, 5 rows NULL image_url (4 pre-existing + test dish — nullable by design, UI shows placeholder).

## 15. Android Verification

Maximum honest verification as detailed in Test G: LAN-reachable API proven (200s from `192.168.18.79:8001`), resolver pattern applied to mobile (`FoodImage.tsx` → `resolveApiImageUrl`), production gap documented. No physical Android device access for the agent; production :8000 container serves only baked pre-Phase-48 images until the next (forbidden-this-phase) deployment.

## 16. Data-Safety Verification

- **No major DB redesign** — one data-only Alembic migration (0011), downgrade no-op.
- **Existing data preserved:** 3 cafeterias (2 seeded active/open + 1 test deactivated), 47 orders intact, 15 users intact, 27 seeded menu images intact.
- **Phase 47 suspended accounts untouched:** `p47.testa@student.lgu.edu.pk`, `p47.testb@lgu.edu.pk`, `p47.testc@lgu.edu.pk` — all still `suspended`.
- **No SQL used for functionality** — all changes through API/UI; SQL only for verification (psql counts).
- **Daily-menu publish/unpublish behavior preserved** (backend suite passed; daily-menu section rendered correctly on menu page; no daily-menu code touched).
- **Student/Faculty ordering preserved** — student web login still routes to `/mobile-required`; order flow code untouched; 47 historical orders unchanged.
- **No seeding/wiping** — new test data only via real UI/API; final state documented (test cafeteria deactivated, test dish image NULL — hygiene met).

## 17. Known Pre-Existing Issues (Not Fixed, Not Caused by Phase 48)

- Dual-React build failure (root React 19 + apps/web React 18; styled-jsx crash on stock error pages) — fix forbidden (React/lockfile changes).
- Next lockfile-patch `TypeError` + npm `ENOWORKSPACES` warning in workspaces dev flow.
- `"Middleware cannot be used with output: export"` + rewrites warnings in Next static-export config.
- Lint warnings (`no-img-element`, orders useCallback/useFetch) — pre-existing class.

## 18. Remaining Gaps (Honest)

- **No DELETE endpoint for cafeterias** — deactivation is the only lifecycle action; test cafeteria left deactivated (`is_active=false`) since deletion via API is impossible by design.
- **Production container gap:** `uniserve_api` (:8000) runs baked pre-Phase-48 code, Mounts `[]` — new uploaded images exist only on host disk; served by local :8001 only. Next deploy must copy `app/static/food/` and include Phase 48 code. Deployment forbidden this phase.
- **Physical Android verification** deferred (no device access; mobile resolver implemented + LAN-reachable API proven).
- **5 menu items have NULL image_url** (4 pre-existing seeded + 1 test dish) — placeholders render; admins can attach images via the new UI at any time.
- **Test data left in DB:** "Phase48 Test E2E" cafeteria (deactivated) + "Phase48 Image Test Dish" (active, image NULL) — no delete endpoint for cafeteria; item could be deactivated via existing UI in a later cleanup phase.

## 19. Explicit Confirmations

- **Commit: NO** — working tree only; HEAD unchanged.
- **Push: NO** — no push performed.
- **Deploy: NO** — no Docker rebuild/push, no deployment, Docker Desktop only used for read-only psql verification.
- **Dependency changes: NO** — no package.json dependency edits (raw-binary upload chosen precisely to avoid `python-multipart`); `shared-types` dist rebuilt with existing `tsc` only.
- **Lockfile: NOT CHANGED** — sha256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A` unchanged.
- **Branch: `main` unchanged**; starting HEAD = ending HEAD = `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee`.
- **No reset/clean**; all inherited Phases 43–47 dirty entries preserved; Phase 48 files added on top (see final git inspection in closing response).
- **Test servers killed** after E2E (uvicorn :8001 + web :3000 terminated).

## 20. Environment Notes (For Future Phases)

- API login body field is `university_email` (not `email`); token at `response.tokens.access_token`.
- PowerShell 5.1: `$pid` is read-only (use `$procId`); scripts to `$env:TEMP\*.ps1` + `powershell -NoProfile -ExecutionPolicy Bypass -File`.
- Lint needs `$env:NODE_PATH = "...\apps\web\node_modules"`; pytest runs with cwd=`apps/api`.
- Toasts auto-dismiss (~3s) — capture immediately; toasts in `div.fixed` without aria roles.
- shared-types: type-check uses `src/`, runtime resolves `dist/` — rebuild after src changes.
- Docker Desktop at `C:\Users\Lenovo\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`.
- LAN IP observed this session: `192.168.18.79` (was `192.168.100.5` in older sessions — DHCP varies; always re-check with `ipconfig`).
