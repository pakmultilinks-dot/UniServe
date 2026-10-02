# UniServe — Production Server Provisioning (Phase 40)

**Date:** 2026-10-02 · **Starting commit:** `51e4a9a` · **Tree:** clean throughout
**Outcome:** **Blocked path — no provisioning executed against any server.** No VPS/SSH/domain information was supplied (the owner stated it would be provided separately; an explicit request for it this phase was not answered). Per phase rules, **no server IP, SSH credential, domain, password, API key, SMTP value, or JazzCash value was invented.** All server-independent pre-flight validation was completed and is recorded below.

---

## 1. Server details (no credentials exposed)

| Item | Status |
|---|---|
| Production VPS | **None exists.** `docker context ls` → only local (`default`, `desktop-linux`); no remote Docker host configured |
| SSH | Local keypair `id_ed25519` present; **no `~/.ssh/config`; no server to test against** — SSH access unverified and unverifiable until an address is supplied |
| Owner inputs requested this phase | (a) server IP/hostname (b) SSH method (c) domains + DNS state (d) secrets-handling choice — **awaiting answers** |
| Local build host (for context only) | Docker Desktop on Windows: client/server **29.8.0**, Compose **v5.5.1** — NOT a production server |

## 2. Exact release commit deployed

**Nothing deployed.** Deployment release candidate: **`51e4a9a`** (`docs: prepare production provisioning readiness`; contains Phase 38 hardening `7b3a5e8` + Phase 39 doc). Tree clean; transfer method when SSH exists: `rsync`/`scp` of the local tree to `/opt/uniserve` (no pushed remote exists; automatic push is forbidden — `.git` kept locally on the server for rollbacks, per `DEPLOYMENT_BLOCKERS.md` B9).

## 3. Docker / Compose versions

- **Server:** unknown — no server reached.
- **Local validation host:** Docker 29.8.0 / Compose v5.5.1. Server requirements per runbook: Docker Engine + Compose v2 plugin (installed by `scripts/vps/run-all.sh`).

## 4. Deployment directory

`/opt/uniserve` — **not created** (no server). Procedure (runbook Step 1, `scripts/vps/07-prepare-deployment-dir.sh`) is documented and unmodified.

## 5. Environment configuration status

- **Server `.env.production`: NOT created** — no server, and no owner-supplied values (secrets are owner-governed; generation-on-server per runbook Step 3 remains the documented path; values never printed).
- Local gitignored rehearsal `.env.production`: `APP_ENV=production`, `APP_DEBUG=false`, strong secrets (86/86/43-char class), **no `SMTP_*`/`PAYMENT_PROVIDER` entries**, `CORS_ORIGINS` still rehearsal values — review/rotate + real CORS required before any use (Phase 39 §4/§7.3).
- Fail-closed startup guards verified present in `config.py` at this commit (secrets, `APP_DEBUG`, DB password, SMTP TLS) — unchanged since Phase 38.

## 6. Database / migration status

- **No production database exists anywhere** (no server, no remote context, no production container). Local `uniserve_postgres` = rehearsal stack only.
- First deployment will therefore follow the documented **fresh-database procedure**: compose `up postgres` (init mount + healthcheck) → manual `alembic upgrade head` → verify head. **No reset/seed script will ever target production.**
- Migration head at release commit verified in-repo: versions `0000`–`0009` present, **head `0009`** (`0009_checkout_idempotency.py`). No migrations executed this phase (no target exists — the database-safety rules were honored by having nothing to touch).

## 7. API status

- **Not deployed; not started.** Production API **image build validated locally at `51e4a9a`**: `docker compose -f docker-compose.prod.yml build api` → success, `uniserve-prod-api:latest`, 836 MB (Dockerfile + `requirements.lock.txt` intact). This proves the build step (Phase 40 item 9) will succeed on the server.
- Container-start, DB-connection, health/readiness, 401/RBAC checks (items 11–15) require the server — **blocked**. (Historical live evidence for the earlier RC image: Phases 33/37 — cited as history, not as current verification.)

## 8. Web / Caddy status

- **Not deployed.** `infrastructure/caddy/Caddyfile` retains `api.example.com` / `app.example.com` placeholders — **correct**: real domain values are configured only after the domain is confirmed (rule honored; nothing edited).
- Web static export with the **real** production API URL (item 10) is blocked on the domain (build-time `NEXT_PUBLIC_API_URL`); the export pipeline itself is green (Phase 38 build). Deep-link `try_files` line untouched.

## 9. HTTPS / DNS status

**Blocked — no domains, no DNS, no server.** No HTTPS claim is made. Deployment will either wait for domains, or proceed in the documented pre-HTTPS state (placeholders + HTTP) exactly as the runbook describes; Let's Encrypt issuance is Caddy-automatic once real domains + open 80/443 exist.

