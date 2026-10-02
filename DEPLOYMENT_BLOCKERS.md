# UniServe — Deployment Blockers

**Date:** 2026-10-02 (Phase 34)
**Repository state:** `main` @ `70ae399`, working tree clean, release candidate fully validated locally (see `PHASE_33_PRODUCTION_RELEASE_CANDIDATE_SIMULATION.md`, `EVIDENCE_PRODUCTION_DEPLOYMENT.md`).

**No real production deployment has occurred.** The repository is deployment-ready; execution is blocked exclusively on external operator-owned prerequisites. This file lists each missing prerequisite, why it is required, the exact operator action, the exact expected configuration, and the verification command to run once it is provided. Nothing here can be fabricated by the project — do not substitute placeholders for real values when executing.

---

## Summary

| # | Missing prerequisite | Required for | Severity |
|---|---|---|---|
| B1 | Production server (VPS) | everything | blocking |
| B2 | SSH access to that server | server preparation, deploy | blocking |
| B3 | Production domains + DNS A records | HTTPS, web/API URLs | blocking |
| B4 | Real domains in `infrastructure/caddy/Caddyfile` | HTTPS routing | blocking |
| B5 | Server-side web build with real `NEXT_PUBLIC_API_URL` | web artifact | blocking |
| B6 | Mobile production API URL + Expo EAS credentials | mobile production build | blocking (mobile only) |
| B7 | Provisioned server-side `.env.production` | API/database startup | blocking |
| B8 | Real `CORS_ORIGINS` value | browser web app access | blocking |
| B9 | Git hosting reachable from the server (or file transfer) | code delivery | blocking |
| B10 | Payment provider contract (e.g., JazzCash) | online payments only | **optional** — system is fail-closed without it; cash ordering works |

---

## B1 — Production server (VPS)

1. **Missing:** No VPS exists. `VPS_PROVISIONING_REPORT.md` (Phase 18) records `BLOCKED — VPS NOT READY`: no cloud provider account, no server IP. Phase 34 re-verified: `docker context ls` shows only local Docker Desktop contexts; no remote Docker host is configured.
2. **Why required:** The entire deployment (Caddy, API, PostgreSQL, static web) runs on a Linux server with Docker.
3. **Operator action:** Provision a VPS per the documented requirements, then run the prepared toolkit: `scripts/vps/run-all.sh` (verify → update → Docker → deploy user → SSH hardening → firewall → `/opt/uniserve`).
4. **Expected:** Ubuntu 22.04+ / Debian 12+, 2+ CPU, 4 GB+ RAM, 40 GB+ SSD; Docker Engine + Compose plugin; public ports only 22/80/443.
5. **Verification:**
   ```bash
   ssh root@<server-ip> "docker compose version && df -h / && free -m"
   ```

## B2 — SSH access

1. **Missing:** No server IP and no SSH credentials are available in this environment.
2. **Why required:** All deployment steps execute on the server over SSH.
3. **Operator action:** Provide SSH access (key-based; see `scripts/vps/05-harden-ssh.sh` for the safe hardening path).
4. **Expected:** `root` or sudo-capable user on the target server.
5. **Verification:** `ssh root@<server-ip> 'whoami && docker ps'`

## B3 — Production domains + DNS

1. **Missing:** No production domains are configured. Repository artifacts still use placeholders (`api.example.com`, `app.example.com`, `api.uniserve.app`).
2. **Why required:** Caddy obtains HTTPS certificates and the web/mobile clients call the API at its public domain.
3. **Operator action:** Register two subdomains (e.g., `api.<your-domain>`, `app.<your-domain>`) and create DNS records:
   | Type | Name | Value |
   |---|---|---|
   | A | api | `<server-ip>` |
   | A | app | `<server-ip>` |
4. **Expected:** Both A records resolving to the server IP.
5. **Verification:** `dig +short api.<your-domain>` and `dig +short app.<your-domain>` both return `<server-ip>`.

