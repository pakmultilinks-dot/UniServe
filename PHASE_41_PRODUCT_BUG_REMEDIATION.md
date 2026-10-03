# Phase 41 — Focused Product Bug Remediation

**Scope**: Fix exactly the three product bugs found during Phase 40 real-world acceptance. No deploys, no VPS/DNS/EAS/JazzCash/SMTP work, no redesign, no dependency upgrades, no changes to unrelated behavior or business rules.

**Starting commit**: `8dd1506` (Phase 40 real-world product acceptance, `main`)
**Final commit**: `fix: close product acceptance cancellation and inventory gaps` (this report + all changes below)

---

## Bug 1 — P1: Menu items creatable without inventory record

**Root cause**: `MenuService.create_menu_item` (`apps/api/app/modules/menus/service.py`) inserted the `MenuItem` row but never created a matching `InventoryItem`. Checkout later calls `_reserve_inventory`, which hard-fails with `No inventory record for item {id}` for any item created through the admin/manager API (web console "Add Item" uses exactly this endpoint). Pre-existing items were only orderable because their inventory rows had been seeded or added manually.

**Fix**:
1. `menus/service.py` — after flushing the new `MenuItem`, auto-create an `InventoryItem` for the same `(cafeteria_id, menu_item_id)` with `quantity=0`, `unit=portions`, `low_threshold=10`. Staff restock before sale; checkout therefore correctly fails only when stock is genuinely zero.
2. `inventory/service.py` — `create_inventory_item` now upserts: if an inventory row for the same `(menu_item_id, cafeteria_id)` exists it is updated (quantity/unit/low_threshold) instead of inserting a duplicate. This prevents `MultipleResultsFound` 500s in checkout's `scalar_one_or_none` when staff explicitly POST `/inventory/` for an auto-created row.

**Regression tests** (`apps/api/tests/test_menus.py`, both PASS, both discriminate — reverting the menus fix makes them fail):
- `test_create_menu_item_auto_creates_inventory` — manager POST `/menu-items` → exactly one inventory row, quantity 0, unit `portions`, low_threshold 10.
- `test_create_inventory_after_auto_create_upserts` — manager POST menu-item → POST `/inventory/` (quantity 60) → 201, quantity 60, still exactly one row.
- `apps/api/tests/test_orders.py::TestMenuItemInventoryGap::test_api_created_item_checkout_after_restock` — manager creates item via API → inventory auto row 0 → adjust +40 → student cart + checkout → **201** (pre-fix: 400 `No inventory record for item ...`), inventory decremented to 38.

**Live evidence (real web + mobile UI)**:
1. Web console (admin) → Cafeterias → Student → Menu → **Add Item** → "Phase41 Karahi" (main_course, PKR 320) → POST 201.
2. DB: menu item `29672b59-3081-412d-a18c-ea2222f7d343`; inventory row `5536983a-87c9-46f8-8ce9-3d65c22ee65f` auto-created, quantity 0, unit portions, threshold 10 — **exactly one row**.
3. Published menu interaction (rule respected): published menus are immutable (400 "Cannot modify a published or archived menu") — correct business rule, not weakened. Resolution: via the real web workflow, **Create Draft for Today** (Student, Oct 3) → added Phase41 Karahi + Chicken Roll → **Publish** → "Published — students see this menu today". Mobile home renders `/daily-menus/today`, so the item went live immediately.
4. Web console → Inventory → row 29672b59 "0 portions · out of stock" → **Adjust +20** → "20 portions · active".
5. Mobile (student ayesha.khan) home → Phase41 Karahi PKR 320 → item detail "Available now" → Add → cart → checkout → **Place Order → Order #37 created** (pre-fix this exact path failed with `No inventory record`). Web admin Order Queue shows **#37 pending · 1× Phase41 Karahi · PKR 320**. DB: inventory 20 → 19 (reservation) → 20 again after cancel (release).

---

## Bug 2 — P2: Mobile customer cancellation UI missing

**Root cause**: The backend endpoint `POST /orders/{id}/cancel` was fully functional (pending-only, 30-minute scheduled deadline, reason + audit), but the mobile app had no customer-facing cancel action — the only way to cancel was staff/admin tools.

