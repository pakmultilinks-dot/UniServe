# PHASE 53 — Mobile Notification Inbox

**Status:** PASS  
**Date:** 2026-10-05  
**Branch:** `main` — HEAD `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` (unchanged, zero commits)  
**Authoritative spec:** Phase 53 — "Make the existing UniServe notification infrastructure actually consumable from the mobile app."

---

## 1. Objective

Give students and faculty a real, first-class consumption surface inside the mobile app for the existing in-app notification system (Phase 50 admin broadcasts + order-lifecycle notifications), with an authoritative unread badge, mark-one/mark-all read, complete UI states, strict role gating for admin/manager/staff accounts, and verified server-side data isolation. **No push, SMS, email, or WhatsApp** — in-app only, reusing the existing backend without new endpoints.

## 2. Discovery Findings (STEP 1 — completed before any implementation)

1. **Exact mobile files changed (6 total):**
   - `apps/mobile/src/services/data.ts` — edited (2 new client wrappers + 1 page-level fetch)
   - `apps/mobile/src/contexts/NotificationsContext.tsx` — **new** (unread-count provider)
   - `apps/mobile/app/(app)/(tabs)/notifications.tsx` — **new** (inbox screen)
   - `apps/mobile/app/(app)/(tabs)/_layout.tsx` — edited (5th tab + badge)
   - `apps/mobile/src/components/WebDashboardGate.tsx` — **new** (role-gate screen)
   - `apps/mobile/app/_layout.tsx` — edited (RoleGate no longer silently logs out; provider wrap)
2. **Exact reusable API functions:** existing `getNotifications` + `getUnreadNotificationCount` (data.ts); new `markNotificationRead` / `markAllNotificationsRead` wrappers map 1:1 to **existing** backend endpoints `PATCH /notifications/{id}/read` and `PATCH /notifications/read-all`; shared-types already export `MarkReadResponse` / `MarkAllReadResponse`; UI kit reused: `Button`, `EmptyState`, `ErrorState`, `Toast`, `ConfirmDialog`, `ActivityIndicator`, `RefreshControl`; cart-badge pattern reused for the tab badge.
3. **Exact route/tab location:** 5th primary tab `notifications` in `apps/mobile/app/(app)/(tabs)/`, positioned between **Orders** and **Favorites**, visible bell icon in the bottom tab bar (same pattern as the established Home-tab cart badge).
4. **Whether backend change is necessary:** **NO.** Verified by full read of `apps/api/app/modules/notifications/router.py` (7 endpoints, all user-scoped / admin-guarded) and `service.py` (`mark_as_read` raises 404 for foreign rows — hides existence; `mark_all_as_read` UPDATE scoped to `auth.user.id`). CORS already allows Expo web `http://localhost:8081`; `secure-storage.ts` has a web localStorage shim. Zero backend files touched.

## 3. Files Changed

| File | Change |
|---|---|
| `apps/mobile/src/services/data.ts` | + `markNotificationRead(id)` → `PATCH /notifications/{id}/read`; + `markAllNotificationsRead()` → `PATCH /notifications/read-all`; + `getNotificationsPage()` (returns items+total+unread_count); exported `NotificationListResponse` |
| `apps/mobile/src/contexts/NotificationsContext.tsx` | **NEW** — `NotificationsProvider` + `useNotifications()` → `{unreadCount, refreshUnreadCount}`; server-fetched count (never local); fetches only while authenticated; silent on failure (badge is passive; inbox owns error UX) |
| `apps/mobile/app/(app)/(tabs)/notifications.tsx` | **NEW** — inbox screen: header ("Notifications" + "N unread notifications" / "You're all caught up" + "Mark All Read" when unread>0), type-icon/title/body/relative-timestamp rows, unread tint + green dot + bold title, tap-unread→read, ErrorState+retry, EmptyState "No notifications yet", RefreshControl, Toast on action failures |
| `apps/mobile/app/(app)/(tabs)/_layout.tsx` | 5th `<Tabs.Screen name="notifications">` between Orders and Favorites; badge mirrors cart-badge pattern (`99+` cap, `colors.error`); `useFocusEffect` re-fetches `refreshUnreadCount()` on every tab focus (server truth, no polling) |
| `apps/mobile/src/components/WebDashboardGate.tsx` | **NEW** — themed gate: desktop-outline icon, "Use the Web Dashboard", exact spec copy, "Signed in as {name} ({role})", existing `Button` + `ConfirmDialog` Sign Out |
| `apps/mobile/app/_layout.tsx` | `RoleGate`: removed silent-logout `useEffect`; renders `<WebDashboardGate/>` in the same conditional position (leaf render — Phase 43 navigator-swap lesson respected); `<NotificationsProvider>` wrapped inside `<AuthProvider>` |

