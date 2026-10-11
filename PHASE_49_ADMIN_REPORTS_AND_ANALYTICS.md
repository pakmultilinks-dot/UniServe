# Phase 49 — Admin Reports & Analytics

**Date:** 2026-10-05
**Branch:** `main` · **HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (unchanged)
**Commit:** NO · **Push:** NO · **Deploy:** NO · **Lockfile changed:** NO · **Dependency changes:** NO
**Scope:** Make the existing Admin Reports area a genuinely useful, production-quality reporting and analytics experience using the real backend data already available. No fake statistics, no unrelated business changes.

---

## 1. Discovery

Surveyed the existing reporting surface before writing any code.

**Backend report endpoints (all pre-existing, mounted at `/api/v1/reports`):**

| Endpoint | Data | Auth |
|---|---|---|
| `GET /sales` | Summary (orders, revenue, net, refunded) + `cafeteria_id` | report roles |
| `GET /sales/daily` | Daily revenue + paid orders | report roles |
| `GET /sales/by-cafeteria` | Per-cafeteria revenue rows | **ADMIN ONLY** |
| `GET /orders/summary` | Status / type / payment breakdowns + rates | report roles |
| `GET /orders/volume` | Daily + hourly order volume | report roles |
| `GET /orders/cancellation-rate` | Rate + reasons dict | report roles |
| `GET /cafeteria/{id}/performance` | Completion, cancellation, uncollected, preparation/ready/ETA averages | scoped |
| `GET /cafeteria/{id}/popular-items` | Top items by quantity (limit 1–50) | scoped |
| `GET /cafeteria/{id}/peak-hours` | Peak-hour histogram | scoped |

**Authorization (unchanged):** `_REPORT_ROLES = (UNIVERSITY_ADMIN, CAFETERIA_MANAGER, CAFETERIA_STAFF)`; `_resolve_cafeteria_scope` — admin may request any or none (all); manager/staff restricted to their assigned cafeteria. `cafeteria_assignments.user_id` carries a `UniqueConstraint` — each user has at most one assignment (schema-enforced); the router's multi-assignment branch is defensive only.

**Authoritative metric definitions (documented, never redefined by UI):**
- **Revenue** = `SUM(Payment.amount) WHERE SUCCEEDED` on orders in range; **net** = revenue − succeeded refunds. Money in paisa; web formats as `Rs. X` via `amount/100` `en-PK`.
- **Payment method** lives on `Order.payment_method` (the payments table has no method column).
- **Two "total orders" definitions, both authoritative:** `sales.total_orders` = PAID orders (≥1 succeeded payment); `orders/summary.total_orders` = ALL orders. UI labels disambiguate.
- Order statuses: PENDING / PREPARING / READY / COMPLETED / CANCELLED (5; no CONFIRMED).
- **No export/CSV backend contract exists** → export intentionally not implemented (follow-up, Section 13).
- **No chart library** in `apps/web` dependencies → SVG/CSS charts only, no new dependency (Section 8).

## 2. Reporting Model (what the dashboard consumes)

```
Admin Reports dashboard
├── All views (core, in parallel):
│   ├── GET /sales                    → KPI: revenue, net, refunded, paid orders, online/cash paid
│   ├── GET /orders/summary           → KPI: total/completed/cancelled, status/payment/type breakdowns, rates
│   ├── GET /sales/daily              → Revenue-by-day trend, daily detail revenue
│   ├── GET /orders/volume            → Order-volume trend, daily detail order counts, hourly strip
│   └── GET /orders/cancellation-rate → Cancellation reasons panel
├── All Cafeterias (admin only):
│   ├── GET /sales/by-cafeteria       → Cafeteria Performance comparison table
│   └── GET /cafeteria/{id}/popular-items (limit 50, per cafeteria) → merged Top Menu Items
└── Specific cafeteria:
    ├── GET /cafeteria/{id}/performance    → Performance StatTile panel
    └── GET /cafeteria/{id}/popular-items (limit 10) → Top Menu Items
```

All endpoints receive `{ start_date, end_date }` plus `cafeteria_id` when scoped. `peak-hours` is not consumed — `orders/volume.hourly` already covers hourly distribution for every view including All.

## 3. Dashboard Structure

`apps/web/src/app/dashboard/admin/reports/page.tsx` (rewritten in full, "use client"):