**Fix** (no backend changes; policy untouched):
- `apps/mobile/src/services/data.ts` — `cancelOrder(orderId, reason?)` → `POST /orders/${orderId}/cancel`.
- `apps/mobile/app/(app)/order/[id].tsx` — pending-only inline confirmation card: collapsed "Cancel Order" row → expands to "Yes, cancel" / "Keep order"; on success refreshes order state; on error surfaces the API error message inline. The control renders **only** when `order.status === "pending"` — terminal/preparing orders show no cancel affordance.

**Live evidence**:
- Order #37 (pending) → "Cancel Order" → "Cancel this order?" → **Yes, cancel** → banner "This order was cancelled", button removed. DB: status `cancelled`, reason "Cancelled by customer", `cancelled_at` 2026-10-03 03:32:26 +05.
- Order #38 (pending → staff confirm + preparing via the real staff endpoints `POST /orders/{id}/confirm`, `PUT /orders/{id}/status`) → mobile detail shows **Preparing** active and **no Cancel Order button** — the status gate works.
- No backend cancellation rules were invented or weakened; the endpoint's own validations were left exactly as-is.

---

## Bug 3 — P2: Scheduled-order cancellation rejected for same-day local slots (timezone)

**Root cause**: `OrderService.checkout` stored `order_date = date.today()` — the **naive server date** — while `scheduled_collection_time` is cafeteria-local wall time. `_check_scheduled_cancellation_deadline` correctly combines `(order_date, slot)` in the cafeteria timezone and compares against now, so when the server ran in UTC the order date could be one day behind the cafeteria's local date; every same-day slot then computed a deadline already in the past and cancellation was rejected with `Cancellation deadline has passed` (Phase 40 order #35).

**Fix**: `orders/service.py` — checkout now computes `local_order_date = datetime.now(ZoneInfo(cafeteria.timezone)).date()` (UTC fallback if the timezone string is invalid) and stores `order_date=local_order_date`. `_validate_published_menu`'s naive `date.today()` and other naive-date sites were **out of scope** (see Known Issues) — the acceptance bug was the cancellation deadline, and only that was fixed.

**Regression tests** (`apps/api/tests/test_orders.py`, frozen clock via monkeypatched `service.datetime`/`service.date`; all PASS; reverting the fix → 3/4 fail with the exact Phase 40 signature `Cancellation deadline has passed`):
- `TestScheduledOrderDateLocalTimezone` — frozen 2026-10-02 23:30 UTC (= 04:30 PKT Oct 3): immediate + scheduled orders store `order_date == "2026-10-03"` (cafeteria-local, not UTC Oct 2); cancel of a 05:00 slot (deadline 04:30 PKT) succeeds exactly at the boundary; cancel succeeds before the local deadline and is rejected after it with `deadline` in the detail.

**Live evidence (container aligned to `Asia/Karachi` — see Environment Notes)**:
- Order #39 — mobile checkout, "Schedule collection", slot **08:00 same day** (the Phase 40 bug case) → 201, DB `order_date = 2026-10-03`, slot 08:00 → mobile **Cancel Order → cancelled successfully** (deadline 07:30 PKT still future). Pre-fix, the UTC date (Oct 2) made this exact flow fail.
- Policy preserved: API-scheduled order #40 with slot **04:15** (~20 min ahead) → cancel → **400 `Cancellation deadline has passed. Orders can cancelled up to 30 minutes before the scheduled collection time.`** — the rule itself is intact; only the wrong-date false rejection was removed.

---

## Web → Mobile real-world verification (summary)

