# Final Presentation Fix — F-ACC-06 (Staff Order Console: Prepare gating)

**Task:** Implement and verify the single confirmed presentation-blocking fix identified by `FINAL_CLIENT_FINDINGS_TRIAGE.md` (finding **F-ACC-06**, classification **A — fix before final presentation**). Scope was strictly limited to this one fix; no other finding, workflow, backend code, or data was touched.

---

## 1. Original Defect

**Finding F-ACC-06 (P2 triage severity retained from acceptance register; classified A in triage):** the staff/manager order queue in the web console rendered the **Prepare** action button for any order with `status === "pending"` — including orders that had **not been confirmed yet** (`confirmed_at` null). Clicking it fired a request the server correctly rejected with **HTTP 400** ("Order must be confirmed before starting preparation") and a corrective error toast.

The server's workflow rule is correct (confirm must precede preparation); the defect was purely client-side: the UI offered an action that was guaranteed to be refused. The sibling **Confirm** button in the same action block already implemented the correct guard (`!order.confirmed_at`), and the order objects rendered by the queue already carry `confirmed_at`, so the gating data was present in the page — the Prepare button simply wasn't using it. Every fresh order starts `pending`/unconfirmed, so the defective state appeared immediately on the central staff demo screen.

- Source of finding: `FINAL_CLIENT_ACCEPTANCE_TEST.md` §19 (F-ACC-06), triaged in `FINAL_CLIENT_FINDINGS_TRIAGE.md` §3/§4 (FIX-1).
- Affected client/role: **Staff** (primary) and **Manager** (secondary) in the web console order queue.

## 2. Exact Code Change

### Application code — `apps/web/src/app/dashboard/orders/page.tsx` (action block ≈ line 590)

Before:

```tsx
{order.status === "pending" && (
  <Button
    size="sm"
    variant="secondary"
    loading={actionLoading === order.id}
    onClick={() => handleAction(order.id, () => prepareOrder(order.id))}
  >
    Prepare
  </Button>
)}
```

