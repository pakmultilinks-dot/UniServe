# PHASE 47 — Member & Staff Management

**Date:** 2026-10-05
**Branch:** `main` · **HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (unchanged)
**Commit created:** NO · **Push performed:** NO · **Staged files:** 0
**Dependency changes:** NO · **Lockfile changed:** NO (`package-lock.json` sha256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A`, identical to pre-phase baseline)

---

## 1. Executive Summary

Phase 47 closed the Phase 45 P0 gap (role changes to Staff/Manager omitted the backend-required `cafeteria_id`) and delivered the complete Admin member & staff management workflow end-to-end through the **real Admin UI against the real API**:

- **Real "Add Member" workflow** — the Admin Members page now calls the real `POST /api/v1/users/` for Student, Faculty, Staff, Manager and University Admin accounts. Temporary passwords are shown exactly once with a copy button and a secure-share note.
- **P0 role-change fix** — `PUT /users/{id}/role` now always sends `cafeteria_id` when the target role is Staff/Manager; the confirm action is disabled until a cafeteria is chosen; the confirmation text names the member, role and cafeteria. Backend validation (Pydantic `model_validator`) rejects staff/manager requests without `cafeteria_id`, and rejected requests leave no partial change.
- **Cafeteria assignment display & reassignment** — `/users/` responses now expose `cafeteria_id`, `cafeteria_name` and `updated_at` (the only backend change made — data was genuinely absent from the contract). Assignments are shown in list, detail and both admin pages, and can be reassigned through the same coherent role endpoint (single workflow, no invented endpoints).
- **Real "Staff & Managers" page** — operational listing filtered to `cafeteria_staff` + `cafeteria_manager` (managers were missing from the Phase 45 page), with search, role chips, status/cafeteria filters, suspend/activate UX and an "Add Staff" entry pre-set to the Staff role.
- **Suspend/Activate** — named-target confirmation dialogs, mandatory suspension reason, accurate session-revocation wording, status badges and action swapping verified live, including persistence across browser reloads.
- **Member list improvements** — search, role chips, role badges, status badges, cafeteria filter (incl. "Unassigned"), "(you)" self-marker with all self-mutating actions hidden, and the Phase 46 error→empty→success state machine preserved everywhere.

All 8 manual E2E tests (A–H) **PASSED** through the real UI. Backend tests **36 passed** (13 new Phase 47 tests). Type-check clean; lint clean (3 pre-existing warnings only, none in Phase 47 files). No commits, no pushes, no dependency or lockfile changes, no DB schema changes.

---

## 2. Backend Changes (assignment exposure + validation only)

The mission permitted backend changes ONLY to expose assignment data if genuinely absent, plus validation for the P0 bug. Exactly that was done — no new endpoints, no RBAC weakening, no schema changes.

### 2.1 `apps/api/app/modules/auth/schemas.py`
- `UserSummary` gains optional `cafeteria_id: str | None`, `cafeteria_name: str | None`, `updated_at: datetime | None` (after `created_at`). Existing fields untouched; the second `UserSummary` in `administration/schemas.py` (counts only) intentionally unchanged.
- `CreateUserByAdminRequest` and `ChangeUserRoleRequest` both gain `@model_validator(mode="after")` raising `ValueError("cafeteria_id is required for staff and manager roles")` when role ∈ {CAFETERIA_STAFF, CAFETERIA_MANAGER} and `cafeteria_id` is None.
  - **Why `model_validator` and not `field_validator`:** Pydantic 2.13 does not run `field_validator` on a field that carries a default and is omitted from the input. A `field_validator` on `cafeteria_id` was silently skipped, letting staff-without-cafeteria requests return 201. `model_validator(mode="after")` validates the cross-field rule reliably → 422 as required.

### 2.2 `apps/api/app/modules/users/router.py`
- New helper `_attach_cafeteria_info(summaries, db)` — queries the `CafeteriaAssignment` table **directly** (`select(user_id, cafeteria_id).where(user_id.in_(...))`) then one bulk `select(Cafeteria.id, Cafeteria.name)`, and stamps `cafeteria_id`/`cafeteria_name` onto each summary.
  - **Why table-direct:** reading the `user.cafeteria_assignment` ORM relationship returned stale `None` inside shared test sessions (SQLAlchemy identity map serves the cached parent object whose relationship was never loaded). Table-direct reads are correct for freshly-mutated sessions too (autoflush covers pending adds).
- Helper called in all six user endpoints: `list_users`, `get_user`, `create_user`, `suspend_user`, `activate_user`, `change_user_role`.
- `change_user_role` hardening:
  1. Validates cafeteria requirement + cafeteria existence **before** any mutation (`old_role = user.role; user.role = body.role` happens only after validation passes) — rejected requests leave no partial change.
  2. Role-change audit event description includes old→new role.
  3. Assignment upsert for staff/manager; assignment row **deleted** when the target role is student/faculty/university_admin.
- Existing endpoints/behavior otherwise unchanged (temp password `generate_otp()+"Aa1!"`, auto `email_verified` + ACTIVE, duplicate 409s, manager restrictions, session revocation on suspend, self-change prevention, self-only DELETE).

### 2.3 Tests — `apps/api/tests/test_phase47_user_management.py` (NEW, 13 tests)
- `TestAssignmentExposure`: staff assignment visible in list (created via real POST — no pre-created duplicate identifiers); detail exposes assignment; student detail has null assignment.
- `TestMemberCreation`: student create (temp password regex `^\d{6}Aa1!$`, active, email_verified, cafeteria null); staff-with-cafeteria auto-assigns; manager-with-cafeteria; **staff-without-cafeteria rejected in (400,422)**; duplicate email → 409 "User with this email already exists"; duplicate university ID → 409 "User with this University ID already exists".
- `TestRoleChangeWithCafeteria`: student→staff requires+sets cafeteria; same-role PUT reassigns cafeteria; change to student deletes the assignment row.
- `TestLifecycle`: create → reassign → suspend → activate → detail persists.

**Result:** `pytest tests/test_phase47_user_management.py tests/test_auth_authorization.py` → **36 passed** (root venv Python 3.13.7 / pytest 9.1.1, cwd `apps/api`).

---

## 3. Frontend Changes

### 3.1 Shared contract — `packages/shared-types/src/index.ts`
- `User` += `cafeteria_id?`, `cafeteria_name?`, `updated_at?` (Phase 47 comment).
- New: `AdminCreateUserRequest`, `AdminCreateUserResponse` (`user` + `temporary_password`), `AdminChangeRoleRequest` (`role` + optional `cafeteria_id`), `AdminSuspendRequest` (`reason`).

### 3.2 API client — `apps/web/src/lib/api.ts`
- New/updated wrappers (all typed, all hitting existing endpoints only): `getUsers(params?)`, `getUserDetail(userId)`, `createUser(data)` → `POST /users/`, `suspendUser(userId, reason)`, `activateUser(userId)`, `changeUserRole(userId, role: User["role"], cafeteriaId?)`. Errors flow through Phase 46 `getApiErrorInfo`.

### 3.3 Email rules — `apps/web/src/lib/universityEmail.ts` (NEW)
- Mirrors the backend's configured university-email patterns as blocking helpful validation (student: `^fa\d{2}-.+@lgu\.edu\.pk$` / `.+@student\.lgu\.edu\.pk$`; faculty/staff/manager/admin → faculty group). Backend remains authoritative; this only prevents obviously-wrong submissions with an actionable message.

### 3.4 Admin components — `apps/web/src/components/admin/` (NEW, 5 files)
| File | Purpose |
|---|---|
| `ModalShell.tsx` | Fixed backdrop (click closes) + centered scrollable card, `role="dialog" aria-modal` |
| `RoleBadge.tsx` | Role badges (Student/Faculty/Staff/Manager/Admin) + `roleLabel()`; colors distinguish only, no permission implication |
| `AddMemberModal.tsx` | Real create flow: name/ID/email validation (incl. role-aware university email), role select with optgroups, cafeteria select revealed for Staff/Manager with helper text + inline "Cafeteria is required for Staff accounts.", duplicate/other API errors via toast, success panel showing `temporary_password` **once** with copy button + secure-share note |
| `ChangeRoleModal.tsx` | Role mode (new role + required cafeteria for staff/manager, explicit confirmation naming member/role/cafeteria) and Cafeteria mode (shows current assignment, reassign via the same role endpoint with unchanged role). `canSubmit` prevents no-op saves and the P0 broken payload. **E2E-driven fix:** dialog now calls `onClose()` after a successful change (both modes) — see §9 Test D |
| `MemberDetailsModal.tsx` | Detail view fetched from `GET /users/{id}`: name/email/ID/RoleBadge/StatusBadge/email-verified/Cafeteria/Joined/**Last updated** (new `updated_at`), with loading skeleton + retryable LoadErrorState |

### 3.5 Pages (rewritten, Phase 46 state machine preserved)
- **`apps/web/src/app/dashboard/admin/users/page.tsx` — "Members"**: PageHeader + [Add Member]; search + role chips (All/Student/Faculty/Staff/Manager/Admin) + status select + cafeteria select (All/Unassigned/each cafeteria); single `getUsers()` fetch + client-side filtering; table Member (name+email, "(you)" marker)/University ID/RoleBadge/Cafeteria/Status/Joined/Actions (View, Role, Cafeteria [staff/manager only], Suspend [active], Activate [suspended]; **all mutation actions hidden on the self-row**); error→empty→success machine (compact banner when stale data exists, full LoadErrorState when empty); modals: AddMember, MemberDetails, ChangeRole (both modes), Suspend (named target, mandatory reason, accurate session wording), Activate (named target).
- **`apps/web/src/app/dashboard/staff/page.tsx` — "Staff & Managers"**: same foundations; `OPERATIONAL_ROLES = {cafeteria_staff, cafeteria_manager}` filter (**managers now included** — Phase 45 gap); role chips (All Staff/Staff/Managers); "Add Staff" opens AddMemberModal with `preselectedRole="cafeteria_staff"`; actions View/Cafeteria/Suspend/Activate — **no inline role select, no operational order controls** (admin management ≠ order operations, per mission).

---

## 4. Member Creation (Manual Test A — PASS)

Admin UI → Members → **Add Member** → form → real `POST /users/`:

1. **Client validation:** submitted with `p47.testa@lgu.edu.pk` for role Student → inline blocking error on the email field: *"Student emails must look like fa22-bse-001@lgu.edu.pk or name@student.lgu.edu.pk."* — no API call made.
2. Corrected to `p47.testa@student.lgu.edu.pk` → **Create Student** → success panel: *"Member Created — The account is active and the email is pre-verified. Share this temporary password securely — it is shown only once and cannot be retrieved again."* + temporary password (conformed to backend format `^\d{6}Aa1!$`) + **Copy** button + Done.
3. After Done the new row appears immediately: `Phase47 TestA · p47.testa@student.lgu.edu.pk · P47-STU-001 · Student · Not assigned · active · Oct 5, 2026 · [View][Role][Suspend]` — correct action set for a student (no Cafeteria button).

---

## 5. Staff & Manager Creation (Manual Tests B & C — PASS)

1. **Staff (Test B):** Add Member → selecting role **Staff** reveals the cafeteria select with helper *"Staff and Manager accounts must be assigned to a cafeteria."*; submit button relabels to "Create Staff". Submitting **without** a cafeteria → inline alert *"Cafeteria is required for Staff accounts."* (blocked client-side; the broken payload never leaves the browser — the P0's counterpart guard). Selecting **Student Cafeteria** → created; temporary password shown once; row: `Staff · Student Cafeteria · active` with View/Role/Cafeteria/Suspend actions.
2. **Manager (Test C):** same flow with role **Manager** + **Faculty Cafeteria** → row: `Manager · Faculty Cafeteria · active`. (Backend also permits University Admin creation — select included, not exercised to avoid extra test accounts.)
3. **Staff & Managers page:** all three P47 operational accounts appear alongside seed staff; **Managers chip lists both manager accounts** (Phase 45 page had shown staff only); "Add Staff" opens the modal with **Staff preselected** + cafeteria required (verified, cancelled without creating).

---

## 6. Role Change (Manual Test D — PASS, incl. P0 fix verification)

Target: `P47-STU-001` (Student, unassigned) → row **Role** button → Change Role modal:

1. Selecting **Staff** reveals the required cafeteria select + helper text; **Confirm Change is disabled** until a cafeteria is chosen (`confirmDisabledBeforeCafeteria: true` measured in the live DOM) — the exact payload omission from Phase 45 is now impossible from the UI.
2. With Student Cafeteria selected the confirmation reads: *"Change Phase47 TestA to Staff at Student Cafeteria?"* — member, role and cafeteria named explicitly.
3. **Confirm Change** → `PUT /users/{id}/role` with `{role: cafeteria_staff, cafeteria_id}` → row becomes `Staff · Student Cafeteria · active`; the Cafeteria action appears.
4. **Reverse direction** (Staff → Student): assignment row is deleted by the backend — row returns to `Student · Not assigned` (verified live).
5. **E2E-discovered defect & fix:** on first run the modal stayed open after a successful change (background list refreshed, dialog showed stale context). Root cause: the success path called `onUpdated()` (list reload) but never `onClose()`. Fixed in `ChangeRoleModal.tsx` (success path now closes the dialog in both modes) and **re-verified live**: modal closes automatically, row updates, toast "Role updated successfully." fires.

---

## 7. Cafeteria Assignment (Manual Test E — PASS)

Target: `P47-STF-001` (Staff @ Student Cafeteria) → row **Cafeteria** button → modal shows current assignment: *"Phase47 TestB currently works at Student Cafeteria."* → select **Faculty Cafeteria** → **Save Assignment** → toast "Cafeteria assignment updated.", dialog closes, row shows `Faculty Cafeteria`. **Browser reload** → row still `Faculty Cafeteria` (fresh `GET /users/` from the database — persistence proven). The reassignment rides the existing `PUT /users/{id}/role` endpoint with the unchanged role — one coherent workflow, no invented endpoints.

---

## 8. Suspension & Activation (Manual Test F — PASS)

Target: `P47-MGR-001` (Manager):

1. **Suspend** → named-target dialog: *"Suspend Phase47 TestC?"* + *"They will no longer be able to sign in until reactivated. Any active sessions will be revoked."* + reason textarea. **Confirm Suspend is disabled while the reason is empty.**
2. Reason entered (`Phase 47 E2E verification - temporary suspension test`) → confirmed → toast "Member suspended.", dialog closes, status badge → `suspended`, action swaps to **Activate**.
3. **Browser reload** → still suspended (persistence).
4. **Activate** → named-target dialog: *"Activate Phase47 TestC?"* + *"They will be able to sign in again with their existing credentials."* → confirmed → toast "Member activated." (caught live in the toast container), status → `active`, action swaps back to Suspend. Reload → still active.

---

## 9. Validation Summary

| Check | Result |
|---|---|
| Backend tests (`test_phase47_user_management.py` + `test_auth_authorization.py`) | **36 passed** |
| TypeScript (`npm run type-check:web`) | **Clean** (exit 0), re-run after the E2E modal fix |
| ESLint (`npm run lint --workspace=apps/web`, `NODE_PATH` workaround per Phase 46) | **Clean** — 3 pre-existing warnings only (`orders/page.tsx` exhaustive-deps, `Avatar.tsx` no-img-element, `useFetch.ts` exhaustive-deps); **none in Phase 47 files** |
| Frontend build | **Pre-existing failure out of scope** — dual-React node_modules (root react 19.2.3 vs `apps/web` react-dom 18.3.1) crashes styled-jsx while prerendering stock `/404`,`/500`; dev server + type-check + lint unaffected; unchanged from Phases 43–46 |
| `git diff --check` | Clean (only the pre-existing `apps/mobile/package.json` CRLF notice) |
| Git HEAD / staged / lockfile | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` unchanged / 0 staged / lockfile hash identical |
| Commit / Push | **NO / NO** |

---

## 10. Manual E2E Tests A–H — Results (real Admin UI, real API)

**Runtime setup (honest disclosure):** the Docker `uniserve_api` container (image `uniserve-prod-api`, up 13 h, no bind mounts) serves the **pre-Phase-47** API code and port 8000 is owned by Docker — rebuilding/restarting it would be a **deploy, which the mission forbids**. E2E therefore ran the **same codebase** locally: uvicorn (`apps/api`, root venv, `POSTGRES_DB=uniserve_prod` at `localhost:5433` — the **same live database** the Docker stack uses) on `127.0.0.1:8001`, plus the Next.js dev server on **port 3000** (mandatory — backend CORS allows only localhost:3000/8081) with `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1`. A probe against :8001 confirmed `cafeteria_id, cafeteria_name, updated_at` present in `/users/` responses before any UI testing. Test services were stopped after verification; the production Docker stack was never restarted or redeployed.

| # | Test | Result | Key evidence |
|---|---|---|---|
| A | Create Student | **PASS** | Client-side student-email validation error shown; real `POST /users/`; temp password shown once (format `^\d{6}Aa1!$`); row active with correct actions |
| B | Create Staff w/ cafeteria | **PASS** | Cafeteria select revealed for Staff + helper text; submit without cafeteria blocked with "Cafeteria is required for Staff accounts."; created with Student Cafeteria; appears on Staff page |
| C | Create Manager w/ cafeteria | **PASS** | Created with Faculty Cafeteria; Manager badge + assignment displayed; Managers chip on Staff page lists managers (Phase 45 gap fixed) |
| D | Role change Student→Staff (P0 fix) | **PASS** | Confirm disabled until cafeteria chosen; confirmation names member+role+cafeteria; `PUT /users/{id}/role` sent with `cafeteria_id`; row updated; reverse change deletes assignment; modal auto-close defect found & fixed & re-verified |
| E | Reassign cafeteria + refresh | **PASS** | Modal shows current assignment; Save → Faculty Cafeteria; **browser reload persists** |
| F | Suspend + Activate | **PASS** | Named-target dialogs both ways; reason mandatory (disabled button); wording accurate; status badge + action swap; persistence after reload; toasts "Member suspended."/"Member activated." observed |
| G | Duplicate email/ID | **PASS** | Duplicate email → toast "User with this email already exists" (HTTP 409); duplicate ID → "User with this University ID already exists" (HTTP 409); modal keeps values for correction; **no duplicate records created** (exactly 3 P47 rows remain) |
| H | Refresh persistence | **PASS** | Create, role change, reassignment and suspend/activate all verified against fresh `GET /users/` after full browser reloads |
| + | Filters & error states | **PASS** | Search "p47" → exactly the 3 test rows; Manager chip → both managers; Faculty Cafeteria filter → correct subset; zero-match filter → "No members found / Try adjusting your filters, or add a new member." empty state (not an error state); Phase 46 error machine intact (dashboard notifications 500-sim still shows "Unable to load recent notifications." + Try again) |
| + | Member details | **PASS** | View modal shows Role/Status/Email verified/**Cafeteria**/**Last updated** (the new `updated_at` field live from the detail endpoint) |

**Observations (not failures):** transient paired 401s appear in the console during full page loads (silent-refresh race, Phase 46 behavior — app recovers transparently, no forced logout after login); the Toast component renders visually but carries no `role="status"`/`aria-live` attribute (minor a11y follow-up, pre-existing Phase 46 component).

---

## 11. Database Hygiene

No SQL was used for any functionality, verification, or cleanup — everything went through the real application API/UI. No schema changes. No migrations.

**Created via application workflow (real `POST /users/`), then suspended via the real UI as cleanup** (admin has no delete-others endpoint — `DELETE /users/{id}` does not exist; only self-delete `DELETE /users/me` — so suspend-and-document is the correct application-workflow terminal state):

| University ID | Email | Final role / assignment | State left in DB |
|---|---|---|---|
| `P47-STU-001` | `p47.testa@student.lgu.edu.pk` | Staff @ Student Cafeteria (role changed during Test D) | **suspended** — reason "Phase 47 E2E test cleanup - test account suspended after verification." |
| `P47-STF-001` | `p47.testb@lgu.edu.pk` | Staff @ Faculty Cafeteria (reassigned during Test E) | **suspended** — same reason |
| `P47-MGR-001` | `p47.testc@lgu.edu.pk` | Manager @ Faculty Cafeteria (lifecycle tested in Test F) | **suspended** — same reason |

- Rejected attempts (Test G) created **no records**.
- The 12 seed accounts are untouched, including the protected `admin@lgu.edu.pk`, `dr.sana.malik@lgu.edu.pk`, `dr.imran.chaudhry@lgu.edu.pk` (only read/listed, never mutated).
- The three P47 records are clearly identifiable (`Phase47 …` names, `P47-…` IDs) and inactive; they can be deleted later only if/when the product gains an admin user-deletion workflow (listed as a remaining gap).

---

## 12. Remaining Gaps / Out of Scope (unchanged or newly noted)

1. **Menu item image upload**, **cafeteria creation UI**, **notification broadcast**, **reports expansion**, **refund rejection flow**, **settings backend**, **profile editing**, **audit-log UI**, **pagination** — all deferred to later phases per mission; not touched.
2. **Production container runs pre-Phase-47 code** — the Docker `uniserve_api` image was built before this phase; the Phase 47 API changes reach it only after the next image rebuild/deploy, which was explicitly out of scope (no deploy performed).
3. **Admin user deletion** — no application workflow exists to permanently delete test/erroneous members (only self-delete); suspend-and-document is the current terminal state.
4. **Pending-verification rows** show only View/Role actions (Suspend/Activate appear for active/suspended respectively) — deliberate status-gated UX; backend suspend semantics for pending users untested here.
5. **Toast a11y** — toasts lack `role="status"`/`aria-live` (Phase 46 component; minor follow-up).
6. **Frontend build** — pre-existing dual-React prerender failure (§9) remains out of scope.
7. Phase 43–46 working-tree deltas (mobile, menus, orders, other dashboard pages, deleted PHASE_22–41 reports, `package-lock.json` etc.) remain uncommitted exactly as inherited — **not** created or modified by Phase 47 beyond the files listed in §2–§3.

---

## 13. Phase 47 Files Changed

**Backend (2 modified, 1 new):**
- `apps/api/app/modules/auth/schemas.py` (M) — optional assignment fields + `model_validator` cafeteria rule on both request schemas
- `apps/api/app/modules/users/router.py` (M) — `_attach_cafeteria_info` + wiring in 6 endpoints + hardened `change_user_role`
- `apps/api/tests/test_phase47_user_management.py` (NEW) — 13 tests

**Frontend (2 modified pages, 2 modified libs/types, 5 new components, 1 new lib):**
- `apps/web/src/app/dashboard/admin/users/page.tsx` (M, rewritten) — "Members"
- `apps/web/src/app/dashboard/staff/page.tsx` (M, rewritten) — "Staff & Managers"
- `apps/web/src/lib/api.ts` (M) — user-management wrappers
- `packages/shared-types/src/index.ts` (M) — `User` fields + 4 admin request/response types
- `apps/web/src/components/admin/ModalShell.tsx` (NEW)
- `apps/web/src/components/admin/RoleBadge.tsx` (NEW)
- `apps/web/src/components/admin/AddMemberModal.tsx` (NEW)
- `apps/web/src/components/admin/ChangeRoleModal.tsx` (NEW, incl. E2E fix)
- `apps/web/src/components/admin/MemberDetailsModal.tsx` (NEW)
- `apps/web/src/lib/universityEmail.ts` (NEW)

**Report:** `PHASE_47_MEMBER_AND_STAFF_MANAGEMENT.md` (this file, NEW)

---

## 14. Stop Conditions

All mission stop conditions met: real Add Member workflow ✅ · P0 role-change bug fixed + backend-validated ✅ · assignments displayed & reassigned ✅ · real Staff & Managers page with suspend/activate ✅ · member list improvements ✅ · backend limited to exposure+validation ✅ · backend tests ✅ · type-check/lint/git checks ✅ · manual E2E A–H PASS ✅ · DB hygiene documented ✅ · report written ✅ · git inspected (HEAD unchanged, no commit, no push) ✅.

**Phase 48 (cafeteria creation, image upload, broadcast, reports expansion) was NOT started.** STOP.
