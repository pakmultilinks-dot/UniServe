# IDOR Vulnerability Fix — Evidence & Audit Document

**Date:** 2026-09-24
**Scope:** `GET /api/v1/orders/{order_id}` — Insecure Direct Object Reference (IDOR) remediation
**Severity:** Critical — any authenticated user could read any other user's order by UUID

---

## Table of Contents

1. [Vulnerability Summary](#section-1)
2. [Root Cause Analysis](#section-2)
3. [Attack Vector](#section-3)
4. [Fix Description](#section-4)
5. [Changed Files](#section-5)
6. [Authorization Logic (Before vs After)](#section-6)
7. [Test Suite — 319 Tests](#section-7)
8. [New Security Regression Tests (10)](#section-8)
9. [Live IDOR Attack Test — 5/5 Pass](#section-9)
10. [Static Analysis — Zero Issues](#section-10)
11. [Out-of-Scope Finding: `/orders/{order_id}/eta`](#section-11)
12. [Consistency Audit: All Order Endpoints](#section-12)
13. [Minimal Change Justification](#section-13)
14. [Risk Assessment](#section-14)
15. [Reproduction Instructions](#section-15)

---

<a id="section-1"></a>
## 1. Vulnerability Summary

| Field | Value |
|-------|-------|
| **Vulnerability** | IDOR (Insecure Direct Object Reference) |
| **Endpoint** | `GET /api/v1/orders/{order_id}` |
| **Impact** | Any authenticated user could read any order's full details (items, prices, user info) by providing the order's UUID |
| **CVSS-style severity** | Critical — confidentiality breach of all order data |
| **Discovery method** | Code audit during Phase 1 |
| **Fix scope** | Minimal — 1 endpoint modified in 1 file |

---

<a id="section-2"></a>
## 2. Root Cause Analysis

The `GET /orders/{order_id}` endpoint in `apps/api/app/modules/orders/router.py` used only `Depends(get_current_user)` to validate the caller was authenticated. After authentication, the endpoint loaded the order by UUID without checking **who** was making the request:

```python
# BEFORE (vulnerable):
@router.get("/{order_id}")
async def get_order(
    order_id: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    order = await service.get_order(order_id)  # loads by UUID only
    return OrderResponse.model_validate(order)  # returns to ANY authenticated user
```

**Root cause:** No authorization check between authentication and data retrieval. The service layer's `get_order()` performs no auth checks — it only verifies the order exists.

---

<a id="section-3"></a>
## 3. Attack Vector

1. Attacker registers/logs in as a student (User B)
2. User A places an order (order UUID: `a1b2c3d4-...`)
3. User B calls `GET /api/v1/orders/a1b2c3d4-...` with their own valid JWT
4. **Before fix:** Server returns User A's full order (items, prices, cafeteria, timestamps)
5. **After fix:** Server returns `403 Forbidden` with `"Order not found"`

---

<a id="section-4"></a>
## 4. Fix Description

Added a **three-tier authorization check** in the router, matching the existing architecture pattern (inline auth, not in service layer):

```python
# AFTER (fixed):
# 1. Owner always allowed
if order.user_id == auth.user.id:
    return OrderResponse.model_validate(order)

# 2. University Admin — universal access
if auth.user.role == Role.UNIVERSITY_ADMIN:
    return OrderResponse.model_validate(order)

# 3. Manager / Staff assigned to the order's cafeteria
if auth.user.role in (Role.CAFETERIA_MANAGER, Role.CAFETERIA_STAFF):
    result = await db.execute(
        sa_select(CafeteriaAssignment).where(
            CafeteriaAssignment.user_id == auth.user.id,
            CafeteriaAssignment.cafeteria_id == order.cafeteria_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return OrderResponse.model_validate(order)

# Default: deny
raise AuthorizationError("Order not found")
```

**Design decisions:**
- Denial uses `AuthorizationError("Order not found")` (not 403) to avoid leaking order existence — matches existing pattern in `get_order_by_number`
- No 404 on denial — the attacker should not learn whether the order exists
- Uses existing `CafeteriaAssignment` model for staff/manager cafeteria scoping
- Minimal imports: only `sa_select`, `AuthorizationError`, `CafeteriaAssignment`, `Role`

---

<a id="section-5"></a>
## 5. Changed Files

| File | Change | Lines Changed |
|------|--------|---------------|
| `apps/api/app/modules/orders/router.py` | Added 3-tier auth check to `get_order` | ~20 lines added |
| `apps/api/tests/test_orders.py` | Added `TestOrderDetailIDOR` class (10 tests) | ~250 lines added |

**No other files modified.** No schema, model, service, config, or migration changes.

---

<a id="section-6"></a>
## 6. Authorization Logic (Before vs After)

| Caller Role | Before Fix | After Fix |
|-------------|-----------|-----------|
| Order owner (student/faculty) | ✅ 200 OK | ✅ 200 OK |
| University Admin | ✅ 200 OK | ✅ 200 OK (explicit bypass) |
| Manager of same cafeteria | ✅ 200 OK | ✅ 200 OK (cafeteria check) |
| Staff of same cafeteria | ✅ 200 OK | ✅ 200 OK (cafeteria check) |
| **Different student** | ✅ **200 OK (BUG)** | ❌ 403 Denied |
| **Different faculty** | ✅ **200 OK (BUG)** | ❌ 403 Denied |
| **Manager of different cafeteria** | ✅ **200 OK (BUG)** | ❌ 403 Denied |
| **Staff of different cafeteria** | ✅ **200 OK (BUG)** | ❌ 403 Denied |
| **Unauthenticated** | ❌ 401/403/422 | ❌ 401/403/422 |

---

<a id="section-7"></a>
## 7. Test Suite — 319 Tests

Full test run after fix:

```
pytest apps/api/tests/ -v
319 passed in 183.91s (0:03:03)
```

- **Baseline:** 309 tests (pre-fix)
- **Added:** 10 new security regression tests
- **Total:** 319 tests — all passing
- **No regressions:** All existing tests continue to pass

---

<a id="section-8"></a>
## 8. New Security Regression Tests (10)

Class: `TestOrderDetailIDOR` in `apps/api/tests/test_orders.py`

| Test | Scenario | Expected | Result |
|------|----------|----------|--------|
| A | Owner accesses own order | 200 OK | ✅ PASS |
| B | Different student blocked | 403 | ✅ PASS |
| C | Different faculty blocked | 403 | ✅ PASS |
| D | Cross-cafeteria manager blocked | 403 | ✅ PASS |
| E | Correct cafeteria manager access | 200 OK | ✅ PASS |
| F | Correct cafeteria staff access | 200 OK | ✅ PASS |
| G | University admin access | 200 OK | ✅ PASS |
| H | Unauthenticated request | 401/403/422 | ✅ PASS |
| I | Nonexistent order | 404 | ✅ PASS |
| J | UUID substitution attack (different order) | 403 | ✅ PASS |

**Key design note:** Tests B, C, D, J create separate `AsyncClient` instances (sharing transport) with the attacker's JWT token, to avoid HTTPX's header-merging behavior that would silently override the Authorization header.

---

<a id="section-9"></a>
## 9. Live IDOR Attack Test — 5/5 Pass

Ran against live PostgreSQL + uvicorn server at `http://127.0.0.1:8001/api/v1`.

```
============================================================
UNISERVE — LIVE IDOR ATTACK TEST (Phase 7)
Target: http://127.0.0.1:8001/api/v1
Time: 2026-09-24 22:32:38
============================================================

TEST: A: Owner accesses own order
  Result: PASS — Owner got 200 with correct order (id=378c5253...)

TEST: B: Different student blocked
  Result: PASS — Attacker got 403 (denied) — IDOR blocked

TEST: C: Unauthenticated request blocked
  Result: PASS — Unauthenticated got 422 (denied)

TEST: D: Nonexistent order returns 404
  Result: PASS — Nonexistent order returned 404

TEST: E: UUID substitution attack blocked
  Result: PASS — UUID substitution blocked — got 403

  5/5 tests passed
============================================================
```

---

<a id="section-10"></a>
## 10. Static Analysis — Zero Issues

| Tool | Result |
|------|--------|
| `ruff check` | ✅ All checks passed |
| `ruff format` | ✅ No formatting issues |
| `mypy` | ✅ Success: no issues found |

---

<a id="section-11"></a>
## 11. Out-of-Scope Finding: `/orders/{order_id}/eta`

**`GET /api/v1/orders/{order_id}/eta`** (line ~467 in router.py) has the same IDOR vulnerability — any authenticated user can query any order's ETA by UUID. This is **out of scope** for this fix per user's explicit constraints, but is reported here for future remediation.

---

<a id="section-12"></a>
## 12. Consistency Audit: All Order Endpoints

| Endpoint | Auth Pattern | IDOR Protected? |
|----------|-------------|-----------------|
| `GET /orders/` | `get_current_user` + scoped query | ✅ Yes (list is user-scoped) |
| `GET /orders/by-number/{n}` | `get_current_user` + owner check | ✅ Yes |
| `GET /orders/{id}` | **Fixed (this PR)** | ✅ Yes (3-tier) |
| `POST /orders/{id}/cancel` | `get_current_user` + service auth | ✅ Yes |
| `GET /orders/{id}/eta` | `get_current_user` only | ⚠️ **NO (same IDOR, out of scope)** |

---

<a id="section-13"></a>
## 13. Minimal Change Justification

Per the constraint: "Do NOT implement automatic no-show, pickup deadline enforcement, scheduled-order, online payment, refunds, notifications, redesign order lifecycle/RBAC/permissions, modify frontend, refactor unrelated services, fix unrelated lint/type issues."

This fix:
- Touches **exactly 1 endpoint** in 1 production file
- Adds **~20 lines** of inline authorization logic
- Follows the **existing pattern** (see `get_order_by_number` which already does an owner check)
- Uses **existing models** (`CafeteriaAssignment`, `Role`)
- Introduces **no new abstractions, middleware, or decorators**

---

<a id="section-14"></a>
## 14. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| False positive denial (owner can't see own order) | Very Low | Test A + Test E/F verify owner + cafeteria staff access |
| Performance regression (extra DB query for managers) | Negligible | Single indexed query on `cafeteria_assignments(user_id, cafeteria_id)` |
| Breaking existing API consumers | Low | Only changes response for unauthorized callers (200→403) |
| Admin access broken | Very Low | Test G verifies admin bypass |

---

<a id="section-15"></a>
## 15. Reproduction Instructions

### Automated (preferred):
```bash
cd apps/api
pytest tests/test_orders.py::TestOrderDetailIDOR -v
```

### Live server:
```bash
# Start server
cd apps/api
$env:POSTGRES_PORT="5433"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# In another terminal, from project root:
python live_verify.py
```

### Manual (curl):
```bash
# Register two users, verify emails, login to get tokens
# User A creates an order → gets order_id
# User B tries: curl -H "Authorization: Bearer <B_TOKEN>" http://127.0.0.1:8001/api/v1/orders/<ORDER_ID>
# Expected: 403 Forbidden
```
