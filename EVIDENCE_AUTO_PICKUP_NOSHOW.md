# Phase 12 — Automatic Pickup Expiry & No-Show Processing: Evidence Document

**Date:** 2026-09-25
**Scope:** Live verification of automatic pickup expiry against real PostgreSQL
**Result:** ✅ 9/9 tests passed
**Infrastructure:** Docker PostgreSQL (`uniserve_postgres`, port 5433), uvicorn on port 8001

---

## Table of Contents

1. [Feature Summary](#section-1)
2. [Architecture Overview](#section-2)
3. [Configuration](#section-3)
4. [Test Results — 9/9 PASS](#section-4)
5. [Test-by-Test Evidence](#section-5)
6. [Bugs Found & Fixed During Verification](#section-6)
7. [Key Implementation Files](#section-7)
8. [Safety & Concurrency Guarantees](#section-8)
9. [Out-of-Scope Items](#section-9)
10. [Reproduction Instructions](#section-10)

---

<a id="section-1"></a>
## 1. Feature Summary

UniServe now **automatically processes expired pickup deadlines** via a background worker. When a customer does not collect a READY order within the pickup window:

1. The order is marked as **uncollected** (sets `uncollected_at` timestamp).
2. A **NoShow** record is created linking the user, order, and cafeteria.
3. The user's `no_show_count` is incremented.
4. After exceeding the threshold (3 students / 5 faculty within 30 days), the user is **ordering-suspended** for 7 days (students) or 3 days (faculty).

The mechanism is fully automatic — no manual intervention required.

---

<a id="section-2"></a>
## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  FastAPI Application (main.py lifespan)                  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  _pickup_expiry_worker()                           │  │
│  │  - Runs every 60 seconds                          │  │
│  │  - Creates its own DB session                     │  │
│  │  - Calls OrderService.process_expired_pickups()    │  │
│  │  - Commits after each tick                         │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  process_expired_pickups()                         │  │
│  │  - SELECT FOR UPDATE SKIP LOCKED (PostgreSQL)      │  │
│  │  - Finds READY orders with pickup_deadline <= now   │  │
│  │  - Filters: uncollected_at IS NULL                 │  │
│  │  - Filters: collected_at IS NULL                   │  │
│  │  - Calls mark_uncollected() for each               │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  mark_uncollected()                                │  │
│  │  - Sets uncollected_at timestamp                   │  │
│  │  - Calls record_no_show()                          │  │
│  │  - Creates UNCOLLECTED OrderEvent                  │  │
│  │  - Idempotent: skips if uncollected_at already set │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  record_no_show() (noshow.py)                      │  │
│  │  - Creates NoShow record                           │  │
│  │  - Increments user.no_show_count                   │  │
│  │  - Counts no-shows in 30-day window                │  │
│  │  - Suspends user if threshold met                  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

<a id="section-3"></a>
## 3. Configuration

| Setting | Value | Source |
|---------|-------|--------|
| `PICKUP_WINDOW_MINUTES` | 30 | `config.py` |
| Worker interval (`_PICKUP_CHECK_INTERVAL`) | 60 seconds | `main.py` |
| Student no-show threshold | 3 | `config.py: NOSHOW_STUDENT_THRESHOLD` |
| Student suspension window | 30 days | `config.py: NOSHOW_STUDENT_WINDOW_DAYS` |
| Student suspension duration | 7 days | `config.py: NOSHOW_STUDENT_SUSPENSION_DAYS` |
| Faculty no-show threshold | 5 | `config.py: NOSHOW_FACULTY_THRESHOLD` |
| Faculty suspension window | 30 days | `config.py: NOSHOW_FACULTY_WINDOW_DAYS` |
| Faculty suspension duration | 3 days | `config.py: NOSHOW_FACULTY_SUSPENSION_DAYS` |

---

<a id="section-4"></a>
## 4. Test Results — 9/9 PASS

```
============================================================
RESULTS: 9/9 passed, 0/9 failed
============================================================
```

| # | Test Name | Result | Duration |
|---|-----------|--------|----------|
| 09 | Worker health check | ✅ PASS | <1s |
| 01 | Single order auto-expires | ✅ PASS | ~70s |
| 02 | No-show record created | ✅ PASS | ~70s |
| 03 | Multiple orders expired | ✅ PASS | ~70s |
| 04 | Future deadline not expired | ✅ PASS | ~70s |
| 05 | Collection prevents expiry | ✅ PASS | ~70s |
| 06 | Idempotent processing | ✅ PASS | ~140s |
| 07 | Order event recorded | ✅ PASS | ~70s |
| 08 | Suspension after threshold | ✅ PASS | ~70s |

---

<a id="section-5"></a>
## 5. Test-by-Test Evidence

### Test 09 — Worker health check

**Purpose:** Verify the API server and background worker are running.

**Terminal output:**
```
Health response: {'status': 'healthy', 'service': 'uniserve-api', 'timestamp': '2026-09-25T02:42:40.778602+00:00'}
✅ PASS
```

---

### Test 01 — Single order auto-expires

**Purpose:** A READY order past its `pickup_deadline` is automatically marked uncollected by the background worker.

**Setup:**
1. Register student user (fa23- email pattern)
2. Register admin, create cafeteria, assign manager
3. Create full order: cart → checkout → confirm → prepare → ready
4. Set `pickup_deadline` to 5 minutes ago via DB (`SET pickup_deadline = NOW() - 5 minutes`)
5. Wait 70 seconds for worker cycle

**Assertion:** `uncollected_at IS NOT NULL` in orders table, `no_show_count >= 1`

**Terminal output:**
```
Set pickup_deadline to 5 minutes ago
Waiting for background worker (up to 70s)...
Order automatically marked uncollected at: 2026-09-25 02:43:03.630657+00
No-show count: 1
✅ PASS
```

---

### Test 02 — No-show record created

**Purpose:** An automatically expired order creates a NoShow record in the `no_shows` table.

**Setup:** Same flow as Test 01. Deadline set 10 minutes ago.

**Assertion:** `SELECT id FROM no_shows WHERE user_id = '<user_id>'` returns at least 1 row.

**Terminal output:**
```
Set pickup_deadline to 10 minutes ago
Waiting for background worker (up to 70s)...
NoShow records found: 1
✅ PASS
```

---

### Test 03 — Multiple orders expired

**Purpose:** Multiple expired orders for the same user are all processed in a single worker cycle.

**Setup:**
1. Create 3 separate orders (cart → checkout → confirm → prepare → ready for each)
2. Set all pickup_deadlines to the past (5, 6, 7 minutes ago)
3. Wait 70 seconds

**Assertion:** `no_show_count >= 3`

**Terminal output:**
```
Created 3 orders, set deadlines in the past
Waiting for background worker (up to 70s)...
No-show count: 3
✅ PASS
```

---

### Test 04 — Future deadline not expired

**Purpose:** An order whose `pickup_deadline` is in the future is NOT processed by the worker.

**Setup:**
1. Create order and leave default `pickup_deadline` (~30 min in future)
2. Wait 70 seconds

**Assertion:** `no_show_count == 0`

**Terminal output:**
```
Order ready, deadline is ~30 min in future
Waiting for background worker (up to 70s)...
No-show count: 0 (correct: order not expired)
✅ PASS
```

---

### Test 05 — Collection prevents expiry

**Purpose:** Collecting an order before its deadline prevents expiry processing, even if the deadline is subsequently backdated.

**Setup:**
1. Create order, immediately collect it via `POST /orders/collect`
2. Set `pickup_deadline` to 10 minutes ago (backdate)
3. Wait 70 seconds

**Assertion:** `no_show_count == 0` — collected orders are not processed

**Terminal output:**
```
Order collected successfully
Set pickup_deadline to 10 minutes ago (but order already collected)
Waiting for background worker (up to 70s)...
No-show count: 0 (correct: order was collected)
✅ PASS
```

---

### Test 06 — Idempotent processing

**Purpose:** Processing the same expired order twice does not create duplicate no-shows.

**Setup:**
1. Create order, backdate deadline
2. Wait 70s (first worker cycle — order processed)
3. Wait 65s (second worker cycle — order should be skipped)

**Assertion:** `no_show_count` is the same after both cycles.

**Terminal output:**
```
Set deadline in past, waiting for first worker cycle...
No-shows after first cycle: 1
Waiting for second worker cycle...
No-shows after second cycle: 1 (idempotent ✓)
✅ PASS
```

**Why this works:** `process_expired_pickups()` checks `uncollected_at.is_(None)` — the second cycle sees `uncollected_at` is already set and skips the order.

---

### Test 07 — Order event recorded

**Purpose:** The `UNCOLLECTED` event type is recorded in `order_events` for auto-expired orders.

**Setup:**
1. Create order, backdate deadline
2. Wait 70 seconds

**Assertion:** `SELECT event_type FROM order_events WHERE order_id = '<id>' AND event_type = 'uncollected'` returns a result.

**Terminal output:**
```
Set deadline in past, waiting for worker...
UNCOLLECTED event found: uncollected
✅ PASS
```

**Note:** The `OrderEventType.UNCOLLECTED` enum stores value `"uncollected"` (lowercase) in PostgreSQL.

---

### Test 08 — Suspension after threshold

**Purpose:** After N no-shows (3 for students), the user's `ordering_suspended` flag is set to `true`.

**Setup:**
1. Create 3 orders, backdate all deadlines
2. Wait 70 seconds for worker to process all 3

**Assertion:** `is_user_suspended()` returns `True` AND `no_show_count == 3`

**Terminal output:**
```
Created and expired 3 orders, waiting for worker...
User is suspended: True
No-show count: 3
✅ PASS
```

---

<a id="section-6"></a>
## 6. Bugs Found & Fixed During Verification

Two bugs were discovered during the 2nd run of live verification and fixed immediately:

### Bug 1 — Event type case mismatch (Test 07)

| Field | Value |
|-------|-------|
| **Symptom** | UNCOLLECTED event not found in `order_events` |
| **Root cause** | SQL query searched for `'UNCOLLECTED'` (uppercase) but enum stores `'uncollected'` (lowercase) |
| **Fix** | Changed SQL literal from `'UNCOLLECTED'` to `'uncollected'` in `live_verify_pickup.py` line ~646 |
| **Impact** | Test script only — no production code affected |

### Bug 2 — PostgreSQL boolean representation (Test 08)

| Field | Value |
|-------|-------|
| **Symptom** | User suspension not detected despite `ordering_suspended = true` in DB |
| **Root cause** | `psql -t -A` returns `t`/`f` for boolean columns, not `True`/`False`. The check `result.lower() == "true"` never matched `t` |
| **Fix** | Changed to `result.lower() in ("t", "true")` in `is_user_suspended()` in `live_verify_pickup.py` line ~384 |
| **Impact** | Test script only — no production code affected |

---

<a id="section-7"></a>
## 7. Key Implementation Files

| File | Purpose |
|------|---------|
| `apps/api/app/main.py` (lines 63-95) | Background worker: `_pickup_expiry_worker()` runs every 60s |
| `apps/api/app/modules/orders/service.py` (lines 1278-1350) | `process_expired_pickups()` — SELECT FOR UPDATE SKIP LOCKED |
| `apps/api/app/modules/orders/service.py` (lines 818-878) | `mark_uncollected()` — sets `uncollected_at`, creates NoShow |
| `apps/api/app/modules/orders/service.py` (lines 443-500) | `collect_order()` — race-safe collection with `uncollected_at` guard |
| `apps/api/app/modules/orders/noshow.py` | `record_no_show()` — creates NoShow, increments count, suspends |
| `apps/api/app/core/config.py` (lines 82-91) | Pickup window, no-show thresholds, suspension durations |
| `apps/api/app/modules/orders/models.py` | `OrderEventType.UNCOLLECTED = "uncollected"` (lowercase) |
| `apps/api/migrations/versions/0007_auto_pickup_expiry.py` | Adds `uncollected_at` and `closing_time` columns |
| `apps/api/tests/test_pickup_expiry.py` | 33 automated unit tests for pickup expiry |
| `live_verify_pickup.py` | 9 live verification tests against real PostgreSQL |

---

<a id="section-8"></a>
## 8. Safety & Concurrency Guarantees

### Race condition prevention
- `process_expired_pickups()` uses **`SELECT FOR UPDATE SKIP LOCKED`** on PostgreSQL — concurrent workers safely skip locked rows.
- `collect_order()` uses **`SELECT FOR UPDATE`** — prevents race between collection and automatic expiry.
- The `uncollected_at` check in `collect_order()` (`if order.uncollected_at is not None: raise`) prevents collection of already-expired orders.

### Idempotency
- `mark_uncollected()` checks `if order.uncollected_at is not None: return order` — safe to call multiple times.
- `process_expired_pickups()` filters `Order.uncollected_at.is_(None)` — already-processed orders are excluded from the query.
- Verified by Test 06: second worker cycle produces no duplicate no-shows.

### Session isolation
- The background worker creates its own `async_session_factory()` session — no leaking of request-scoped state.
- Session is committed after each tick and errors are caught per-order to avoid blocking other orders.

---

<a id="section-9"></a>
## 9. Out-of-Scope Items

The following items are explicitly **out of scope** for this feature:

- **Notifications** — users are not notified when their order expires or when they are suspended
- **Scheduled orders** — no special handling for scheduled order pickup deadlines
- **Online payment orders** — no special refund processing for unpaid online orders
- **Refunds** — no automatic refund mechanism for uncollected orders
- **Suspension expiry** — no automatic unsuspension after the suspension period ends

---

<a id="section-10"></a>
## 10. Reproduction Instructions

### Prerequisites
```bash
# Docker PostgreSQL running on port 5433
docker start uniserve_postgres

# API server running on port 8001
cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Run live verification
```bash
cd c:\Users\Lenovo\Documents\Code_PlayGround\UniServe
python live_verify_pickup.py
```

### Run automated test suite
```bash
cd apps/api
python -m pytest tests/ -v  # 352 tests, all passing
```

### Manual DB inspection
```bash
# Check no-show records
docker exec uniserve_postgres psql -U uniserve -d uniserve_dev \
  -c "SELECT * FROM no_shows ORDER BY created_at DESC LIMIT 10;"

# Check user suspension status
docker exec uniserve_postgres psql -U uniserve -d uniserve_dev \
  -c "SELECT university_email, no_show_count, ordering_suspended FROM users WHERE no_show_count > 0;"

# Check order events
docker exec uniserve_postgres psql -U uniserve -d uniserve_dev \
  -c "SELECT order_id, event_type, created_at FROM order_events WHERE event_type = 'uncollected' ORDER BY created_at DESC;"
```
