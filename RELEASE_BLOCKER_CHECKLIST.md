# UniServe — Release Blocker Checklist

**Generated:** 2026-10-11 · **Basis:** `FINAL_PRE_DEPLOYMENT_REPORT.md` + this gate's read-only runtime inspection.
**Scope:** only the items that remain actionable. Verified/defect-closed items (D1, D3, D4, D5–D8, stale chunk, full suites, build) are **not** repeated here — see the report §1/§11.
**Invariants honored:** no deploy, no production-DB write, no credential exposure/rotation, no volume or image removal, all Git changes preserved. HEAD `bc967b3` unchanged.

> **Deployment readiness is NOT claimed.** Two release-critical facts remain unverified by design
> (they require operator-owned external inputs): the **live persistence wiring** of the running API
> container and the **real public API origin**. Both are tracked below as essential blockers.

---

## How to read this checklist
- **P0 — Essential launch blocker:** release cannot go live until resolved.
- **P1 — Essential (launch-degraded):** app launches but a core flow is dead for all users.
- **P2 — Optional / post-launch:** safe to defer; no launch-blocking impact.
- Status values: **OPEN** (needs operator action) · **VERIFIED-BLOCKED** (correctly waiting on an external input; nothing to fix in-repo).

---

## P0 — Essential launch blockers

### B-A. Real public API + frontend origins are still placeholders (`example.com`)
- **Status:** OPEN (operator decision required)
- **Verified this gate:**
  - `infrastructure/caddy/Caddyfile` (tracked) still carries the literal comment *"Replace example.com with your actual domains."* and serves `api.example.com` / `app.example.com` — **placeholders, not real domains.**
  - `.env.production` (non-secret lines only) has `CORS_ORIGINS=["http://app.localhost","http://localhost","http://localhost:3000","http://localhost:8081","https://app.example.com"]` — 5 exact origins, **no wildcard**; the only HTTPS entry is the placeholder `https://app.example.com`.
  - The validated local build used `NEXT_PUBLIC_API_URL=https://api.example.com/api/v1` **as a placeholder** — it is not a real, reachable production endpoint.
