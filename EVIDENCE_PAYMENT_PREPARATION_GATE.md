# EVIDENCE: Payment-Preparation Gate

## Business Rule

> An online-paid order must not enter preparation unless its payment has
> successfully completed.

## Bug Found

**File:** `apps/api/app/modules/orders/service.py` — `start_preparation()`

**Root cause:** The `start_preparation()` method only checked `order.status == PENDING`
and `order.confirmed_at is not None` before allowing the status transition to
`PREPARING`. It did **not** check whether an online-paid order had a successful
payment record. This meant any confirmed online order — regardless of payment
status (pending, failed, abandoned) — could enter preparation.

## Fix Applied

Added a payment status check in `start_preparation()` between the `confirmed_at`
guard and the status transition:

```python
# Online orders must have a successful payment before preparation
if order.payment_method == PaymentMethod.ONLINE:
    from app.modules.payments.models import Payment, PaymentStatus

    result = await self.db.execute(
        select(Payment).where(Payment.order_id == order.id)
    )
    payment = result.scalar_one_or_none()

    if payment is None:
        raise ValidationError("Payment not found for online order")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise ValidationError(
            f"Cannot start preparation: payment is {payment.status.value}, "
            f"must be succeeded"
        )
```

- Uses lazy import to avoid circular dependency (payments imports orders.models)
- Cash orders skip the payment check entirely (existing behavior preserved)
- Only online orders are subject to the gate

## Live Verification Results

All 22 assertions passed against the running FastAPI server + PostgreSQL:

| Test | Scenario | Result |
|------|----------|--------|
| A.1 | Order created (online) | ✅ PASS |
| A.2 | Payment initiated | ✅ PASS |
| A.3 | Payment webhook accepted | ✅ PASS |
| A.4 | Payment succeeded | ✅ PASS |
| A.5 | Order confirmed | ✅ PASS |
| A.6 | **Preparation started (succeeded payment)** | ✅ PASS |
| B.1 | Payment initiated (pending) | ✅ PASS |
| B.2 | Order confirmed | ✅ PASS |
| B.3 | **Preparation REJECTED (pending payment)** | ✅ PASS |
| C.1 | Payment failed via webhook | ✅ PASS |
| C.2 | Payment status is failed | ✅ PASS |
| C.3 | Order confirmed | ✅ PASS |
| C.4 | **Preparation REJECTED (failed payment)** | ✅ PASS |
| D.1 | Payment initiated (abandoned — no webhook) | ✅ PASS |
| D.2 | Order confirmed | ✅ PASS |
| D.3 | **Preparation REJECTED (abandoned payment)** | ✅ PASS |
| E.1 | Cash order created | ✅ PASS |
| E.2 | Cash order confirmed | ✅ PASS |
| E.3 | **Cash order preparation started** | ✅ PASS |
| F.1 | Order confirmed without payment | ✅ PASS |
| F.2 | **Preparation rejected despite confirmed status** | ✅ PASS |
| F.3 | Payment still not succeeded | ✅ PASS |

**Script:** `live_verify_payment_gate.py`

## Automated Regression Tests

6 new unit tests in `tests/test_payment_preparation_gate.py` — all pass:

| Test | Scenario | Result |
|------|----------|--------|
| succeeded_payment_allows_preparation | Online + SUCCEEDED → prepare OK | ✅ PASS |
| pending_payment_blocks_preparation | Online + PENDING → 400 | ✅ PASS |
| failed_payment_blocks_preparation | Online + FAILED → 400 | ✅ PASS |
| no_payment_record_blocks_preparation | Online + no record → 400 | ✅ PASS |
| cash_order_preparation_not_blocked | Cash order → prepare OK | ✅ PASS |
| confirmed_unpaid_online_order_still_blocked | Confirmed + PENDING → 400 | ✅ PASS |

## Full Regression Suite

- **364 passed** (including 6 new tests)
- **3 pre-existing failures** (time-sensitive scheduled order tests — unrelated to this fix)
- **0 regressions** introduced

## Files Changed

| File | Change |
|------|--------|
| `apps/api/app/modules/orders/service.py` | Added payment gate check in `start_preparation()` |
| `apps/api/tests/test_payment_preparation_gate.py` | New — 6 automated regression tests |
| `live_verify_payment_gate.py` | New — live verification script (22 assertions) |

## Concurrency Safety

The payment query runs within the same async SQLAlchemy session/transaction as the
status update. PostgreSQL READ COMMITTED isolation ensures that a concurrent
preparation attempt would either see the updated status or the committed payment
record — no TOCTOU vulnerability is introduced. This follows the same concurrency
model the original code used for the status check.
