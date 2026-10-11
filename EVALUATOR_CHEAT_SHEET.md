# UniServe — Evaluator Cheat Sheet

**Purpose:** 15 anticipated evaluator questions with answers grounded in the **actual implementation** (Phase 62 verified state). Answers are honest — including limitations. No marketing language.

**Rule of thumb:** if asked something not covered here, answer from what the running system actually does, then say *"it's in our known-limitations register"* if it's an open item. Never invent capabilities.

---

### Q1. What problem does UniServe solve?

**A:** Campus cafeteria ordering at Lahore Garrison University is manual — students and faculty queue during short breaks, staff lose track of rush orders, managers have no visibility, and the university has no auditable record of orders, payments, or refunds. UniServe replaces this with one platform: mobile ordering for customers, real-time fulfillment consoles for staff/managers, and a governed admin layer with audit logging.

---

### Q2. Why five roles instead of one simple ordering app?

**A:** Each campus stakeholder has a genuinely different job and different data boundary. Students/faculty *consume* (mobile). Staff *fulfill* (one cafeteria's queue). Managers *operate* (their cafeteria). The university *governs* (system-wide users, refunds, reports, audit). Collapsing these into one interface would either leak operational data to customers or make staff hunt through admin screens. Role-based design also maps directly onto our RBAC enforcement — every role has API-level guards, not just different menus.

---

### Q3. Why can faculty access both cafeterias while students pick one?

**A:** Faculty are mobile across campus — they teach in different buildings and eat where convenient, so the cafeteria switcher offers both Faculty Cafeteria (Administration Block) and Student Cafeteria (Block B). Students are scoped to the Student Cafeteria by role policy. This is enforced in the data the API returns per role, and demonstrated live in the faculty mobile session (`presentation/04-faculty/faculty-mobile-cafeteria-picker.png`).

---

### Q4. How is authorization actually enforced — is it just hidden menus?

**A:** Two layers, both verified. **UI layer:** route guards redirect unauthorized navigations (staff visiting `/dashboard/admin/users` are redirected to `/dashboard`; managers get "Access denied" on admin reports — screenshots in `presentation/12-security/`). **API layer:** every sensitive endpoint requires a valid JWT and checks the role server-side — our RBAC probe suite ran 13 forbidden cross-role calls and **all 13 returned HTTP 403**. Hiding a button is not security; rejecting the call is.

---

### Q5. Walk me through an order's lifecycle.

**A:** `PENDING → PREPARING → READY → COMPLETED`. A student places an order from the mobile app; it appears in the cafeteria staff's Order Queue as PENDING; staff move it to PREPARING when they start, then READY when it's on the shelf; completion closes it. Our end-to-end rehearsal (order #31, cash, PKR 80) walked this exact path and left a **7-event audit trail** plus **2 notifications** to the order owner. Cancellation is also a state — visible in student order history with status badges.

---

### Q6. Are payments real? What about refunds?

**A:** **Payments in the demo are test/seed data and E2E-test transactions** — no real money has moved; order #31 was a cash order. The online-payment path (JazzCash) is configured **fail-closed**: if the provider is unconfigured or unreachable, the API returns **503** rather than pretending an order was paid — we would rather refuse than lie about money. Refunds run through the admin Refund Management console against recorded payments; the demo database has 4 refund records from test flows. Going live requires a real payment-merchant integration — that's roadmap, not a claim.

---

### Q7. How do notifications work?

**A:** Order-status transitions generate notifications to the order owner, delivered to the in-app notification inbox on mobile (unread badge + Mark All Read — see `presentation/03-student/mobile-notifications.png`). Admins additionally have a Broadcast console for university-wide messages. **Engineering honesty:** our first implementation had a delivery-gap defect found during Phase 61 verification; it was fixed in Phase 61A and re-verified — the E2E order produced 2 notifications to its owner. Current delivery is in-app; mobile push is roadmap.

---

### Q8. What happens if an item is unavailable or a menu isn't published?

**A:** The app never fabricates availability. If no menu is published for the current date, the mobile app shows the honest empty state — *"Menu not published yet — today's menu hasn't been published. Check back later!"* (visible in the demo because the latest published menu is dated 2026-10-06). Staff/managers publish menus through their console; students see only what's actually published. For unavailable items, staff manage availability through menu/inventory administration — the queue only shows orders that were validly placed.

---

### Q9. What happens if an order is delayed or a cafeteria closes?

**A:** Status stays truthful — an order sits in its actual state (e.g., PREPARING) until staff advance it; students see the real status in order history rather than a fake "completed." The notification system carries status-change messages (the faculty inbox in the demo contains cafeteria-operation notifications). Cafeteria operational state is managed by staff/managers; the admin can see active-order counts system-wide on the dashboard.

---

### Q10. How is personal data protected?

**A:** Authentication is JWT-based (access + refresh tokens); the API rejects any request without a valid token (verified live — unauthenticated calls return 401 `AUTHENTICATION_ERROR`). Sessions are tracked (383 sessions in the demo DB) and the profile screen offers "Sign Out All Devices." Sensitive actions are recorded in an append-only audit log (844 events). Role guards mean a student token cannot read other users' data or admin endpoints (13/13 probes 403). Passwords for demo accounts are committed test fixtures — in production these would be real credentials hashed server-side.

---

### Q11. What's your testing story?

**A:** Phase 62 verification (all automated, reproducible): backend **872 Pytest passed / 5 skipped**; web console **40/40 Vitest**, TypeScript **0 errors**, ESLint **0 errors**; mobile **34/34 Jest**, TypeScript **0 errors**, ESLint **0 errors**; shared-types **13/13**; RBAC forbidden probes **13/13 → 403**. Plus human role rehearsals: admin **8/8**, manager **7/7**, staff **5/5**, student **4/4**, faculty **3/3** browser/API scenarios. And one full E2E order lifecycle with audit-trail verification. We also test the *negative* paths — that's how we caught the notification defect before this demo.

---

### Q12. What technologies did you use, and why?

**A:** **FastAPI (Python)** for the API — async-first, fast, typed; **PostgreSQL 16** with SQLAlchemy async and Alembic migrations (at 0013) for durable relational data; **Next.js 14** for the role-scoped web console; **React Native 0.86.3 + Expo SDK 57** for the mobile app — one codebase for iOS/Android (demoed here via Expo web since this machine has no emulator); **JWT + RBAC** for authn/authz; **Docker Compose** for reproducible local/prod-parity runtime; **Pytest / Vitest / RTL / Jest** for the test pyramid. Deliberately mainstream stack — the discipline is in the RBAC layer, audit trail, and migrations, not novelty.

---

### Q13. What are the current limitations?

**A (short version):** 15 open items are documented in our known-limitations register; **none blocks the demonstrated functionality**. The demo-visible ones: (1) no live payment-merchant integration — online payments are fail-closed by design; (2) test-residue records in demo data — e.g., "Phase 56 E2E Cafeteria" in cafeteria lists, a few stale pending-payment orders, seeded accounts in the user list; (3) sparse menu dietary/allergen metadata (3/35 and 2/35 items tagged); (4) in-app notifications only — no mobile push yet. Each item has an owner and severity in `FINAL_KNOWN_LIMITATIONS.md`.

---

### Q14. What would you do next to take this to production?

**A:** In priority order: (1) real payment-merchant integration with the fail-closed behavior already in place as the safety net; (2) production deployment hardening — the Docker Compose setup exists, but real TLS, secrets management, backups, and monitoring need a deployment pass; (3) test-data cleanup — remove E2E residue (cafeteria, stale orders, seed accounts) via controlled scripts, not manual deletes; (4) complete menu dietary/allergen metadata; (5) mobile push notifications (in-app delivery already works); (6) load/performance testing — we have not claimed production-scale performance numbers, and won't until we measure them.

---

### Q15. What's the single most important thing to take away from this demo?

**A:** UniServe is a **running, verified system — with an honest register of what it isn't**. Every screenshot came from the live application; 959+ automated tests pass; RBAC is enforced at the API (13/13 403s), not just the UI; an order walked its full lifecycle with a 7-event audit trail; and where something isn't finished — payments, test residue, menu metadata — we say so plainly instead of demoing around it. That combination — working software plus honest accounting — is the actual deliverable.

---

## Quick-reference facts (for rapid-fire questions)

| Fact | Value |
|---|---|
| Backend tests | 872 passed / 5 skipped (Pytest) |
| Web tests | 40/40 (Vitest) · TS 0 errors · ESLint 0 errors |
| Mobile tests | 34/34 (Jest) · TS 0 errors · ESLint 0 errors |
| Shared-types tests | 13/13 (Vitest) |
| RBAC forbidden probes | 13/13 → HTTP 403 |
| Role rehearsals | admin 8/8 · manager 7/7 · staff 5/5 · student 4/4 · faculty 3/3 |
| E2E order | #31 · cash PKR 80 · PENDING→PREPARING→READY→COMPLETED · 7-event trail · 2 notifications |
| Demo DB census | 18 users · 52 orders · 39 payments · 4 refunds · 150 notifications · 844 audit events · 383 sessions |
| Migrations | Alembic 0013 |
| Known limitations | 15 open (F-61-02 … F-61-16) · none demo-blocking |
| Stack | FastAPI · PostgreSQL 16 · SQLAlchemy async · Next.js 14 · React Native 0.86.3 + Expo 57 · JWT+RBAC · Docker Compose |
| Latest published menu (demo DB) | 2026-10-06 (mobile correctly shows empty state for later dates) |
