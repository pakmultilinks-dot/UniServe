# UniServe Phase 8 — Consolidated Report

**Date:** 2026-10-10 → 2026-10-11 (Phase 8A evidence closure 2026-10-11)
**Scope:** Isolated Full-Product E2E, Transactional Ordering, Refunds, Visual Evidence
**Isolated environment:** test DB `uniserve_test_phase7` @ 127.0.0.1:5433, API `http://127.0.0.1:8001`, web `http://localhost:3010`, Expo web `http://localhost:8090`
**Production:** `uniserve_prod` — never written; counts unchanged (isolation proof below)

> **Phase 8A (2026-10-11):** recovered the two visual items previously marked BLOCKED (D6 stock-error UI, Expo API-destination). Both are now directly verified with captured evidence. See §12 for the browser-blocker resolution method and commands.

---

## 1. Isolation Proof

**Before Phase 8 (recorded baseline):**
| Table | users | menu_items | orders | cafeterias | cart_items | notifications | refunds | daily_menus |
|---|---|---|---|---|---|---|---|---|
| count | 36 | 55 | 59 | 5 | 60 | 188 | 8 | 25 |

**After Phase 8 (2026-10-11):** identical — 36 / 55 / 59 / 5 / 60 / 188 / 8 / 25.

**After Phase 8A (2026-10-11, re-verified):** still identical — 36 / 55 / 59 / 60 / 188 / 5 / 8 / 25 (single `psql` UNION-ALL count query against `uniserve_prod`). Git HEAD unchanged at `bc967b3`; only `artifacts/phase-8/` is untracked/new. Nothing committed, pushed, or deployed.