- **Conclusion:** `api.example.com/api/v1` is **confirmed a placeholder**, not a real intended endpoint. The exact final origins are operator-chosen; the required set is derived below.
- **Exact prerequisites to resolve:**
  1. Choose the real domains, e.g. `api.<yourdomain>` and `app.<yourdomain>` (A/AAAA records).
  2. Update `NEXT_PUBLIC_API_URL` to `https://api.<yourdomain>/api/v1` for the server-side web build.
  3. Replace both `example.com` blocks in `infrastructure/caddy/Caddyfile` with the real domains (Caddy auto-TLS via Let's Encrypt).
  4. Rewrite `CORS_ORIGINS` in `.env.production` to exactly the origins that will serve the web client — at minimum `https://app.<yourdomain>` plus any explicit dev origins you still want. **Keep it an explicit array; do not introduce a wildcard.**
  5. Confirm `EXPO_PUBLIC_API_BASE_URL` for mobile = `https://api.<yourdomain>/api/v1` at EAS build time (do not hardcode a LAN IP into production config).
- **Evidence:** `infrastructure/caddy/Caddyfile`; `.env.production` `CORS_ORIGINS` line; report §5, §9, §11.

### B-B. Live API container is NOT wired to the `menu_images_data` volume
- **Status:** OPEN — **release-critical image-persistence configuration is not live yet** (explicitly called out by the task; readiness cannot be claimed until the *running* container uses the volume).
- **Verified this gate (read-only Docker inspection):**
  - Running container `uniserve_api` image = `sha256:acf61fa…` = `uniserve-prod-api:latest`. **`Mounts=[]` — empty.** `/app/app/static/food` is the **ephemeral container layer**, *not* the `menu_images_data` volume.
  - The container was created `2026-10-09T06:15:55Z` and last started `2026-10-11T09:09:46Z`, i.e. it predates the D1 compose fix, so it never received the new mount.
  - `docker-compose.prod.yml` **intends** `volumes: [menu_images_data:/app/app/static/food]` on the `api` service and `docker compose -f docker-compose.prod.yml config --quiet` → **exit 0** (valid). The fix is correct **in config but not yet applied to the running container**.
  - Image `uniserve-prod-api:latest` bakes **27** files into `/app/app/static/food` at build time (`COPY . .`). The **6** restored images exist only in (a) the running container layer via `docker cp` and (b) the pre-seeded volume — **not** in the image.
- **Two separate copies, not one persistence path:** named volume `uniserve-prod_menu_images_data` = **33 files**; running container layer = **33 files**. They are duplicated right now; the volume is only authoritative once the API container is recreated *with the mount*.
- **`docker cp` runtime-only deltas (all 6):** `1a107b9f…69c6.jpg`, `341d2569…261.jpg`, `7eff44d8…906.jpg`, `b2f95203…9a2.jpg`, `957fdd11…12e.png`, `ef2d15aa…96cf.png`. These live in the container layer only and are **not** in the image; a plain `docker run uniserve-prod-api:latest` would serve 404 for them until the volume is mounted.
- **All 33 image URLs verified this gate:** `URLS_TOTAL=33 HTTP_200=33 FAILED=0` against the live API.
- **Exact prerequisites to resolve (operator — this is a deploy action, deliberately NOT done here):**
  1. Do **not** manually recreate the running container for this alone; the mount takes effect at the next real `docker compose -f docker-compose.prod.yml up -d`.
  2. **Guard against the empty-volume edge:** if the operator had instead created the volume empty, Docker's first-mount auto-seed would populate it from the image's 27 baked files and the 6 restored images would 404. The volume is **already pre-seeded with all 33**, so this risk is neutralized — but the operator must mount the *existing* `uniserve-prod_menu_images_data` volume, **never** `down -v` / `volume rm` it, and never let a fresh empty volume replace it.
  3. Optional hardening (recommended before first deploy, not required): rebuild the API image so the 6 restored photos are baked in (image goes 27 → 33), making even an empty-volume first run fully correct. Requires a rebuild = a deploy step.
  4. After the real `up`, re-run `docker inspect uniserve_api --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{end}}'` and confirm it prints `uniserve-prod_menu_images_data /app/app/static/food`, then re-verify the 33 URLs.
- **Evidence:** `docker inspect uniserve_api` (image, Created/StartedAt, Mounts=[]), `docker images --no-trunc`, `docker compose … config --quiet`=0, volume vs container file counts (33/33), image layer count (27), `apps/api/Dockerfile` (`COPY . .`), report §4.

### B-C. Server-side production web build with the real API URL
- **Status:** OPEN (blocked on B-A domain choice)
- **Verified this gate:** the local `apps/web/out/` is a **validation** build using the placeholder `https://api.example.com/api/v1` (exit 0, 24 HTML + 23 RSC `.txt`, zero `localhost` refs). It must be rebuilt on the server with the real URL from B-A.
- **Exact prerequisites:** run the web build on the VPS with `NEXT_PUBLIC_API_URL=https://api.<yourdomain>/api/v1`; the Caddy service already bind-mounts `./apps/web/out:/srv:ro`, so the rebuilt `out/` is served automatically.
- **Evidence:** report §9; `docker-compose.prod.yml` caddy service `volumes`.

### B-D. Infrastructure does not exist yet (VPS / SSH / DNS / reverse-proxy domains / Git remote)
- **Status:** VERIFIED-BLOCKED (external — `DEPLOYMENT_BLOCKERS.md` B1–B9)
- **What's missing:** no VPS, no SSH access, no registered domains, no DNS records, real Caddyfile domains, no git remote. Caddy/HTTPS cannot come up until B-A domains + a host exist.
- **Exact prerequisites:** provision VPS → point DNS A/AAAA for `api.`/`app.` → clone repo on server → apply `.env.production` → `docker compose -f docker-compose.prod.yml up -d --build`.
- **Evidence:** `DEPLOYMENT_BLOCKERS.md`; no remote configured (`git remote` empty).

---

## P1 — Essential (launch-degraded): core flow dead for all users

### B-E. SMTP credentials absent → NO user can ever activate or log in
- **Status:** OPEN — **this is on the critical auth path, not optional.**
- **Verified this gate (code-level):**
  - Registration sets `status=AccountStatus.PENDING_VERIFICATION` (`auth/service.py:145`).
  - Login rejects anything not `ACTIVE` (`auth/service.py:568, 608` → `EmailNotVerifiedError`).
  - The **only** transition to `ACTIVE` is a successful OTP check (`auth/service.py:434`).
  - The OTP is created in-DB and emailed; the provider `SMTPEmailProvider` **fails closed** — if `SMTP_HOST`/`SMTP_FROM_EMAIL` are empty it logs and returns failure (`core/email.py:91, 117–124`); the plaintext OTP is **never** returned to the client nor logged. `DevelopmentEmailProvider` (which surfaces codes) is dev/testing only (`core/email.py:179`).
  - No admin/seed bypass: no code path sets `is_verified=True` / `ACTIVE` outside OTP verification.
  - Startup TLS guard: `SMTP_TLS_MODE=none` is rejected when `APP_ENV=production` (`config.py:226–237`).
- **Conclusion:** with SMTP unset, registration succeeds but **no account can verify**, so **login is impossible for every user**. SMTP is an **essential launch blocker** (P1 — the app boots and the API is healthy, but the product is unusable end-to-end).
- **Exact prerequisites:** provision an external SMTP account; set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` in `.env.production`; leave `SMTP_TLS_MODE=starttls` (or `ssl`); do **not** set `none` in production. Then test one registration → verify the OTP email arrives → login.
- **Evidence:** report §5/§11; `core/config.py:136–141, 226–237`; `core/email.py`; `auth/service.py:145, 434, 568, 608`.

---

## P2 — Optional / post-launch (no launch-blocking impact)

### B-F. Payment provider credentials (optional — fail-closed 503)
- **Status:** VERIFIED-BLOCKED (optional by design, `DEPLOYMENT_BLOCKERS.md` B10)
- **Verified:** `PAYMENT_MERCHANT_ID/API_KEY/API_SECRET/WEBHOOK_SECRET/CALLBACK_URL` are absent from `.env.production` and the running container env (names only; no values read). Online payment fails closed with **503**; cash-on-delivery and the rest of the order flow are unaffected.
- **Exact prerequisites (only when enabling online payments):** obtain provider credentials → set the five `PAYMENT_*` values → set `PAYMENT_CALLBACK_URL=https://api.<yourdomain>/api/v1/payments/webhook` → configure the provider webhook secret → test a sandbox transaction + refund.

### B-G. EAS credentials / on-device build (optional for web launch)
- **Status:** VERIFIED-BLOCKED (no Expo account / physical device in this environment)
- **Verified:** mobile was validated via `jest --ci` (51/51) and `tsc` (exit 0) only — no `eas build`, no on-device run.
- **Exact prerequisites (when shipping mobile):** an Expo account + `eas login`; set the EAS build channel/`EXPO_PUBLIC_API_BASE_URL` to the real API origin; `eas build --platform android|ios`; submit store credentials.

### B-H. Orphan table `phase28a_rehearsal_marker` (operator data decision)
- **Status:** OPEN (operator decision — a production-data change, deliberately not performed here)
- **Verified:** `uniserve_prod` still contains `phase28a_rehearsal_marker` (1 row) though its `drop_table` was removed from the migration chain. The DB is at head `0013` and the API runs healthy — harmless drift. `alembic check` reports "new upgrade operations detected" until it is resolved.
- **Exact prerequisites:** operator decides — either `DROP TABLE phase28a_rehearsal_marker;` (a deliberate production-DB write) or leave it (accepting that `alembic check` keeps flagging it). **Do NOT run `alembic upgrade` blindly to "fix" it.**

### B-I. `.env.production` review / rotation before server provisioning
- **Status:** OPEN (operator, pre-provisioning hygiene — B7)
- **Verified:** values were never printed; only key names and the non-secret `CORS_ORIGINS`/`APP_ENV`/`APP_DEBUG`/`APP_HOST` lines were read. `APP_ENV=production`, `APP_DEBUG=false` confirmed.
- **Exact prerequisites:** operator reviews every secret in `.env.production`, rotates anything provisioned for staging, and confirms strong `POSTGRES_PASSWORD`, `APP_SECRET_KEY`, `JWT_SECRET_KEY` before the first server `up`.

---

## Advisory (informational, no action required)

- **`ENOWORKSPACES` dev lockfile "patch" warning:** benign pre-existing npm-workspaces interaction; no effect on build or runtime.
- **Phase 8 live-API D7/D8 scripts** (`artifacts/phase-8/task10_d7_verify.py`, `task10_d8_verify.py`): require an isolated API + test DB; not re-executed this gate. The code-level fixes are confirmed present and covered by the full backend suite (875 passed / 5 skipped).