## B4 — Real domains in the production Caddyfile

1. **Missing:** `infrastructure/caddy/Caddyfile` ships with `api.example.com` / `app.example.com` vhosts (placeholders by design; replacing them is an operator step, per its header comment).
2. **Why required:** Caddy will not route or issue certificates for domains that do not match the vhost addresses.
3. **Operator action:** Edit the two vhost addresses to the real domains. **Do not touch the `try_files` line** — `try_files {path} {path}.html {path}/index.html /index.html` is the Phase 33 deep-link fix and must remain exactly as committed.
4. **Expected:** `api.<your-domain>` and `app.<your-domain>` vhosts; unchanged proxy target `uniserve_api:8000`; unchanged try_files line.
5. **Verification:**
   ```bash
   grep -n 'try_files\|^[a-z].*{$' infrastructure/caddy/Caddyfile
   curl -sI https://<app-domain>/login        # 200, route-specific body
   curl -sI https://<api-domain>/api/v1/health # 200 {"status":"healthy"...}
   ```

## B5 — Server-side web build with real API URL

1. **Missing:** The deployable web artifact must be built **on the server** with the real API URL; no real API URL exists yet (B3). `NEXT_PUBLIC_API_URL` is baked at build time (`apps/web/src/lib/api.ts:95`).
2. **Why required:** A build without it embeds the dev fallback `http://localhost:8000/api/v1`.
3. **Operator action:** Per runbook Step 6/7, after DNS + Caddyfile are set:
   ```bash
   cp apps/web/.env.production.example apps/web/.env.production.local
   # set NEXT_PUBLIC_API_URL=https://api.<your-domain>/api/v1
   npm ci --ignore-scripts
   ( cd apps/web && NEXT_PUBLIC_API_URL=https://api.<your-domain>/api/v1 npm run build )
   ```
4. **Expected:** `apps/web/out/` contains 22 HTML + 21 RSC files; zero occurrences of `localhost:8000`, `127.0.0.1`, `api.example.com`, `app.example.com`.
5. **Verification:**
   ```bash
   grep -rl 'localhost:8000\|127\.0\.0\.1\|api\.example\.com\|app\.example\.com' apps/web/out --include='*.html' --include='*.js' --include='*.css' --include='*.txt' | wc -l   # 0
   ```

## B6 — Mobile production API URL + EAS credentials

1. **Missing:** `apps/mobile/src/config.ts` still carries the committed placeholder `https://api.uniserve.app/api/v1`; no Expo account/EAS credentials exist.
2. **Why required:** Production mobile builds must target the real API; EAS builds need an external Expo account.
3. **Operator action:** Set `ENV.production.API_BASE_URL` to `https://api.<your-domain>/api/v1`; then, with an Expo account, run `eas build --platform all --profile production` from `apps/mobile/`.
4. **Expected:** No localhost/simulation URL in the production config; an EAS build artifact only if actually produced.
5. **Verification:**
   ```bash
   grep -n 'API_BASE_URL' apps/mobile/src/config.ts   # real domain, no localhost
   # EAS dashboard shows a build only if one was actually submitted/built
   ```

## B7 — Provisioned server-side `.env.production`