| # | Flow | Result |
|---|------|--------|
| 1 | Web admin Add Item → DB auto-inventory row (0/10/portions, exactly 1) | ✅ |
| 2 | Web: draft today's menu → add items → publish (published menus immutable, rule respected) | ✅ |
| 3 | Web: inventory Adjust +20 → restocked | ✅ |
| 4 | Mobile student: item visible on today's menu → cart → checkout → **Order #37** (P1 path) | ✅ 201 |
| 5 | Web admin Order Queue: #37 pending visible (staff-queue proof) | ✅ |
| 6 | Mobile: cancel #37 (pending) → cancelled banner + DB cancelled/reason/at | ✅ |
| 7 | Staff: confirm + preparing #38 → mobile shows no cancel button (status gate) | ✅ |
| 8 | Mobile: scheduled 08:00 same-day → Order #39 → `order_date=2026-10-03` → cancel OK (TZ fix) | ✅ |
| 9 | API: scheduled 04:15 → cancel → 400 deadline (policy preserved) | ✅ |
| 10 | Isolation: student switcher lists only Student Cafeteria (backend role filter); DB faculty Oct-2/Oct-3 menus have no Phase41 Karahi; item belongs to student cafeteria with exactly 1 inventory row | ✅ |

**DB evidence block**: orders 37 cancelled (reason) / 38 preparing / 39 cancelled (reason) / 40 pending — all `order_date=2026-10-03`; inventory for Phase41 Karahi: 18 portions, threshold 10, exactly one row; student Oct-3 published menu (2 items, includes Phase41), student Oct-2 (16 items, none); faculty Oct-2 (12) / Oct-3 (1) — none includes Phase41.

---

## Test results

- **Focused**: `tests/test_menus.py tests/test_orders.py tests/test_inventory.py` → **103 passed** (includes the 6 new regression tests).
- **Full backend**: `pytest` in `apps/api` → **656 passed** (650 baseline + 6 new), 0 failed.
- **Discrimination proven**: with each fix reverted to pre-fix code, the corresponding new tests fail with the exact Phase 40 failure signatures (400 `No inventory record for item ...`; `AssertionError` on auto-inventory; `Cancellation deadline has passed` on frozen-clock timezone tests).
- **Builds / type-checks**: `npm run type-check:all` (shared build + web `tsc --noEmit` + mobile `tsc --noEmit`) passed; web production build (Next.js static export) succeeded.
- Mobile has no test runner — its regression coverage is the API-level tests above plus the real UI verification chain; documented honestly rather than inventing a mobile test harness.

## Known issues (out of scope, unchanged)

- Naive `date.today()` sites remain in `orders/service.py` (`_validate_published_menu` ~line 1314, listing cutoff ~line 293, `mark_ready` closing check ~line 835) — same bug class as Bug 3 but not part of the three acceptance bugs; fixing them belongs to a future phase.
- Web console client-date daily-menu panels can disagree with server-resolved today during UTC/PKT divergence (environment quirk, see below).
- Web console Order Queue is a read-only overview; kitchen transitions run through staff-role API endpoints (`POST /orders/{id}/confirm` with `notes`, then `PUT /orders/{id}/status`) — by design in this console, not a regression.
- Inventory table "Item" column renders the raw `menu_item_id` instead of the item name — cosmetic, out of scope.
- `POST /cafeterias/{id}/inventory/` now upserts on `(menu_item_id, cafeteria_id)` instead of erroring on duplicates — intentional consequence of Bug 1's fix (duplicate rows would break checkout).
- **Environment quirk (not a repo change)**: the production API container originally ran UTC while host + Postgres are Asia/Karachi (PKT), which made server-resolved "today" lag the cafeteria's local date by 5 hours — this amplified Bug 3 in the live environment. Mitigated locally by appending `TZ=Asia/Karachi` to the gitignored `.env.production` (compose `env_file`); the backend code fix (cafeteria-local `order_date`) is what actually closes the bug regardless of container TZ. Backend code is baked into the image — future backend edits require `docker compose -f docker-compose.prod.yml up -d --build api`.

## External prerequisites (explicitly NOT part of this remediation)

- SMTP / email delivery, JazzCash (or any online-payment provider), VPS/DNS/EAS configuration — all deferred to their respective phases; online-payment and notification flows were not touched.

---

## Conclusion

All three Phase 40 acceptance bugs are closed at the root cause with regression tests that discriminate against the pre-fix code, full backend suite green (656 passed), builds/type-checks green, and a complete live Web→Mobile verification chain executed against the production-compose stack. Cancellation policy, published-menu immutability, and cafeteria isolation were verified unchanged. Working tree committed locally on `main` — **not pushed**.
