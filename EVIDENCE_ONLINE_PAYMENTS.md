# EVIDENCE: Online Payment Flow — Phase 6 Live Verification

**Date:** 2026-09-25  
**Verifier:** Automated (`live_verify_online_payments.py`)  
**API Server:** `127.0.0.1:8001`  
**Test Provider:** `TestPaymentProvider` (mock — always succeeds)  
**Refund Processor:** `TestRefundProcessor` (mock — always succeeds)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Assertions | 91 |
| Passed | 91 |
| Failed | 0 |
| Pass Rate | **100%** |
| Defects Found | 4 |
| Defects Fixed | 4 |

---

## Test Categories

### 1. Payment Initiation & Checkout (Tests 1.x)
- Online payment checkout creates order + payment record
- Payment status transitions: PENDING → SUCCEEDED
- Webhook processing marks payment SUCCEEDED
- Order status transitions: PENDING → CONFIRMED after webhook
- Redirect URL present for online payment
- Idempotent webhook processing (duplicate events ignored)

### 2. Multi-Item Orders (Test 15)
- Cart with multiple items (Burger + Fries)
- Both items present in checkout response
- Single partial cancel returns updated item list
- Remaining item has correct total
- Second partial cancel cancels entire order

### 3. Webhook Late/Edge Cases (Tests 16-19)
- Late webhook for terminal-state payment handled gracefully (HTTP 200)
- Payment status does not regress from SUCCEEDED to CANCELLED
- Order status does not regress after late webhook
- Webhook for non-existent payment returns appropriate error

### 4. Refund Flow (Tests 3.x, 4.x)
- Refund request creates refund record
- Refund status transitions: PENDING → SUCCEEDED
- Payment status updated to REFUNDED
- Order status updated to REFUNDED
- Full refund prevents re-order with same payment

### 5. Partial Cancel with db.refresh Fix (Tests 15.x)
- After partial cancel, API returns **correct** item count (not stale)
- Remaining item has correct subtotal
- Cancelling all items sequentially cancels the order
- Total is correctly recalculated after each cancel

### 6. Timezone Handling (Tests 5.x, 6.x)
- `WebhookEvent.processed_at` stores timezone-aware UTC datetime
- `Refund.processed_at` stores timezone-aware UTC datetime
- Both fields accept `None` for unprocessed state

### 7. Security (Tests 7.x, 8.x)
- Unauthenticated users cannot initiate payments
- IDOR protection: user cannot pay for another user's order
- Staff cannot initiate payments for student orders

---

## Defects Found & Fixed

### Defect 1: `WebhookEvent.processed_at` — Timezone Naive
- **File:** `apps/api/app/modules/payments/models.py`
- **Issue:** `processed_at` column used `DateTime()` (timezone-naive)
- **Fix:** Changed to `DateTime(timezone=True)`
- **Impact:** All webhook timestamps were being stored without timezone info, causing comparison issues

### Defect 2: `Refund.processed_at` — Timezone Naive
- **File:** `apps/api/app/modules/refunds/models.py`
- **Issue:** `processed_at` column used `DateTime()` (timezone-naive)
- **Fix:** Changed to `DateTime(timezone=True)`
- **Impact:** Same pattern as Defect 1 — refund timestamps lacked timezone info

### Defect 3: Late Webhook for Terminal-State Payment Returns HTTP 400
- **File:** `apps/api/app/modules/payments/service.py`
- **Issue:** `process_webhook()` propagated `ValidationError` from `handle_payment_success()` when a late webhook arrived for a payment already in CANCELLED/REFUNDED state, causing HTTP 400
- **Fix:** Added `try/except ValidationError` in `process_webhook()` to catch terminal-state errors, log a warning, and mark the webhook as processed gracefully (returns HTTP 200)
- **Impact:** Late webhooks no longer cause 400 errors; webhook is acknowledged and ignored

### Defect 4: Partial Cancel Returns Stale Items
- **File:** `apps/api/app/modules/orders/service.py`
- **Issue:** `partial_item_cancel()` deleted an order item and flushed, but did not refresh the SQLAlchemy relationship. The returned order object still contained the deleted item in its stale `items` collection.
- **Fix:** Added `await self.db.refresh(order, ["items"])` after `db.delete(target_item)` + `db.flush()`
- **Impact:** API now returns correct item count and remaining items after partial cancel

---

## Full Test Suite Results

| Metric | Value |
|--------|-------|
| Total Tests | 361 (354 baseline + 7 new regression) |
| Passed | 358 |
| Failed | 3 (pre-existing time-of-day issues) |
| New Regression Tests | 7/7 passing |

### New Regression Tests (`test_regression_phase6.py`)

| # | Test | Status |
|---|------|--------|
| 1 | `test_webhook_event_processed_at_tz_aware` | ✅ PASS |
| 2 | `test_webhook_event_processed_at_none` | ✅ PASS |
| 3 | `test_refund_processed_at_tz_aware` | ✅ PASS |
| 4 | `test_refund_processed_at_none` | ✅ PASS |
| 5 | `test_partial_cancel_returns_correct_item_count` | ✅ PASS |
| 6 | `test_partial_cancel_all_items_cancels_order` | ✅ PASS |
| 7 | `test_partial_cancel_total_recalculated` | ✅ PASS |

### Pre-Existing Failures (Not Caused by Phase 6)
These 3 tests fail due to hardcoded scheduled collection times (`14:00`, `14:30`) that become stale as the day progresses:
- `test_scheduled_order_inventory_reserved_at_prep` — hardcoded `14:30`
- `test_checkout_scheduled_does_not_reserve_inventory` — hardcoded `14:00`
- `test_scheduled_inventory_reserved_at_preparation` — hardcoded `14:00`

---

## Files Modified

| File | Change |
|------|--------|
| `apps/api/app/modules/payments/models.py` | `DateTime(timezone=True)` for `processed_at` |
| `apps/api/app/modules/refunds/models.py` | `DateTime(timezone=True)` for `processed_at` |
| `apps/api/app/modules/payments/service.py` | Graceful handling of terminal-state webhook |
| `apps/api/app/modules/orders/service.py` | `db.refresh(order, ["items"])` after partial cancel |
| `apps/api/tests/test_regression_phase6.py` | **NEW** — 7 regression tests |
| `live_verify_online_payments.py` | **NEW** — 91-assertion live verification script |

---

## Verification Script

The full 91-assertion verification script is at the project root:
```
live_verify_online_payments.py
```

Run with:
```bash
python live_verify_online_payments.py
```

Requires the API server running on `127.0.0.1:8001`.
