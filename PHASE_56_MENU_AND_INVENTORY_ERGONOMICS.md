# Phase 56 — Menu & Inventory Ergonomics: Acceptance Report

**Status:** COMPLETE · **Date:** 2026-10-07 · **Baseline HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (0 commits, tree left dirty) · **Phase 55:** closed, untouched.

## Scope Delivered (5 features)

| # | Feature | Backend | Web | Mobile |
|---|---------|---------|-----|--------|
| 1 | Copy Previous Day's Menu | `POST /daily-menus/copy` (201; 400 same-date, 404 missing source, 409 occupied target; skips inactive items; copies junction metadata; audit `daily_menu_copied`) | Copy Previous Day button + modal (source preview, date pickers, success state, 409/400 surfaced) | n/a |
| 2 | Menu Item Delete | `DELETE /menu-items/{id}` admin-only soft-delete (is_active/is_available false; junction+inventory rows persist; orders use snapshot cols) | Admin-only Delete on cards + confirm modal with history note | n/a |
| 3 | Inventory Creation/Reachability | `POST /cafeterias/{id}/inventory/` upsert (manager/admin; units portions/kg/g/L/mL/pcs) | Add Item button + create modal (catalog of addable items, unit dropdown, validation) | n/a |
| 4 | Inactive Cafeteria Filtering | `GET /cafeterias/?is_active=` | Menu/inventory selectors + home/broadcasts/orders/staff use `{isActive:true}`; admin cafeterias/users/overview/reports keep full list by design | n/a |
| 5 | Dietary/Allergen Info | Text columns on menu_items (no migration); update path `is not None` (clears with ""/JSON strings) | Edit form toggle-chips + card chips (emerald dietary, amber allergens); Copy modal preserves metadata | `formatTags` JSON parse + humanized render on item detail |

Typechecks: **web tsc EXIT=0**, **mobile tsc EXIT=0**. Lint = pre-existing `next/dist/compiled/babel/eslint-parser` failure (unchanged, documented).

## Tests

- `apps/api/tests/test_phase56_menu_inventory.py`: **23 passing** (copy happy/400/404/409/skip-inactive/metadata, delete admin-only + soft-delete semantics, inventory upsert + unit validation, cafeteria is_active filter).
- Full backend regression: **849 passed** (baseline 826 + 23).

## E2E Verification (live stack :8001 API / :3000 web / Postgres :5433)

Fixtures via `phase56_e2e_setup.py` (idempotent, urllib): E2E cafeteria `50d67d4b…`, inactive probe `a7641b13…`, items Sandwich `c343f85d…` / Lassi `6bbfea95…` / Delete Probe `75fd0527…`, source menu 2026-10-06, target menu 2026-10-07.