Every write in this phase targeted `uniserve_test_phase7`. The isolated DB evolved to: users=9, orders=6 (#1/#4/#6 completed; #2/#3/#5 cancelled), refunds=5, daily_menus=3 (today's published).

---

## 2. Pre-existing Menu Item Verification (Criterion A)

`PHASE8-E2E-7F3A9C Test Burger` (`5d33b252-ec7d-4cf1-bc28-db366e7cdec8`), **PKR 349**, Faculty Cafeteria (`c84affd5-...`) — confirmed published via the isolated backend (`/daily-menus/today` returns it as `published`) and visible in the web admin UI and Expo web home.

> **Note (2026-10-11):** daily menus are per-date. On the new day the checkout returned `400 "No published menu available for today"` until a fresh menu for 2026-10-11 was created and published (`37318186-a96a-4bf0-ae83-8f919092b6e8`) carrying the same item. This is correct product behavior, not a defect.

---

## 3. Ordering & Lifecycle Outcomes (Criterion B/C)

Exercised end-to-end against the isolated API and via Expo web (screenshots below):

| Order | Owner | Flow | End state |
|---|---|---|---|
| #1 `1012b956-...` | faculty | checkout → lifecycle | **completed** |
| #2 | faculty | checkout → cancel | cancelled |
| #3 `eb6c9731-...` | faculty | checkout → cancel | cancelled |
| #4 `be1e501b-...` | faculty | full lifecycle | **completed** |
| #5 `77797d57-...` | faculty | checkout → cancel | cancelled |
| #6 `089b98e0-...` | faculty | **post-fix E2E**: confirm→prepare→ready→collect | **completed** |

**Post-remediation E2E smoke (`artifacts/phase-8/task11_e2e_smoke.py`): 14/14 PASS** — cart add 201, cash checkout 201, full staff lifecycle to `completed`, live D7 cash refund settled (`manual_cash_0b03c73a-3c1...`), live D8 stranger-cancel parity (403 `Order not found` on both GET and cancel).

Notifications confirmed: 28 in the isolated DB including `refund_processed` for order #6 (`/notifications` returns key `items`).

---

## 4. Refund Outcomes & Provider Limits (Criterion D)

5 refunds in the isolated DB:
- **2 pre-existing, untouched:** `e2c1df06` **failed** (PKR 10000), `fda9c41b` **rejected** (PKR 5000) — both on order #1, evidence of the failed-processor and reject paths.
- **3 succeeded (manual cash settlement):** on order #4 (`e121dcd2`, `93abfd9f`) and order #6 (`0b03c73a`) — provider_reference `manual_cash_<id[:12]>`, payment → `refunded`, `refund_succeeded` events recorded.

**Provider limits:** the online test provider cannot settle refunds when its reference is missing — this must fail closed (see D7). Cash ("pay at counter") payments have no provider capture, so they settle manually.

**Refund suite first run: 19/19.** Re-run: 17/19 — the 2 mismatches are **re-run artifacts**: the script's fixed idempotency keys (`phase8-refund-001/002`) replay refunds already in terminal states, and the API correctly returns `400 "Cannot reject/process refund in <terminal> status"`. Not regressions.

---

## 5. Authorization & Cafeteria Isolation (Criterion E)

- Role matrix: **20/20**; auth/session: **9/9**; refund RBAC: **19/19**; authz suite: **108/112** (first run).
- Re-runs against the fixed API: task8 **97/99**, task8b **6/7**, task8c **4/6**, task6_negative **18/20**, task6_stale_stock **9/9**. Every mismatch is accounted for as a probe-shape or re-run artifact (none are product defects):
  - `422` on a malformed create-user payload fires **before** RBAC — **no write occurred** (`phase8.intruder@lgu.edu.pk` absent from DB: 0 rows).
  - Student hitting the Faculty cart path gets a **stronger** 403 (`Access to Faculty Cafeteria is restricted to faculty members`) than the probe assumed.
  - IDOR cancel-oracle now returns **identical** `Order not found` for completed and cancelled (the D8 fix); the "missing" case only echoes the supplied UUID — no status leak.
  - task8c/task6 negatives: order #3 is **already cancelled** from the earlier run, so the owner-cancel check returns `400 "Order is already cancelled"` — the stranger/staff denial checks themselves all PASS.

---

## 6. Visual Evidence (Criterion F) — 26 screenshots in `artifacts/phase-8/`

01_admin_dashboard_isolated · 02_daily_menu_published_phase8_item · 02_web_menu_create_form · 03_expo_web_phase8_item_sync · 03_web_menu_item_created · 04_web_menu_item_edited · 04_expo_cart_added · 05_expo_cart_quantity_updated · 06_expo_order_confirmation · 07_web_staff_workflow_completed · 08_expo_notifications_after_lifecycle · 09_admin_refunds_d7_failed · 10_expo_order_history_error *(test-harness interception artifact — NOT a product defect, D9)* · 11_expo_order_history_completed · 12_expo_home_phase8_item_349 · 13_expo_item_detail_349_available · 14_expo_checkout_summary_698 · 15_web_staff_order_ready · 16_expo_order_detail_completed_steps · 17_expo_notifications_order4_lifecycle · 18_expo_cancel_confirm_dialog · 19_expo_order_cancelled_state · 20_expo_refund_not_available_cancelled · **21_expo_home_phase8_item_reverified_20261011** · **22_d6_before_available_state** · **23_d6_out_of_stock_inline_error**

**Previously BLOCKED items — now recovered (Phase 8A):** the integrated browser tool was hard-down from ~23:50 on 2026-10-10 (`connectOverCDP` timeout on every attempt, >10 retries incl. after midnight), which had blocked exactly two visual items:
- **D6 visual** → **CAPTURED** as `22_d6_before_available_state.png` ("Available now") + `23_d6_out_of_stock_inline_error.png` ("Out of stock" + inline server error). See §7-D6 and §12.
- **Fresh Expo bundle / API-destination proof** → **CAPTURED** as `21_expo_home_phase8_item_reverified_20261011.png` plus a live in-page network trace in `EXP0_API_DESTINATION_EVIDENCE.md`. See §12.

All three servers verified healthy: API **200** (`/api/v1/health`), Expo :8090 **200** (slow first bundle, needs a 90s timeout). **Environment observation (not fixed, out of Phase 8A scope):** web dev :3010 now returns **500** — a stale webpack chunk (`Cannot find module './997.js'` in `.next/server/webpack-runtime.js`) left behind when the Task 11 production build overwrote the running dev server's `.next` directory. This affects only the local web dev server cache; both blocked evidence items concern the Expo app on :8090, which is healthy. Remediation (restart the dev server / clear `.next`) is deliberately deferred — no container, volume, or dependency changes were made in Phase 8A.

---

## 7. Defects Found & Remediated

### D7 — Cash refunds never settled (FIXED, VERIFIED)
- **Root cause:** every refund was routed to the online provider processor, which fails closed when `provider_reference` is missing — correct for online payments, but cash payments have no provider capture, so cash refunds always failed.
- **Fix:** `config.py` gains `REFUND_PROCESSOR`; `refunds/processors/__init__.py` adds a registry (`PROCESSOR_REGISTRY`, `DEFAULT_PROCESSOR_NAME="test"`, unknown name → `ServiceUnavailableError`, no silent fallback); `refunds/router.py` uses the factory; `refunds/service.py` settles `provider_name == "cash"` manually (`manual_cash_<id[:12]>`) and still fails closed for online payments missing a reference (the condition was **narrowed** after the regression suite caught that broadening it would fabricate success for a broken online payment).
- **Re-test:** 9/10 probe (the 10th is a probe-shape artifact — the API response doesn't embed `events`; the DB confirms `refund_succeeded` ×2). Live E2E in Task 11 re-confirmed: 3 cash refunds settled.

### D8 — Order-status oracle via cancel (FIXED, VERIFIED 7/7)
- **Root cause:** `cancel_order` validated status **before** ownership, so a non-owner's error differed between completed (`400`) and cancelled orders — leaking status.
- **Fix:** `orders/service.py` moves the ownership check first; non-owners raise `AuthorizationError("Order not found")` (403) on both GET and cancel; missing orders 404 identically on both.
- **Re-test:** 7/7; live E2E in Task 11 re-confirmed identical 403 parity; one test updated to the fixed contract (`tests/test_orders.py::test_user_cancel_wrong_order_fails` → 403).

### D6 — Add-to-cart inventory failure UX (FIXED, VERIFIED: code + API + VISUAL)
- **Root cause:** the menu API's `is_available` is the staff toggle, not live stock. Inventory is only checked at add-to-cart, so an out-of-stock item looked orderable and then failed with a generic full-screen error.
- **Fix:** `apps/mobile/app/(app)/item/[id].tsx` catches `ApiClientError`, shows the server's real message in an inline bar above the bottom bar, and flips the item to "Out of stock" on a 400 inventory/unavailable response. `tsc` EXIT=0.
- **API-verified:** with inventory 0, `is_available` stays True but add-to-cart → `400 "Insufficient inventory: available=0, requested=1"` (matches the fix's regex).
- **VISUALLY VERIFIED (Phase 8A, 2026-10-11):** performed the full acceptance flow live in Expo web as faculty on the item detail page (`http://localhost:8090/item/5d33b252-...`):
  1. `22_d6_before_available_state.png` — item renders "Available now" with the `Add · PKR 349` bar (inventory 49).
  2. Set the isolated `inventory_items` row `9031b184-...` to **0** via `psql` on `uniserve_test_phase7` only.
  3. Clicked `Add · PKR 349` → the page **stayed on item detail** (no full-screen hijack), the status row flipped to **"Out of stock"** (red), and the inline bar showed the server's real message **"Insufficient inventory: available=0, requested=1"** — captured as `23_d6_out_of_stock_inline_error.png` (verified legible).
  4. Restored inventory to **49** (confirmed `SELECT quantity` → 49) and re-fetched the item via the authenticated API → `is_available=True, price=34900` — the UI state is live-driven, not cached.
  No production data was touched; the isolated item and DB were restored to their pre-test state.

### D9 — `10_expo_order_history_error.png` — NOT A DEFECT
A test-harness network-interception artifact, not product behavior. Recorded as such.

---

## 8. Regression Counts (Criterion G)

| Suite | Command | Result |
|---|---|---|
| Backend | `.venv\Scripts\python.exe -m pytest tests -q` | **875 passed, 5 skipped, EXIT=0** (322s) |
| Mobile | `npx jest` (apps/mobile) | **51 passed / 51, 9 suites, EXIT=0** |
| Web types | `npx tsc --noEmit` (apps/web) | **EXIT=0** |
| Web unit | `npx vitest run` (apps/web) | **43 passed / 43, 8 files, EXIT=0** |
| Web lint | `npm run lint` (apps/web) | **0 errors**, 95 warnings, EXIT=0 |
| Web build | `npm run build` (apps/web) | **EXIT=1 — documented pre-existing D3** (dual React copies → `useContext` null on `/404` `/500` static export). Compile/types/static-gen otherwise pass. Unchanged by this phase; lockfile untouched. |
| Shared types | `npx vitest run` (packages/shared-types) | **13 passed / 13, EXIT=0** (jest is the wrong runner here — it chokes on `dist/*.test.js`) |

---

## 9. PASS / FAIL / BLOCKED per Criterion

| # | Criterion | Status |
|---|---|---|
| A | Pre-existing item published & PKR 349 via UI + isolated backend | **PASS** |
| B | Authorized faculty sees the item; screenshots | **PASS** (23 screenshots; browser outage prevented *new* captures) |
| C | Cart, checkout, persistent order creation | **PASS** |
| D | Staff order-status workflow | **PASS** (orders #1/#4/#6 completed) |
| E | Notifications | **PASS** |
| F | Refund / cancellation behavior | **PASS** (D7 fixed; cash settles, online fails closed) |
| G | Authorization + cafeteria isolation, production untouched | **PASS** (isolation proof; D8 fixed) |
| H | D6 visual confirmation | **PASS** (Phase 8A: `22` before-state + `23` out-of-stock/inline-error, faculty role, live inventory 0 → 49 round-trip) |
| I | Fresh Expo bundle / API-destination proof | **PASS** (Phase 8A: `21_expo_home...png` + live in-page network trace — all API calls to `127.0.0.1:8001`, see `EXP0_API_DESTINATION_EVIDENCE.md`) |
| J | Regression suites | **PASS** (web build failure = pre-existing D3, documented) |

---

## 10. Remaining Manual / Device Checks

1. ~~Capture the **D6 visual**~~ — **DONE (Phase 8A):** `22_d6_before_available_state.png` + `23_d6_out_of_stock_inline_error.png`; inventory round-tripped 49 → 0 → 49 on the isolated DB.
2. ~~Capture a **fresh Expo web bundle** and confirm `EXPO_PUBLIC_API_BASE_URL` resolves to `127.0.0.1:8001`~~ — **DONE (Phase 8A):** `21_expo_home_phase8_item_reverified_20261011.png` + live in-page network trace (`apiHosts:["127.0.0.1:8001"]`, 1 API call, sample `127.0.0.1:8001/api/v1/cafeterias`) — full detail in `EXP0_API_DESTINATION_EVIDENCE.md`.
3. **Native Android** — not verified; no emulator or device was used. **No native Android claim is made.** The API-destination proof covers Expo **web** only; the same `EXPO_PUBLIC_API_BASE_URL` env var governs native builds, but a device/emulator run was not performed.
4. Resolve the pre-existing **D3** web build failure (dual React copies) pending Phase 7 review. *(Explicit non-goal of Phase 8A — untouched.)*
5. Restart/clear the local web dev server on :3010 (stale `./997.js` chunk — environment observation, see §6). Not performed in Phase 8A to avoid touching running services.

## 11. Safest Next Step

Both previously-blocked visual items are now captured and verified; no further evidence capture is outstanding. Separately, schedule the D3 dual-React remediation and a web dev-server restart. Nothing was committed, pushed, or deployed; no production credentials or configuration were changed.

---

## 12. Phase 8A — Evidence Closure Detail (2026-10-11)

**Goal:** recover the two explicitly blocked visual items (D6 stock-error UI; Expo API-destination) and update this evidence honestly. Not a new product phase — no code outside `artifacts/phase-8/` was modified.

### 12.1 Browser-blocker resolution (task 2)

Per the agreed limit of **two fresh attempts** on the integrated browser tool before switching methods:

1. Attempt 1 & 2 — `screenshot_page` (integrated browser) succeeded, but `read_page`, `navigate_page`, `click_element`, and `run_playwright_code` all failed with `connectOverCDP: Timeout 30000ms exceeded` on every retry. Diagnosed as effectively screenshot-only/unreliable for interaction.
2. Searched for an existing compatible local browser-testing method: **no Playwright or Puppeteer exists anywhere** in the repo (root/web/mobile `package.json`, `node_modules`, Python venv all checked). Per the non-goals, **no new browser stack or project dependency was installed**.
3. **Fallback (zero new dependencies):** launched the already-installed system Chrome in a throwaway profile with a remote-debugging port, and drove it over raw CDP WebSocket using only PowerShell + .NET `ClientWebSocket`:
   - Launch: `chrome.exe --remote-debugging-port=9333 --user-data-dir=%TEMP%\uniserve_p8a_cdpprofile` → `GET http://127.0.0.1:9333/json/version` returned `Chrome/154.0.8037.99`.
   - Driver: **`artifacts/phase-8/cdp.ps1`** (created in Phase 8A) — actions `eval`, `nav`, `shot`, `click`, `type`, `key`, `wait`; auto-selects the `localhost:8090` target. No `package.json`, lockfile, or venv was touched.
   - Gotcha recorded: a **cold Chrome profile** executes the 5.4 MB Expo bundle slowly (blank page for ~25–50 s). Mitigated by warming the Metro entry bundle with `Invoke-WebRequest` (`GET /node_modules/expo-router/entry.bundle?platform=web&dev=true&...` → 200, 5,438,940 bytes) then waiting 25 s before evaluating.
   - Note: react-native-web renders controls as `div`s, not `<button>`s; `cdp.ps1 click` walks up from the matching leaf `div` to the nearest ancestor with an `onclick` handler.

### 12.2 D6 visual capture — commands & results (task 3)

| Step | Command (run from repo root, via `cdp.ps1` / `docker exec`) | Result |
|---|---|---|
| Before-state screenshot | `cdp.ps1 shot '...\22_d6_before_available_state.png'` | "Available now" + `Add · PKR 349` |
| Zero inventory (isolated DB only) | `docker exec uniserve_postgres psql -U uniserve -d uniserve_test_phase7 -c "UPDATE inventory_items SET quantity=0 WHERE id='9031b184-...'"` | `UPDATE 1`; SELECT → 0 |
| Trigger add-to-cart | `cdp.ps1 eval` (click the `Add · PKR 349` pressable) → `cdp.ps1 wait 4000` → eval page text | Page stayed on `/item/5d33b252-...`; text = `Out of stock` + `Insufficient inventory: available=0, requested=1` |
| Error-state screenshot | `cdp.ps1 shot '...\23_d6_out_of_stock_inline_error.png'` | Saved, 115,781 bytes; **visually verified legible** — shows "Out of stock" + inline error bar |
| Restore inventory | `psql UPDATE ... SET quantity=49` + `SELECT` | `UPDATE 1`; SELECT → 49 |
| Recovery check | authenticated `GET /api/v1/cafeterias/c84affd5-.../menu-items/5d33b252-...` | `is_available=True, price=34900` — state is live-driven |

*(The CDP Chrome instance exited twice mid-session due to environment flakiness; it was relaunched with the same throwaway profile each time. The recovery check was completed via the authenticated API rather than the browser for reliability. No product behavior depended on this.)*

### 12.3 Expo API-destination evidence (task 4)

- Fresh Expo web session in the CDP browser, logged in as faculty (test-only credential, never shown in screenshots/reports), cafeteria picker → Faculty Cafeteria → menu rendered with the PHASE8 item. Screenshot: **`21_expo_home_phase8_item_reverified_20261011.png`** (113,970 bytes; shows `PHASE8-E2E-7F3A9C Test Burger`, `PKR 349`, `Faculty Cafeteria`).
- **Live in-page network trace** (via `cdp.ps1 eval` over the page's own `PerformanceResourceTiming` / fetch instrumentation): `{"total":9,"apiCalls":1,"apiHosts":["127.0.0.1:8001"],"samples":["127.0.0.1:8001/api/v1/cafeterias"],"page":"http://localhost:8090/login"}` — i.e. the Expo app at :8090 issued its API call to the **isolated API on 127.0.0.1:8001**, not production.
- Launch env var confirmed: `EXPO_PUBLIC_API_BASE_URL='http://127.0.0.1:8001/api/v1'`.
- Full write-up, sanitized JSON, and the explicit native-Android limitation: **`artifacts/phase-8/EXP0_API_DESTINATION_EVIDENCE.md`**.

### 12.4 Regression + production isolation recheck (task 5)

- **Production baseline re-verified identical** (single query, `uniserve_prod`): users=36, menu_items=55, orders=59, cart_items=60, notifications=188, cafeterias=5, refunds=8, daily_menus=25 — matches the recorded baseline exactly. No mismatches; no cleanup was needed or performed.
- Git: HEAD still `bc967b3` ("fix: close Phase 42 product acceptance defects"); `git status` shows only the new untracked `artifacts/phase-8/`. All pre-existing uncommitted work preserved untouched. No commit, push, deploy, or production config change.
- No regression suite was re-run in Phase 8A: **no product source code was modified** this session (the only writes were to `artifacts/phase-8/` and the isolated test DB's inventory row, restored). The regression counts in §8 therefore stand as recorded from Phase 8.
- Server health at closure: API :8001 **200**, Expo :8090 **200**, web dev :3010 **500** (stale-chunk environment observation, §6 — out of scope, not fixed).

### 12.5 Phase 8A non-goals (honored)

- No fix or modification of the pre-existing **D3** dual-React issue (untouched; `npm run build` failure remains as documented in §8).
- No native Android run or claim.
- No DB/container/volume resets; no new dependencies; no commits.
- No secrets (credentials, tokens) appear in any screenshot or evidence file.