## 4. Mobile Notification Architecture Used

```
Backend (unchanged)                     Mobile (Phase 53)
─────────────────────                   ─────────────────────────────────────
GET  /notifications           ←──  getNotificationsPage()  (screen load/refresh)
GET  /notifications/unread-count ←─  getUnreadNotificationCount()
                                     └─ NotificationsContext.unreadCount
PATCH /notifications/{id}/read ←──  markNotificationRead()   (tap unread row)
PATCH /notifications/read-all ←──  markAllNotificationsRead() (Mark All Read)
```

Single source of truth = backend. Badge data flows: `NotificationsContext` (fetched on auth, tab focus, and after every successful mark) → tab bar badge. Screen state updates **only after successful API responses** (no optimistic pretending). Failures: initial-load failure → `ErrorState` + "Try again"; refresh failure with data on screen → keep data + error Toast; mark-read failure → error Toast, row stays unread. Provider sits inside `AuthProvider`, fetches only while authenticated (logged-out 401 can never trip the auth-failure logout hook).

## 5. UI Behavior

- **List row:** type icon (15-type `TYPE_ICONS` map mirroring the web notification center) · title · body (2-line clamp) · relative timestamp ("Just now / Xm ago / Xh ago / Oct 4" — same wording as web `formatDate`).
- **Unread:** brand tint background + green dot + bold title — distinguishable at a glance.
- **Badge:** rendered only when `unreadCount > 0`; "99+" cap; always server-derived.
- **Loading state:** centered `ActivityIndicator` (verified via delayed-route screenshot — no fake empty state during load).
- **Zero state:** EmptyState bell + "No notifications yet" + "Order updates and announcements from your cafeteria will appear here." Only shown for genuinely empty results — a failed fetch never renders "No notifications".
- **Error state:** "Couldn't load notifications" + API error message + "Try again" (retry re-fetches successfully).
- **Pull-to-refresh:** `RefreshControl` wired exactly like `favorites.tsx` (see Known Limitations — mouse-only web harness).
- **Mark All Read:** visible only when unread > 0 (web parity); on success all rows flip read, subtitle → "You're all caught up", badge → 0, button hides.
- **Mark-one-read failure (spec §2.4):** proven with an aborted PATCH — visible Toast "Couldn't mark as read — Network error: Failed to fetch", row remains unread, badge unchanged; retry after un-abort succeeded and landed in DB with `read_at`.

## 6. Role-Gating Behavior

`MOBILE_ROLES = ["student", "faculty"]` enforced by `RoleGate` in `app/_layout.tsx`. Any authenticated `university_admin`, `cafeteria_manager`, or `cafeteria_staff` session now renders `WebDashboardGate` instead of the tab navigator:

- Title: **"Use the Web Dashboard"**; body: **"This account is managed through the UniServe web dashboard. Sign in on a computer to manage orders, menus, refunds, and reports."**
- "Signed in as {first} {last} ({role label})" — identity only, **zero admin data**: no dashboards, orders, refunds, reports, menus, broadcast composer, or staff management surfaces are mounted.
- **No silent logout:** the previous `useEffect` calling `logout()` + `null` return is removed. The session is preserved; the user ends it deliberately via the existing Sign Out button → existing `ConfirmDialog` → `logout()`.
- The gate renders in the same conditional slot as the old `null` (leaf component render — never a navigator swap, per the Phase 43 "Maximum update depth exceeded" lesson).
- Backend RBAC (`RequireRole`) remains the enforcement boundary regardless of UI gating.

