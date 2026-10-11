# FINAL CLIENT TEST MATRIX — UniServe

**Date:** 2026-10-08 · Companion to `FINAL_CLIENT_ACCEPTANCE_TEST.md`
Legend: ✅ verified live via UI · ⛔ correctly denied/scoped (no defect) · ➖ not applicable to role · ⚠️ works, with recorded finding

| # | Workflow | Admin (web) | Manager (web) | Staff (web) | Student (Expo) | Faculty (Expo) | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | Login & identity | ✅ System Administrator | ✅ Sana Malik, scoped to Faculty Cafeteria | ✅ Ahmed Raza, scoped to Student Cafeteria | ✅ Ayesha Khan, FA22-001 verified | ✅ Dr. Sana Malik, FAC-101 | e01, e10, e13, e24, e33 |
| 2 | Dashboard overview | ✅ university-wide stats | ✅ Faculty-only stats, 0 active orders | ✅ Student Cafeteria, sees #55 pending | — (mobile home = menu) | — (mobile home = menu) | e24, e33 |
| 3 | Menu browsing / published menu | ✅ catalog + daily-menu editor | ⛔ Student menu not visible (correct scope) | ➖ orders-focused UI | ✅ 8 items, images, prices | ✅ same 8 items across cafeterias | e03, e05, e08, e11, e14 |
| 4 | Menu item creation | ✅ 4 items created via modal | ➖ | ➖ | ➖ | ➖ | e01–e03 |
| 5 | Daily menu build & publish | ✅ 8 items, published state | ➖ | ➖ | ✅ receives published menu | ✅ receives published menu | e04, e05, e08, e14 |
| 6 | Real image upload | ✅ 4× UI file-chooser upload | ➖ | ➖ | ➖ | ➖ | e02, e03 |
| 7 | Image rendering | ✅ thumbnails in catalog | ➖ | ➖ | ✅ DOM-verified + visual (menu, detail) | ✅ visual on menu | e03, e08, e11, e16 |
| 8 | Item detail view | ✅ (admin menu card) | ➖ | ➖ | ✅ image, price, tags, ETA | ✅ (browsed Student menu) | e16, e11 |
| 9 | Cart add & quantity | ➖ | ➖ | ➖ | ✅ add + cart bar + cart page | ➖ | e17, e20, e21 |
| 10 | Inventory gating (0 stock) | ✅ observed 0-stock state | ➖ | ➖ | ⚠️ add-to-cart correctly blocked at 0 stock (early attempt) | ➖ | e18, API 400 log |
| 11 | Inventory restock | ✅ 4× Adjust → 50 portions | ➖ | ➖ | ➖ | ➖ | e19 |
| 12 | Checkout (payment/collection/note) | ➖ | ➖ | ➖ | ✅ cash + immediate + note | ➖ | e22 |
| 13 | Order placement | ➖ | ➖ | ➖ | ✅ Order #55 confirmed | ➖ | e23 |
| 14 | Order queue visibility | ✅ #55 in completed filter | ⛔ #55 invisible (correct — Student cafeteria) | ✅ #55 at top as pending | ➖ | ➖ | e24, e33, e34 |
| 15 | Order lifecycle processing | ✅ observes transitions | ➖ | ✅ Confirm→Preparing→Ready→Collect w/ dialogs | ✅ sees live status changes | ➖ | e26–e29, e30 |
| 16 | Order details / timeline | ✅ full timestamps + token | ⛔ scoped out | ✅ per-order details | ✅ tracker + payment + note | ➖ | e35, e23 |
| 17 | Order status notifications | ➖ | ➖ | ✅ broadcast visible on dashboard | ✅ 4 lifecycle notifications delivered | ➖ | e24, e31 |
| 18 | Refund management | ✅ approve #46 → sandbox → terminal state | ⛔ scoped out | ➖ | ✅ refund request exists on order #46 (historical) | ➖ | e36, e37 |
| 19 | RBAC — admin routes | ✅ access | ⚠️ reports accessible but data-scoped to Faculty | ⛔ /dashboard/admin/* redirected + 403 | ⛔ web dashboard not for students | ⛔ web dashboard not for faculty | e38, e40 |
| 20 | RBAC — cafeteria scoping | ✅ sees all 3 cafeterias | ⛔ only Faculty data | ⛔ only Student data | ⛔ Faculty cafeteria 403 (correct; copy misleading) | ✅ both cafeterias browse allowed | e33, e24, API 403 log |
| 21 | Negative — invalid credentials | ✅ wrong password rejected ("Invalid email or password") | ✅ same guard | ✅ same guard | ✅ same guard | ✅ same guard | e39 |
| 22 | Negative — cross-cafeteria deep link | ➖ | ➖ | ➖ | ⚠️ API 403 correct; UI shows generic failure | ➖ | API 403 11:34 UTC, e16 context |
| 23 | Data integrity (orphans) | ✅ 0 orphaned order items / inventory / notifications / refunds (read-only DB) | ➖ | ➖ | ➖ | ➖ | DB check, §20 report |
| 24 | Inventory decrement | ✅ biryani 50→49 after completion | ➖ | ➖ | ➖ | ➖ | DB check |
| 25 | Consistency across clients | ✅ same state as all roles | ✅ scoped view consistent | ✅ scoped view consistent | ✅ backend state matches web | ✅ matches web | §17 of main report |

**Summary:** 25 workflows tested across 5 role clients — **no privilege escalation, no cross-tenant data leakage, no P0/P1 defects.** All ⚠️ items map to defects F-ACC-02/04/05/06 (P2/P3) in `FINAL_CLIENT_ACCEPTANCE_TEST.md` §19.