1. **Header** — title, description, cafeteria `<select>` (admin: includes "All Cafeterias"; manager: assigned only), segmented date presets (Today / 7 Days / 30 Days / Custom), Refresh button.
2. **Custom range inputs** — two `<input type="date">` with cross-constrained min/max, shown only for Custom preset; amber hint when start > end.
3. **Active-filter indicator** — "Showing {cafeteria} · {range}" always visible.
4. **KPI cards (8)** — Total Orders, Completed, Cancelled, Revenue, Net Revenue (+ refunded subtext), Avg Order Value (per paid order), Online Paid, Cash Paid.
5. **Trend grid** — Revenue by Day (sales/daily) + Order Volume by Day (orders/volume, all vs completed overlay), SVG `<title>` tooltips, first/mid/last axis labels.
6. **Cafeteria Performance** — All view (admin): comparison table (orders, revenue, completed, cancelled, refunded, AOV) from `sales/by-cafeteria`; specific view: StatTile panel from `cafeteria/{id}/performance`.
7. **Top Menu Items** — table (#, item, cafeteria column in All view, qty, revenue, orders); specific cafeteria uses its own endpoint; All merges per-cafeteria rows.
8. **Order Breakdown** — status bars (counts + % of total), payment method counts (explicitly labeled "order counts"), order type counts, completion/cancellation rate tiles.
9. **Cancellation Reasons** — backend `cancellation_reasons` dict, humanized labels, counts.
10. **Hourly Order Volume** — 24-column CSS strip with tooltips.
11. **Daily Detail** — scrollable table: date, orders, completed, cancelled, revenue (newest first, zero-days filtered out).
12. **Metric-definitions footnote** — backend terminology only; manager-scoping note for managers.

## 4. Date Filtering

- Presets: Today (`today..today`), 7 Days (`today-6..today`), 30 Days (`today-29..today`), Custom (two date inputs).
- All dates computed in **local calendar time** and sent as `YYYY-MM-DD` (never `toISOString()` UTC, which can shift the day).
- Backend receives explicit `start_date`/`end_date` on every report request — verified via network capture in E2E (Section 21): Today → `2026-10-05..2026-10-05`; 7 Days → `2026-09-29..2026-10-05`; 30 Days → `2026-09-06..2026-10-05`; Custom Oct 3–4 → `2026-10-03..2026-10-04`.
- Invalid custom range (start > end): request skipped, previous data kept, amber hint shown; the UI never fabricates data for an invalid range.

## 5. Cafeteria Filter

- Admin: "All Cafeterias" (default) plus every cafeteria, loaded dynamically via `getCafeterias()` — newly created cafeterias appear automatically, no hardcoded list.
- Manager: selector populated from `getMyCafeterias()` intersection with the cafeteria list; no "All" option; default = their single assigned cafeteria.
- Selecting a cafeteria scopes **every** request: core endpoints get `cafeteria_id` query param; performance/popular endpoints use the cafeteria path id.
- "All Cafeterias" omits `cafeteria_id` from core endpoints and adds `sales/by-cafeteria` + per-cafeteria popular-items (admin only).
- E2E evidence: Student → 23 orders / Rs. 2,080; Faculty → 24 / Rs. 1,800; All → 47 / Rs. 3,880 (Section 21, Test E).

## 6. Admin Scoping (authorization preserved)

- Backend authorization was **not** modified. `sales/by-cafeteria` remains admin-only; manager/staff remain restricted to assigned cafeterias by `_resolve_cafeteria_scope`.
- Frontend never trusts itself for authorization: the manager path simply omits "All", and any server 403 surfaces as the dedicated access-error banner — never as zeros or an empty report.
- Backend tests confirm: manager requesting unassigned cafeteria → 403 on sales/popular/performance (Test I); student/faculty/staff → 403 on all report endpoints (Test C); admin with bogus cafeteria UUID → 200 zeros (admin may request any scope) (Test I).
- Multi-assignment manager testing is impossible by design: `cafeteria_assignments.user_id` has a `UniqueConstraint` (verified in `users/models.py`) — the router's multi-assignment branch is defensive-only and unreachable (documented in `test_phase49_reports.py`).

## 7. KPI Cards

| Card | Source | Notes |
|---|---|---|
| Total Orders | `orders/summary.total_orders` | ALL orders (label + footnote disambiguate from paid-orders definition) |
| Completed / Cancelled | `orders/summary.status_breakdown` | green / red styling |
| Revenue | `sales.total_revenue` | succeeded payments in range |
| Net Revenue | `sales.net_revenue` | + "{refunded} refunded in period" subtext |
| Avg Order Value | `sales.total_revenue ÷ sales.total_orders` | presentational math on backend values; "per paid order" hint; 0 paid → Rs. 0 |
| Online Paid / Cash Paid | `sales.online_payment_volume` / `cash_payment_volume` | succeeded payment volumes by order payment method (Section 19) |

Every value originates from a backend report endpoint; nothing is hardcoded or estimated.

## 8. Trend Charts (no new dependency)

- `TrendChart`: pure SVG — zero-filled day axis, primary translucent bars + optional dark overlay (completed orders), `<title>` tooltips, min-height 2px for nonzero values, first/mid/last labels.
- `HourlyStrip`: 24 flex columns, height ∝ order count, per-hour tooltips, every-3rd-hour labels.
- `StatusBars`: CSS width bars for the 5 order statuses with counts and percentages.
- Constraint honored: no chart library added; lockfile untouched (hash verified, Section 24).

## 9. Cafeteria Performance

- **All Cafeterias (admin):** `sales/by-cafeteria` rows rendered as a comparison table. New backend fields `completed_orders`/`cancelled_orders` provide the status columns without N+1 performance calls (Section 19). AOV is presentational (`revenue ÷ order_count`).
- **Specific cafeteria:** `cafeteria/{id}/performance` StatTiles — total orders, completion rate (+ completed count hint), cancellation rate (+ cancelled count hint), uncollected orders, avg preparation / time-to-ready / ETA minutes (null → "—").
- E2E: performance panel appears only for a specific cafeteria; comparison table appears only in admin All view (Test E).

## 10. Top Menu Items

- Specific cafeteria: `cafeteria/{id}/popular-items` with `limit=10`.
- All Cafeterias (admin): per-cafeteria call with `limit=50` (backend caps at 50), then **client-side merge** keyed by `menu_item_id ?? item_name`, summing quantity/revenue/order_count, joining cafeteria names, sorted by quantity desc, sliced to top 10.
- The merge is presentational ordering/aggregation of authoritative backend aggregates — each cafeteria has far fewer than 50 selling items, so the merge is exact at current scale (documented limitation otherwise).
- Same-named items at different cafeterias remain distinct rows (they have distinct `menu_item_id`s and unit prices); the cafeteria column disambiguates — visible in E2E (Gulab Jamun at Student Rs. 100 vs Faculty Rs. 110).
- Per-cafeteria failures inside the All merge degrade to `items: []` for that cafeteria without breaking the whole section.

## 11. Status / Payment / Type Breakdowns

- Status bars: pending / preparing / ready / completed / cancelled with counts and % of `orders/summary.total_orders`.
- **Payment method: order counts, not volumes** — explicitly labeled in UI and footnote. Live evidence: Cash 42 / Online 5 order counts, while Online Paid volume = Rs. 0 (the 5 online orders have no succeeded payments).
- Order type: immediate 38 / scheduled 9 in live data.
- Completion rate 19.1%, cancellation rate 55.3% from backend rates.
- Cancellation reasons: backend dict (unspecified 2, cancelled by customer 4, payment-flow cleanup 3, automatic expiry 4, cleanup 2, no longer needed 2, plans changed 1, acceptance test cancellation 1).

## 12. Detailed Table

- Daily Detail: date, orders, completed, cancelled, revenue — merged from `orders/volume.daily` + `sales/daily` by date, zero-filled then filtered to days with activity, newest first, sticky header in a max-height scroll container.
- Live evidence: Oct 4 → 4/1/3/Rs. 320; Oct 3 → 7/1/5/Rs. 640; Oct 2 → 36/7/18/Rs. 2,920 (sums: 47 orders, 9 completed, 26 cancelled, Rs. 3,880 — matches DB baseline exactly).

## 13. Export

**Not implemented — by design.** No export/CSV contract exists anywhere in the backend (discovery confirmed), and Phase 49 constraints allow export "only if existing backend capability". Building an export subsystem is explicitly a STOP-scope item. Documented as a follow-up requiring a backend endpoint first.

## 14. API Client (`apps/web/src/lib/api.ts`)

Added typed wrappers in the reports section (errors propagate as `ApiClientError`):
`getSalesReport` (unwraps `raw.summary`, `?? 0` defaults incl. new volume fields), `getDailySalesReport`, `getSalesByCafeteriaReport`, `getOrderSummaryReport`, `getOrderVolumeReport`, `getCancellationRateReport`, `getPopularItemsReport`, `getCafeteriaPerformanceReport`, plus `ReportRangeParams` and `SalesReportSummary` types. Shared `reportQuery(params?)` helper. No other consumers of the touched functions existed (grep-verified).

## 15. Shared Types (`packages/shared-types/src/index.ts`)

Additive optional fields only — no existing field changed:
- `SalesSummary += online_payment_volume?: number, cash_payment_volume?: number`
- `CafeteriaSalesRow += completed_orders?: number, cancelled_orders?: number`
- All other report interfaces already existed. Dist rebuilt successfully (`tsc` clean).

## 16. Error / Loading / Empty States (Phase 46 machine preserved)

- **Loading:** skeleton KPI cards + chart block (no false numbers during load).
- **Load error:** `LoadErrorState` with retry via `reloadKey` — API failures never render as zeros or as an empty report.
- **Access error (403):** distinct amber banner ("You don't have access to this cafeteria's reports… Manager reports are scoped to your assigned cafeteria.") — never conflated with load errors.
- **Empty:** `EmptyState` ("No orders found for this period…") shown only after a **successful** response with no data — empty ≠ error.
- Cafeteria-list failure gets its own `LoadErrorState` with independent retry (`cafReloadKey`).
- E2E Test G: simulated 500s on `/reports/**` produced "Unable to load report." + Try again (no zeros anywhere); after unroute + retry, real data restored.

## 17. Filter UX

- Segmented preset control with active-state highlight; cafeteria `<select>` with aria-label; custom date inputs with cross-constraints; active-filter indicator always visible; Refresh button re-fetches with current filters.
- **Persistence:** selections (preset, cafeteria, custom range) persist across reloads via `sessionStorage` (`uniserve.admin.reports.filters`). Restore is **validated**: preset must be one of the four; custom range must be non-empty and start ≤ end; stored cafeteria must still be visible to the user (stale/deleted assignment falls back to All/first-visible). A `filtersRestored` ref gates the save effect so mount-time state never clobbers storage before restore reads it. Fresh visitors get defaults (7d + All Cafeterias for admin).
- E2E Test H: Student + 7 Days → reload → both reapplied (23 orders / Rs. 2,080); cleared storage → defaults (47 / Rs. 3,880); bogus stored cafeteria id → safe fallback to All.

## 18. Performance / Race Safety

- `requestSeq` ref: every report fetch increments the sequence; stale responses (older `reqId`) are discarded before any state write — rapid filter switches cannot paint outdated data.
- Core endpoints fetched in one `Promise.all`; performance + popular fetched in a second parallel batch; per-cafeteria popular fetches run concurrently in All view.
- Backend `by-cafeteria` gained `completed_orders`/`cancelled_orders` specifically to avoid an N+1 of performance calls for the admin comparison table.
- Custom invalid range short-circuits the effect without a request.

## 19. Backend Changes (minimal, justified, additive)

Only two changes, both additive schema fields on existing endpoints — Phase 19 style:

1. **`GET /sales` summary += `online_payment_volume`, `cash_payment_volume`** — succeeded payment volume by `Order.payment_method` (mirrors the existing `administration/overview` query pattern exactly; that endpoint is university-wide only, so cafeteria-scoped KPI cards could not reuse it). Needed for the Online/Cash Paid KPI cards under cafeteria filtering.
2. **`GET /sales/by-cafeteria` rows += `completed_orders`, `cancelled_orders`** — status counts per cafeteria via a grouped `stat_q` merged by `cafeteria_id`; needed for the admin comparison table columns without N+1 performance requests.

No new endpoints. No auth changes. No DB migrations. No changes to any non-reports module. `test_reports.py` contains no exact-equality JSON assertions → additive fields are schema-safe (full suite green).

## 20. Backend Testing (A–M) — `apps/api/tests/test_phase49_reports.py`

24 tests, **all passing**. Seed helper `_seed_order` (unique order numbers via global sequence, deterministic user id, per-order payment with unique idempotency key) + `_seed_refund`. Coverage:

| Test | Result |
|---|---|
| A Admin access — volume fields present/correct (30k/20k/10k split), summary keys, by-cafeteria both names, performance + popular 200 | PASS |
| B Manager scope — assigned 200, single-assignment auto-scope 200, unassigned 403, by-cafeteria 403 (multi-assignment impossible: UniqueConstraint) | PASS |
| C Non-admin denied — student/faculty/staff × sales, orders/summary, by-cafeteria → 403 | PASS |
| D–F Date filters — today isolates 1 order/5000; 7d excludes 10-days-ago order; custom _d(4).._d(1) → 2 orders/10000; future range → 200 zeros incl. volume fields | PASS |
| G All-cafeteria aggregate — total revenue == sum of per-cafeteria; by-cafeteria counts (completed/cancelled) correct | PASS |
| H Specific-cafeteria isolation — scoped revenue/orders/items/quantities only | PASS |
| I Access bypass — manager assigned A requesting B → 403 on sales/popular/performance; admin bogus UUID → 200 zeros | PASS |
| J Order totals — statuses/types/rates; sales paid-orders (3) vs summary all-orders (4) distinction | PASS |
| K Revenue totals — succeeded only; pending/failed payments excluded; succeeded refund counted, pending refund excluded; net correct; scoped | PASS |
| L Payment breakdown — counts vs volumes distinction (pending-payment order counted in breakdown, excluded from volume); scoped volumes | PASS |
| M Top items — qty/revenue/order_count; limit=1 returns top; out-of-range orders excluded → empty list | PASS |

Full suite: **743 effective passes, 0 regressions** (one apparent failure was a leaked `$env:POSTGRES_PASSWORD` from the Phase 48 uvicorn session leaking into `test_config_production_guards`; env cleared → 21/21 pass — environmental, not a regression).

## 21. Real UI E2E (A–H) — live DB (`uniserve_prod`), uvicorn :8001 + web :3000, admin login

| # | Scenario | Evidence | Result |
|---|---|---|---|
| A | Reports load real data | Default view (All + 7d): Total 47, Completed 9, Cancelled 26, Revenue Rs. 3,880, Net Rs. 3,880, AOV Rs. 431, Online Paid Rs. 0, Cash Paid Rs. 3,880 — **exact match to DB baseline**; revenue-by-day 292,000+64,000+32,000 paisa; volume 36/7/4 orders; hourly sums to 47; all tables rendered; footnote present; no console-breaking errors | PASS |
| B | Today | Network: all endpoints carry `start_date=2026-10-05&end_date=2026-10-05` (no `cafeteria_id` in All view; per-cafeteria popular-items for all 3 cafeterias); UI shows genuine "No orders found for this period" (live DB has 0 orders on 2026-10-05) | PASS |
| C | 7 days | `2026-09-29..2026-10-05`; 47 orders; "Sep 29 – Oct 5" | PASS |
| D | 30 days | `2026-09-06..2026-10-05`; 47 orders; "Sep 6 – Oct 5" | PASS |
| E | Cafeteria filter | Student: `cafeteria_id` on all 5 core endpoints + performance + popular(limit=10), no by-cafeteria call → 23/5/11/Rs. 2,080/Rs. 416 AOV; Faculty → 24/4/15/Rs. 1,800/Rs. 450 + performance tiles rendered; All → by-cafeteria called once, no scoped params, comparison table 2 rows, back to 47/Rs. 3,880 — data changes appropriately at every step | PASS |
| F | Empty state after successful no-data response | Covered by Test B (200 + zero rows → EmptyState, not an error, not zeros) | PASS |
| G | Error state + retry | `page.route` intercept `**/reports/**` → 500 → LoadErrorState ("Unable to load report." + Try again), **no misleading zeros**, filter indicator intact; unroute → Try again → full real data restored (47/Rs. 3,880) | PASS |
| H | Reload persistence | Student + 7 Days → reload → "Showing Student Cafeteria · Sep 29 – Oct 5", KPIs 23/5/11/Rs. 2,080, preset button active, sessionStorage valid; cleared storage → defaults All + 7d + 47 orders; bogus stored cafeteria id → validated fallback to All (no error) | PASS |

Bonus: Custom preset Oct 3–4 → `2026-10-03..2026-10-04` → 11 orders / 2 completed / 8 cancelled / Rs. 960 — cross-checks against the daily-detail rows exactly.

## 22. Data Integrity (live DB, before == after)

| Table / check | Baseline (pre-Phase 49) | After | Match |
|---|---|---|---|
| users | 15 | 15 | ✓ |
| orders | 47 (2026-10-02..04) | 47 (2026-10-02..04) | ✓ |
| cafeterias | 3 | 3 | ✓ |
| menu_items | 32 | 32 | ✓ |
| order_items | 46 | 46 | ✓ |
| refunds | 0 | 0 | ✓ |
| menu image URLs (`/api/v1/static/food/%`) | 27 | 27 | ✓ |
| p47.testa/b/c | suspended | `status=suspended` ×3 | ✓ |

Phase 49 is read-only against the live database: no rows created, updated, or deleted. Backend tests ran against the ephemeral test database only.

## 23. Build & Quality Checks

- **Type-check:** `npm run type-check:web` → clean (one iteration fix: Map-iterator spread → `Array.from` for the web target's ES5 downlevel).
- **Lint:** eslint on both changed web files → exit 0 (only pre-existing plugin warnings: unsupported TS version notice, pages-directory notice from root config).
- **Build attempt:** `next build` fails **identically to the pre-Phase 49 baseline** — styled-jsx `StyleRegistry` crash prerendering the stock `/_error` pages `/404` and `/500` (dual React 19 root + React 18 web), plus the harmless `patchIncorrectLockfile` TypeError. All 24 pages generated before the stock error-page export failure. Pre-existing environment issue; documented, deliberately not "fixed" (dependency changes are out of scope).
- **Lockfile:** `package-lock.json` SHA-256 `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A` — **identical before and after** (its dirty status is inherited from Phases 43–48).
- **`git diff --check`:** clean except the pre-existing LF→CRLF warning on `apps/mobile/package.json` (inherited).

## 24. Git Safety

- HEAD: `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` — **unchanged**.
- Branch: `main`.
- **Commit: NO. Push: NO. Reset/Clean: NO.**
- Phase 49 files in the working tree:
  - `apps/api/app/modules/reports/schemas.py` (M — additive fields)
  - `apps/api/app/modules/reports/service.py` (M — volume + status-count queries)
  - `apps/api/tests/test_phase49_reports.py` (new — 24 tests)
  - `packages/shared-types/src/index.ts` (M — additive optional fields)
  - `apps/web/src/lib/api.ts` (M — typed report wrappers)
  - `apps/web/src/app/dashboard/admin/reports/page.tsx` (M — full dashboard rewrite)
- All other dirty entries are inherited from Phases 43–48 and untouched (deletions of PHASE_22–41 docs, auth/menus/orders/users modules, mobile files, other dashboard pages, migrations 0010/0011, phase44/47/48 tests, `package-lock.json`, etc.).

## 25. Known Limitations & Follow-ups

1. **Export** — no backend contract exists; requires a new backend endpoint before any UI work (Phase 49 STOP-scope: no large export subsystem).
2. **Online Paid volume = Rs. 0** in live data — truthful: there are zero succeeded online payments in the production DB (5 online orders, none paid). The KPI will populate automatically as online payments occur.
3. **Payment-method breakdown = order counts** (backend semantics), distinct from payment volumes — both shown and explicitly labeled; not reconciled into one number because they measure different things.
4. **Two "total orders" definitions** — sales (paid) vs orders/summary (all) — both authoritative; UI labels and footnote disambiguate rather than silently picking one.
5. **`peak-hours` endpoint not consumed** — `orders/volume.hourly` covers hourly distribution for all views including All; adding it would duplicate data.
6. **All-view top-items merge is per cafeteria (limit 50)** — exact at current scale (each cafeteria ≪ 50 selling items); if a cafeteria ever sells > 50 items, its contribution would truncate (backend limit is the contract).
7. **Dual-React build failure** — pre-existing at HEAD; fixing requires dependency changes, explicitly out of scope.
8. **Filter persistence is per-tab** (`sessionStorage`) — deliberate choice; stale cafeteria ids are validated on restore.

---

**Phase 49 complete. STOP — Phase 50 not started.**