## 7. Data-Isolation Verification (STEP 5)

Backend isolation was verified by code read and confirmed live:

- **Student B (bilal.hussain@student.lgu.edu.pk):** `GET /notifications` → only his rows (total=10, unread=10); `GET /unread-count` → 10 (list and count endpoints agree); **zero foreign rows** in the payload.
- **Cross-user attack:** `PATCH /notifications/{ayesha's_notification_id}/read` as bilal → **404** (`NotFoundException` on ownership check — existence hidden, no write). Ayesha's row unchanged (`is_read=true` retained).
- **Cross-user write containment:** Ayesha's "Mark All Read" (47 rows) left bilal's unread at 10 and the faculty account at 58 — `mark_all_as_read`'s `UPDATE … WHERE user_id = auth.user.id` is genuinely scoped.
- **Faculty (dr.sana.malik@lgu.edu.pk):** own rows only (total=58, unread=58), endpoints agree.
- All queries scoped in `service.py` (`Notification.user_id == user_id`).

## 8. Phase 50 Broadcast Verification (STEP 6)

End-to-end on live infrastructure, labeled test data only:

1. **Broadcast (admin API):** `admin@lgu.edu.pk` → `POST /notifications/broadcast` `{title:"Phase 53 E2E — Campus Wi-Fi maintenance", audience:"students", idempotency_key:"phase53-e2e-broadcast-001"}` → 201, id `006d4893-7532-4a3d-9820-8d647f9fa329`.
2. **Fan-out:** notifications table 131 → 135 (+4 = exactly the 4 active students); fresh student received exactly 1 `admin_announcement`, unread.
3. **Mobile inbox:** fresh student in Expo web → bell tab badge **1** → row "Phase 53 E2E — Campus Wi-Fi maintenance" with megaphone icon + "1m ago" → **tap** → "You're all caught up", badge **0**, Mark All Read button hidden.
4. **DB:** `is_read=true`, `read_at` set on the row.
5. **Repeat broadcast** (idempotency `phase53-e2e-broadcast-002`) re-confirmed the cycle and drove the mark-read failure/retry test.
6. Ayesha's full cycle on 48 pre-existing unread: badge 48 → tap row → 47 (DB `read_at` verified) → Mark All Read → 0 (DB verified) → badge hidden.
7. **Explicitly NOT implemented / NOT claimed:** push notifications, SMS, email, WhatsApp. This is the in-app inbox only.

## 9. Tests Run and Exact Results (STEP 9)