After (the only functional change — one added boolean condition, plus an explanatory comment matching the file's phase-comment convention):

```tsx
{/* F-ACC-06 — Prepare is only valid once the order has
    been confirmed (backend rejects prepare on an
    unconfirmed pending order with 400). Mirror the
    Confirm gate above so the console never offers an
    action the server will refuse. */}
{order.status === "pending" && !!order.confirmed_at && (
  <Button
    size="sm"
    variant="secondary"
    loading={actionLoading === order.id}
    onClick={() => handleAction(order.id, () => prepareOrder(order.id))}
  >
    Prepare
  </Button>
)}
```

Resulting behavior matrix (exactly as specified):

| Order state | Buttons shown |
|---|---|
| `pending`, `confirmed_at == null` | Details, **Confirm** (+ Reject for manager) — **Prepare absent** |
| `pending`, `confirmed_at` set | Details, **Prepare** — Confirm absent |
| `preparing` | Details, Ready, Delay (unchanged) |
| `ready` | Details, Collect, Delay (unchanged) |

Nothing else was changed: no backend code, no API contract, no state machine, no permissions, no other UI. Because `handleAction` refreshes the queue after every action (`loadOrders()`), the just-confirmed order re-renders with `confirmed_at` set and Prepare appears immediately.

### Test code — `apps/web/src/__tests__/orders-page.test.tsx`

Extended the **existing** Phase 60 orders-page test file in place (same mock setup, same `renderPage()` helper, same `apiMock` fixture pattern — no new testing architecture):

1. Added `Order` to the existing shared-types import (`import type { Cafeteria, Order } from "@uniserve/shared-types";`).
2. Added a small typed fixture factory `makeOrder(overrides)` (full valid `Order` shape; overrides carry `order_number` plus the fields under test).
3. Added one focused describe block, `OrdersPage — Prepare action gating (F-ACC-06)`, with the three required cases.

## 3. Why the Change Is Minimal

- **One boolean condition** added to an existing render guard — `&& !!order.confirmed_at` — reusing the exact field the sibling Confirm gate 20 lines above already uses. No new state, hooks, props, or components.
- **No data plumbing:** the queue already receives `confirmed_at` per order (the Confirm gate depends on it); no fetch, type, or API change was needed.
- **No workflow/permission change:** the server remains authoritative; the UI simply stops advertising a pre-rejected action. All other actions (Confirm, Reject, Ready, Collect, Delay, manager Cancel) are untouched.
- **No refactoring:** the rest of the 1,000+ line orders page is byte-identical; the diff on the application file is the guard plus a 5-line comment.
- **No new dependencies, no lock-file change, no migration, no backend edit.**

## 4. Tests Added/Updated

Extended `apps/web/src/__tests__/orders-page.test.tsx` (existing fixture/approach reused):

- **Case 1 — pending, unconfirmed:** asserts `Confirm` is rendered and `Prepare` is **not**.
- **Case 2 — pending, confirmed (`confirmed_at` set):** asserts `Prepare` is rendered and `Confirm` is **not**.
- **Case 3 — preparing/ready unaffected:** renders one `preparing` and one `ready` order; asserts `Ready` and `Collect` actions are still offered and `Prepare`/`Confirm` are absent on both.

Assertion-safety note: the page's status tabs and `StatusBadge` render raw lowercase status text (capitalization is CSS-only), so the capitalized action-button labels (`Confirm`, `Prepare`, `Ready`, `Collect`) are unambiguous in jsdom; this is documented in a comment above the new block.

## 5. Test Results

| Validation | Command (run in `apps/web`) | Result |
|---|---|---|
| Focused orders UI test | `npx vitest run src/__tests__/orders-page.test.tsx` | **7/7 passed** — 4 pre-existing queue-state tests + 3 new gating tests |
| Full web test suite | `npm test` (vitest run) | **43/43 passed** across 8 test files |
| Web TypeScript check | `npm run type-check` (`tsc --noEmit`) | **Clean** — no errors |
| Web lint | `npm run lint` (`eslint . --ext .ts,.tsx`, no auto-fix) | **0 errors**; 57 pre-existing warnings in unrelated files (e.g., legacy `no-explicit-any`); **0 warnings in the two touched files** |

No backend lint was run because no backend file was touched (and per mandate only `ruff check --no-fix app` would be permissible — not required).

## 6. Manual Client Verification (live staff console)

Environment: web console dev server (`localhost:3000`), logged in as the **staff** demo account (Ahmed Raza, Student Cafeteria queue). An existing safe pending order was used — **no new order was created**. Order **#6** (oldest pending seed order, Oct 2, PKR 100, Gulab Jamun) was chosen deliberately to keep the walkthrough's data impact minimal.

| Step | Expected | Observed |
|---|---|---|
| 1. Open `/dashboard/orders`, Pending tab, with 9 pending unconfirmed orders | Every card shows **Details + Confirm**; **Prepare absent** | ✅ All 9 cards show exactly Details + Confirm; zero Prepare buttons rendered (screenshot captured) |
| 2. Click **Confirm** on order #6 | Queue refreshes; #6 now shows **Prepare** (still Pending); unconfirmed orders still show only Confirm | ✅ #6 card: Details + Prepare; the other 8 cards unchanged (Details + Confirm) |
| 3. Click **Prepare** on order #6 | Order leaves the pending queue and moves to **Preparing** normally (no 400, no error toast) | ✅ Pending count dropped 9 → 8; preparing tab shows #6 as **Preparing** with **Details + Ready + Delay** (screenshot captured) |
| 4. Stop — workflow intact | Existing post-confirmation workflow unchanged | ✅ Confirmed via the preparing card's Ready/Delay actions; **stopped here** — Ready was not clicked, order #6 remains in `preparing` |

Database confirmation (read-only query afterwards): order #6 = `status preparing`, `confirmed_at 2026-10-08 18:09:28+05`, `preparation_started_at 2026-10-08 18:09:42+05`; the other **8 pending orders remain pending and unconfirmed** — untouched. No other order, menu item, inventory row, user, or fixture was modified. This single status progression of seed order #6 (pending → confirmed → preparing) is the direct, intended result of the mandated manual verification using an existing pending order.

## 7. Git / Package-Lock Integrity

| Check | Baseline (before) | After | Verdict |
|---|---|---|---|
| HEAD | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` | `bc967b35fccaf7bb6c1b3a4b31e356000bd788ee` | ✅ unchanged |
| Last commit | `bc967b3 fix: close Phase 42 product acceptance defects` | same | ✅ no commit, no push |
| Dirty-file count (`git status --short`) | 174 | 174 | ✅ unchanged — both edited files were already entries in the pre-existing dirty set (`orders/page.tsx` = tracked-modified from earlier phases; `orders-page.test.tsx` = untracked from earlier phases), so no new file appeared |
| `package-lock.json` SHA-256 | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` | ✅ unchanged |
| `FINAL_CLIENT_FINDINGS_TRIAGE.md` | present (untracked) | present (untracked), intact | ✅ untouched |
| Files modified by this task | — | exactly 2: `apps/web/src/app/dashboard/orders/page.tsx`, `apps/web/src/__tests__/orders-page.test.tsx` | ✅ no unrelated files, no dependencies, no migrations, no deployment |

## 8. Final Status

**FIX VERIFIED — READY FOR FINAL PRESENTATION**

F-ACC-06 is fixed with a one-line client-only guard reusing the existing `confirmed_at` condition, proven by 3 new focused unit tests (7/7 in-file, 43/43 full web suite, type-check clean, lint 0 errors) and by an end-to-end walkthrough in the real staff console: unconfirmed pending orders no longer offer Prepare; confirming reveals it; preparing proceeds normally. All repository and data-safety constraints held; the remaining B-classified limitations stay documented in `FINAL_CLIENT_FINDINGS_TRIAGE.md` §5 for presenter awareness, and the C-classified residue remains queued for a separate sanctioned cleanup.