## 10. SMTP status

**Unconfigured** — no `SMTP_*` values supplied, none invented, **no fake delivery test performed**. Consequence (documented): with `SMTP_HOST`/`SMTP_FROM_EMAIL` absent, production OTP email delivery fails closed (reported failure, never faked); self-serve OTP onboarding stays unavailable until the owner supplies a real SMTP account (Phase 39 §5).

## 11. Payment status

**Fail-closed confirmed in code at the release commit** (unchanged since `7b3a5e8` — only docs commits follow): with the wired provider being `test`, **both** `POST /api/v1/payments/initiate/{order_id}` and `POST /api/v1/payments/webhook/{provider}` raise HTTP 503 in production (`apps/api/app/modules/payments/router.py`). Cash ordering remains available by design. Guard **not weakened**; no live probe possible without a server (Phase 33 recorded the live 503 on the RC image — history). JazzCash: not implemented, not configured, not invented.

## 12. Backup status

- `scripts/backup_database.sh` + `scripts/restore_database.sh` verified present and intact at `51e4a9a`; defaults (`uniserve_postgres`, `uniserve_prod`, `uniserve`) match `docker-compose.prod.yml`; `CONFIRM=yes` restore gate and `pg_restore --list` verification built in; 30-day prune built in.
- **Nothing to back up** (no production DB). Server-side actions pending: `backups/` dir, cron `0 2 * * *`, off-machine copies, and the mandatory **first backup immediately after initial seeding**.

## 13. Validation results (this phase — minimum necessary, local)

| Check | Result |
|---|---|
| Baseline | HEAD `51e4a9a`, `git status --short` empty (start + after build) |
| Prod Compose config | `docker compose -f docker-compose.prod.yml config --quiet` → **OK** |
| Release image build | **OK** — `uniserve-prod-api:latest`, 836 MB, built at `51e4a9a` |
| Migration head (in repo) | `0000`–`0009` present, head `0009` |
| Dependency lock | `apps/api/requirements.lock.txt` present; root `package-lock.json` committed (Phase 32) |
| Git hygiene | `.env.production`, `.venv`, `node_modules`, `backups` ignored; no secret files tracked |
| Container inventory | Local rehearsal stack only (`uniserve_api/postgres/caddy` on Docker Desktop) — **no production stack** |
| Backend suite | Not rerun — **no application code changes** (docs-only phases since 649-green run) |
| Secrets exposure | None — no secret values printed in output, evidence, or this report |

## 14. Failures / blockers

**No new application or repository failures.** Deployment remains blocked exactly on the external inputs of `DEPLOYMENT_BLOCKERS.md` B1–B9 (B10/JazzCash optional by design):

| Blocker | Blocks Phase 40 items |
|---|---|
| B1 VPS + B2 SSH (owner supplies) | items 1–3, 6–17 — everything |
| B3/B4 domains + DNS + Caddyfile real values | items 7, 9–10, 14 (HTTPS/web) |
| B7 server `.env.production` (secrets + real CORS) | items 6, 11–13 |
| B9 transfer path (rsync/scp — no pushed remote; push forbidden) | item 5 |
| SMTP account (optional for cash-only launch) | OTP email delivery only |

Phase 40 item status: **8/9/13 partially validated locally** (compose config OK, image build OK, hygiene OK); **all server-execution items (1–7, 10–12, 14–18) blocked on owner inputs**.

## 15. Exact next external action

The owner supplies the four answers requested this phase: **(1)** server IP/hostname · **(2)** SSH method (prefer: authorize local `id_ed25519.pub`; otherwise password typed directly into the terminal) · **(3)** `api.<domain>` + `app.<domain>` with DNS A-record state · **(4)** secrets handling (generate on server per runbook, or owner-supplied values). Then execution proceeds in order: `scripts/vps/run-all.sh` → rsync tree to `/opt/uniserve` @ `51e4a9a` → server `.env.production` (chmod 600) → Caddyfile two-line domain edit (only once DNS confirmed) → `npm ci --ignore-scripts` (repo root) → web build with real `NEXT_PUBLIC_API_URL` → `compose build api` → `up postgres` → healthy → `alembic upgrade head` (backup-first rule if DB ever non-fresh) → `up -d` → `restart caddy` → health/readiness → auth/RBAC/payments-503/backup checks → evidence capture — i.e., `DEPLOYMENT_RUNBOOK.md` Steps 1–20 / `PRODUCTION_DEPLOYMENT_CHECKLIST.md` end-to-end.

---

**Constraints honored:** no deployment · no server connection · no invented IPs/credentials/domains · no secrets printed · no JazzCash implementation or invention · no SMTP faking · no destructive DB operations · no dependency/UI changes · no product/security audit · no push · previous phases not restarted. Mobile/EAS and JazzCash remain out of scope for this phase.