| Test | Command / scope | Result |
|---|---|---|
| Mobile type-check | `npm run type-check` (apps/mobile, `tsc --noEmit`) | **PASS — 0 errors** (one fix during Phase 53: `getNotificationsPage` added after `getNotifications`'s unwrapped return type failed type-check) |
| Mobile lint | `npm run lint` (apps/mobile) | **BASELINE GAP — not runnable.** ESLint 8.57.1 finds no configuration file for `apps/mobile` (only `apps/web/.eslintrc.json` exists; `git ls-files apps/mobile` proves no mobile config is tracked). Pre-existing condition — Phase 53 added no dependency/config; documented instead of papering over. |
| Mobile test suite | none exists | **N/A by design** — mobile has no test script/framework; no framework created (spec). |
| Backend regression | full suite | **N/A per spec** — zero backend files changed |
| Targeted backend evidence | `pytest tests/test_notifications.py tests/test_phase50_admin_notifications.py` (venv py3.13.7) | **PASS — 90 passed in 15.75s** |

## 10. E2E Results A–K (STEP 10)

Expo web E2E on `http://localhost:8081` (Expo SDK 57, `EXPO_PUBLIC_API_BASE_URL=http://localhost:8001/api/v1`, live uvicorn :8001, live Postgres :5433). Web was viable because `secure-storage.ts` shims to localStorage on web and CORS already allows :8081.

| # | Scenario | Result | Evidence |
|---|---|---|---|
| A | Notifications tab visible in primary tab bar | **PASS** | Tab bar snapshot: Home · Orders · **Notifications** · Favorites · Profile |
| B | Badge rendered from server data (not local fakery) | **PASS** | Badge "48" matched ayesha's server unread (48); fresh student badge absent (0) |
| C | Inbox list renders (type icon, title, body, timestamp, read state) | **PASS** | Rows incl. "Order Ready for Collection", "Order Cancelled", Phase 50 broadcast ("6h ago"); unread tint/dot/bold vs read rows |
| D | Tap unread → mark-one-read; badge decrements; DB read_at set | **PASS** | Subtitle 48→47, tab badge 47; DB `690c588d… order_cancelled read_at=2026-10-06 00:38:40+05` |
| E | Mark All Read → all read, badge 0, UI/DB agree | **PASS** | Subtitle "You're all caught up", button hidden, badge hidden; DB ayesha unread=0 |
| F | Zero state "No notifications yet" | **PASS** | Fresh labeled student (`p53.e2e.student@student.lgu.edu.pk`, 0 rows): empty state + "You're all caught up" + no badge |
| G | Error + retry (fetch failure ≠ empty state) | **PASS** | Route-abort → "Couldn't load notifications / Network error: Failed to fetch / Try again" (never "No notifications"); unroute + Try again → data restored |
| H | Student isolation (cross-user fails, no data leaks) | **PASS** | Bilal: own 10/10 only; cross-user PATCH → **404**; ayesha's mark-all didn't touch his rows; DB unchanged |
| I | Faculty isolation | **PASS** | dr.sana.malik: own 58/58 only via both endpoints |
| J | Phase 50 broadcast → mobile inbox → unread → read → badge | **PASS** | Broadcast id `006d4893…` → +4 fan-out → badge 1 → tap → read (DB `read_at` set) → badge 0 |
| K | Admin/manager/staff gate + preserved session + Sign Out works | **PASS** | All three roles (admin `Admin123!`, sana.malik + ahmed.raza `TestPass123!`): gate screen with exact copy, "Signed in as System Administrator (University Admin)" / "Sana Malik (Cafeteria Manager)" / "Ahmed Raza (Cafeteria Staff)", session preserved (no silent logout), Sign Out → ConfirmDialog → login/landing |

**Supplementary verifications (spec-critical semantics):**
- **§2.4 mark-read failure:** aborted PATCH → Toast "Couldn't mark as read — Network error: Failed to fetch", row stayed unread, badge unchanged; unabort + re-tap → success (DB `read_at` landed).
- **Loading state:** delayed-route screenshot (`p53_loading_state.png`) shows centered spinner during load — no fabricated empty/error state.
- **Pull-to-refresh:** `RefreshControl` implemented (favorites.tsx pattern); touch-gesture simulation not possible in the mouse-only web harness — see Known Limitations. Data-freshness paths actually exercised: tab-focus refetch, mark-success refetch, retry refetch.
- **Badge failure containment:** badge refresh failures during route-abort were swallowed (no crash, no logout trip) while the inbox showed proper error UX — as designed.

## 11. Dependencies / Lockfile Status (STEP 8)

- **Zero** dependency or lockfile changes. `package-lock.json` SHA-256 unchanged: `2E2DFE6308369BB225287A228DF86ED5AEC7CC2D2B2E294B54C0FD7CA87CFB8A`.
- No `npm install`, no lockfile regeneration, no new packages (Expo SDK 57 / RN 0.86.3 / expo-router / @expo/vector-icons all pre-existing).

## 12. Database / Data Changes (STEP 11)

**No schema change. No migration. No DB reset. No unrelated-data mutation. No order/refund/payment writes.**

| Table | Before | After | Δ | Explanation |
|---|---|---|---|---|
| `notifications` | 131 | 139 | +8 | 2 labeled broadcasts × 4 active students (product behavior under test) |
| `admin_broadcasts` | 4 | 6 | +2 | both titled "Phase 53 E2E — …" with idempotency keys |
| `users` | 15 | 16 | +1 | fresh labeled test student `p53.e2e.student@student.lgu.edu.pk` / `Phase53 E2E Student` (needed for empty-state + clean mutations) |
| `orders` | 50 | 50 | 0 | untouched |
| `refunds` | 3 | 3 | 0 | Phase 51 refunds untouched |

Read-flag flips performed (ayesha 47+1, fresh student 1, bilal/sana 0) are the product behavior under test. Expo dev artifacts (`apps/mobile/assets/icon.png`, `.expo/`) appeared untracked from the dev server — generated files, no tracked content affected.

## 13. Known Limitations

1. **`npm run lint` (mobile) cannot run** — no ESLint config is tracked for `apps/mobile` (pre-existing baseline gap; `apps/web` has one). Phase 53 did not add lint configuration or dependencies (out of scope); type-check is the enforced gate and passes.
2. **Pull-to-refresh gesture** is implemented via `RefreshControl` (native touch pattern, same as `favorites.tsx`) but could not be gesture-driven in the desktop web harness (mouse-only, no touch emulation). Equivalent refresh paths (tab-focus refetch, post-mark refetch, retry) were exercised live.
3. **Transient subtitle during first load:** before the list response arrives, the subtitle briefly reads "You're all caught up" (local unreadCount starts at 0) then updates to "N unread". Cosmetic only; spinner is visible during this window.
4. **Relative timestamps** re-render on data load/focus, not per-minute tickers — a row showing "Just now" updates on the next fetch (matches web behavior granularity).
5. **Badge refresh failure is silent by design** (passive indicator); the inbox owns error UX. Cross-checked in E2E G that the app neither crashes nor logs the user out when every notifications call fails.
6. **Limit 50** rows per fetch (newest first) — pagination is a Phase 54 concern, intentionally not implemented.
7. **Login redirect quirk (pre-existing, untouched):** post-login deep-link sometimes lands on `/cart`/`/` — RoleGate covers the whole navigator regardless of route, so gating is unaffected.

## 14. Out of Scope (documented, NOT implemented — STOPPED at boundary)

Per the Phase 53 scope boundaries, the following were deliberately **not** implemented (some confirmed discoverable, left for their own phases):
- **Phase 54:** manager-cancel of confirmed orders from mobile (backend-only today — P1 from Phase 52), order-detail deep links from notifications (`order_id`/`reference_id` exist in payloads but rows are non-navigating), notification date filters, pagination.
- **Phase 55:** profile/password/sessions/audit-log/overview banner work.
- **Phase 56:** copy-previous-day menu, inventory create, menu delete, dietary/allergens.
- **Push notifications, SMS, email, WhatsApp** — not implemented, not claimed (spec).
- **Deployment, VPS, production config, unrelated redesign** — untouched.
- Lint configuration creation, test-framework creation, web-build fixes (dual-React baseline issue), ruff E402 baseline — all untouched.

## 15. Git Status

- **HEAD:** `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` — **unchanged**; `git log` shows no new commits.
- **No commit / no push / no reset / no rebase / no amend / no branch change.**
- **Lockfile:** SHA-256 identical (§11).
- **Phase 53 file delta (exactly 6 files):** 3 modified (`data.ts`, `(tabs)/_layout.tsx`, `_layout.tsx`) + 3 new (`notifications.tsx`, `NotificationsContext.tsx`, `WebDashboardGate.tsx`).
- **Inherited dirty tree (Phases 43–51 + PHASE_52 report): preserved untouched** — no cleanup, no restoration of tracked deletions. Status count 108 = inherited baseline + Phase 53's 3 new files + Expo dev artifact `apps/mobile/assets/`.
- **Runtime:** uvicorn :8001, web dev :3000, Postgres :5433 (alembic head 0013) left running, unchanged.

---

*Phase 53 complete. The existing notification infrastructure is now fully consumable from the mobile app for students and faculty, with authoritative unread state, honest failure semantics, and role-gated safety. Phase 54 NOT started — awaiting authorization.*