- **A — Copy previous day ✅**: unpublish today's published menu via UI → Copy Previous Day → success state *"Draft created for 2026-10-07 with 3 items."* API verify: draft on 2026-10-07 with 3 items, metadata preserved (special_price 23000 on Sandwich, display_order 1/2/3, availability T/T/F); source 2026-10-06 **still published, unchanged**; original today menu archived; today's section renders the draft (PKR 230 special price honored, #3 closed).
- **B — Conflict protection ✅**: copy onto an occupied published date → exact backend message surfaced: *"Daily Menu already exists: … date=2026-10-07 already has a PUBLISHED menu — unpublish it first or choose another date"*; nothing overwritten.
- **C — Item delete ✅**: Delete Probe deleted via UI; confirm modal history text verified; card leaves the grid. API: active listing excludes item; row `is_active=false/is_available=false`. DB: 3 junction rows persist (source menu still lists all 3 items — history intact); orders=52; order_items referencing probe=0. *Cosmetic note:* the soft-deleted item's remaining inventory row renders as "Item 75fd0527…" (web resolves names from the active-only listing; backend responses carry no item name) — pre-existing resolution pattern, documented.
- **D — Inventory creation/reachability ✅ (upsert path)**: Add Item modal opens, loads catalog, validates; EmptyState *"Every active menu item already has an inventory record"* shown because `create_menu_item` auto-provisions an inventory row per item (P1 invariant, `menus/service.py` L166–181) — 0 addable items exist DB-wide, so the empty state is correct by design. Upstream endpoint exercised directly: POST upsert → 201, idempotent re-upsert → 201, DB row updated in place (qty 20 / portions / threshold 5), UI table reflects *"20 portions … active"*; invalid unit → 422 enum; staff/student → 403.
- **E — Inactive filtering ✅**: menu + inventory selectors (browser) and admin home show only the 3 active cafeterias — inactive probe absent; admin cafeterias page lists probe as **Inactive** with Activate button; API `?is_active=false` includes probe, `?is_active=true` excludes it.
- **F — Dietary/allergen roundtrip ✅**: Edit Sandwich → toggled vegetarian→**halal**, milk→**peanuts** → Save → card chips update immediately; API GET roundtrip: `dietary=["halal"] allergens=["wheat","peanuts"]` (JSON arrays intact).
- **G — Role separation ✅**: staff (ahmed.raza) menu page shows **no Copy Previous Day / Delete / Add Item / Publish**; selector scoped to assigned cafeteria only. Student (ayesha) never reaches dashboard — redirected to `/mobile-required`. API RBAC: staff/student copy 403, delete 403, inventory upsert 403 (delete message admin-only).
- **H — Regression spot-checks ✅**: Orders Console ("Order Queue"), Notifications, Refund Management, Settings, Audit Log pages all load. ("failed" match on audit page = its own filter-option labels — false positive avoided.)

## Data Safety (BEFORE → AFTER, live DB `uniserve_prod`)

| Table | Before | After | Delta |
|---|---|---|---|
| users | 17 | 17 | 0 |
| cafeterias | 3 | 5 | +2 (Phase 56 E2E + inactive probe) |
| orders | 52 | 52 | **0** |
| refunds | 3 | 3 | 0 |
| payments | 39 | 39 | 0 |
| notifications | 143 | 143 | 0 |
| menu_items | 32 | 35 | +3 (Phase 56 items) |
| daily_menus | 13 | 16 | +3 (source + archived + draft) |
| daily_menu_items | 51 | 60 | +9 (3 per menu × 3) |
| inventory_items | 32 | 35 | +3 (auto-provisioned) |
| security_audit_events | 692 | 733 | +41 (E2E auth/CRUD trail incl. `daily_menu_copied`) |

Phase 56 orders = 0, Phase 56 notifications = 0, probe cafeteria orders = 0. No existing cafeteria deactivated/deleted; no resets; test data labeled "Phase 56 …" only.

## Git

- HEAD `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee`, **0 commits** ahead of baseline.
- Root `package-lock.json` SHA256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A` unchanged; lockfile never touched.
- Dirty tree preserved (Phase 56 edits uncommitted, as required).

## Operational Gotchas Encountered (documented, not defects)

1. **Invoke-RestMethod + 307 trailing-slash redirect drops `Authorization`** → misleading `AUTHENTICATION_ERROR: Invalid authorization header` on collection GETs (`/daily-menus`, `/menu-items`, `/cafeterias/?…`). Fix: append trailing slash or use Python urllib probes (`phase56_e2e_probe.py`).
2. Console shows paired 401s on some navigations (RSC prefetch race) — pages recover and render; pre-existing platform behavior, unrelated to Phase 56.
3. Inventory "Add Item" creation modal is unreachable while every active item auto-provisions its row — by design (checkout P1 invariant); the flow remains valid for legacy/restored data and is covered by unit tests + the upsert probe above.

## Artifacts

- Backend: `apps/api/app/modules/menus/{service,router,schemas}.py`, `apps/api/app/modules/inventory/router.py`, `apps/api/app/modules/cafeterias/router.py`, `apps/api/tests/test_phase56_menu_inventory.py`
- Web: `apps/web/src/lib/api.ts`, `apps/web/src/app/dashboard/{menu,inventory,page}.tsx`, `dashboard/{orders,staff}/page.tsx`, `dashboard/admin/broadcasts/page.tsx`
- Mobile: `apps/mobile/app/(app)/item/[id].tsx`
- Scripts: `phase56_e2e_setup.py`, `phase56_e2e_probe.py` (untracked, Phase 56 labeled)