1. **Missing:** No server exists to hold it (B1). Locally, `.env.production` exists (gitignored, generated during deployment-preparation phases) with strong random values, but it has not been provisioned to any server and its values should be reviewed/rotated by the operator before first use.
2. **Why required:** The API and PostgreSQL refuse to start meaningfully without production secrets; empty/denylisted secrets fail closed at boot (verified live in Phase 33).
3. **Operator action:** Review the local `.env.production` (or regenerate per runbook Step 3: `secrets.token_urlsafe(64)` for app/JWT keys, `token_urlsafe(32)` for the DB password), then transfer it to the server over a secure channel (e.g., `scp`) to `/opt/uniserve/.env.production`. Never commit it; never reuse dev/simulation values.
4. **Expected:** `APP_ENV=production`, `APP_DEBUG=false`, 64-byte-class random `APP_SECRET_KEY`/`JWT_SECRET_KEY`, strong `POSTGRES_PASSWORD`, real `CORS_ORIGINS` (B8).
5. **Verification (on server):**
   ```bash
   grep -E '^(APP_ENV|APP_DEBUG|CORS_ORIGINS)=' /opt/uniserve/.env.production
   # APP_ENV=production / APP_DEBUG=false / CORS_ORIGINS=["https://app.<your-domain>"]
   wc -c <<< "$(grep '^APP_SECRET_KEY=' /opt/uniserve/.env.production | cut -d= -f2)"   # >= 65
   ```

## B8 — Real `CORS_ORIGINS`

1. **Missing:** `.env.production` currently has the placeholder `CORS_ORIGINS=["https://app.example.com"]`.
2. **Why required:** The browser web app is served from the real app domain; without the correct origin the API rejects cross-origin browser requests.
3. **Operator action:** Set `CORS_ORIGINS=["https://app.<your-domain>"]` (JSON array) in the server-side `.env.production`.
4. **Expected:** Exactly the real web origin(s).
5. **Verification:** `curl -s -D - -o /dev/null -H "Origin: https://app.<your-domain>" https://api.<your-domain>/api/v1/health | grep -i access-control-allow-origin` → echoes the origin.

## B9 — Git hosting reachable from the server

1. **Missing:** The runbook clones `https://github.com/your-org/UniServe.git` — no real repository URL has been provided.
2. **Why required:** The server obtains the codebase (and lockfiles, Caddyfile, scripts) from a git remote, or via explicit file transfer.
3. **Operator action:** Push `main` (currently `70ae399`) to the real remote, or transfer the tree (`scp -r` / rsync) and keep `.git` intact for rollbacks.
4. **Expected:** Server can check out `main` at the release commit.
5. **Verification:** `ssh <server> 'cd /opt/uniserve && git rev-parse --short HEAD'` → `70ae399` (or the superseding release commit).

## B10 — Payment provider contract (OPTIONAL)

1. **Missing:** No production payment provider (e.g., JazzCash) contract or credentials exist — by design.
2. **Why required:** Only for **online** payments. The system is deliberately fail-closed: `POST /api/v1/payments/initiate` returns HTTP 503 (`Online payments are unavailable: no production payment provider is configured`) and cash ordering is fully functional. Verified live in Phase 33 on the release-candidate image.
3. **Operator action:** Deploy without it (cash-only launch is supported). To enable online payments later: sign the provider contract, obtain real credentials, and wire the provider through the existing payment-gate configuration — never with guessed values.
4. **Expected until then:** initiate → 503; cash orders unaffected.
5. **Verification:**
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<api-domain>/api/v1/payments/initiate \
     -H 'Content-Type: application/json' -d '{"order_id": 1, "provider": "jazzcash", "idempotency_key": "probe"}'
   # 503 while unconfigured = correct fail-closed behavior
   ```

---

## What is already ready (no operator input needed)

- Release candidate `70ae399`: 622 backend tests pass, web/mobile type-checks pass, production image builds from `requirements.lock.txt` (44/44 pins verified), fresh-database migrations `0000 → 0009` verified, 48/48 end-to-end workflow checks passed, backup/restore and failure/recovery drills passed, Caddy deep-link defect fixed and committed.
- Deployment tooling: `scripts/vps/` provisioning toolkit, `docker-compose.prod.yml` (Caddy + API + PostgreSQL, expose-only, healthchecks, Redis correctly commented out), backup/restore scripts, this runbook.
- Local `.env.production` with strong generated secrets (operator review/rotation before server provisioning — B7).

Once B1–B9 are provided, execute `DEPLOYMENT_RUNBOOK.md` end-to-end; B10 may remain unconfigured indefinitely.
