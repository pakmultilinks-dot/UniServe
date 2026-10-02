# UniServe — Production Deployment Checklist

> **The one checklist to follow when real infrastructure becomes available.**
> Concise and executable; links to the detailed runbooks instead of
> duplicating them. Source of truth: this repository at the commit recorded
> in `PHASE_31_PRODUCTION_DEPLOYMENT_PREREQUISITE_FINALIZATION.md`.
>
> **UniServe is NOT deployed by this document.** No step below has been
> executed against a real server, domain, or payment provider.
>
> **Legend:** `[REPO]` repository-ready · `[OP]` operator-provided ·
> `[EXT]` external service · `[JC]` JazzCash-blocked (do not attempt)

Detailed procedures: `DEPLOYMENT_RUNBOOK.md` (first deployment, 20 steps) ·
`PRODUCTION_RUNBOOK.md` (operations, migrations, backup/restore, monitoring) ·
`DATABASE_OPERATIONS.md` (DB procedures) ·
`UPDATE_ROLLBACK_PROCEDURE.md` (updates & rollback) ·
`DEPLOYMENT_ARCHITECTURE.md` (topology) · `docs/` (architecture).

---

## 0. Before deployment

- [ ] `[REPO]` You are on `main` with a clean tree at the expected commit
      (`git status --porcelain` empty; `git log --oneline -1`).
- [ ] `[REPO]` Read `PRODUCTION_RUNBOOK.md` §1–§3 and this checklist once
      end-to-end before touching the server.
- [ ] `[OP]` Provisioned: VPS (Ubuntu 22.04+/Debian 12+, 2+ CPU, 4 GB RAM),
      two subdomains (e.g. `api.<domain>`, `app.<domain>`), DNS A records
      pointing both at the server IP.
- [ ] `[OP]` Stop any dev compose stack on the server — prod and dev share
      container names (`uniserve_postgres` etc.).
- [ ] `[REPO]` Dependency note (Phase 32): the root `package-lock.json` is
      committed — install from the **repo root** with `npm ci --ignore-scripts`
      (never `npm install`; plain `npm ci` fails on react-native-screens'
      install script, which needs dev-only tooling — no web-build package
      needs install scripts).

## 1. Server setup `[OP]`

Follow `DEPLOYMENT_RUNBOOK.md` Steps 1–2:

- [ ] System updated; Docker Engine + Compose v2 installed
      (`curl -fsSL https://get.docker.com | sh`).
- [ ] `systemctl enable docker` (restart policies + boot survival).
- [ ] Repo cloned to `/opt/uniserve`, on `main`.

## 2. Secret setup `[OP]`

- [ ] `cp .env.production.example .env.production`
- [ ] Generate and set (never reuse dev values, never commit the file):

  ```bash
  APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
  JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
  POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  ```

- [ ] Set `APP_ENV=production`, `APP_DEBUG=false`, `POSTGRES_DB=uniserve_prod`,
      `CORS_ORIGINS=["https://app.<domain>"]`, `LOG_LEVEL=INFO`.
- [ ] `chmod 600 .env.production`
- [ ] Understand the **fail-closed startup guards** (the API refuses to boot
      on any of these — this is by design):
  - default `APP_SECRET_KEY` / `JWT_SECRET_KEY` values
  - **empty or whitespace-only secret keys**
  - `APP_DEBUG=true` with `APP_ENV=production`
  - `POSTGRES_PASSWORD` empty, the dev default, or **shorter than 12 chars**
- [ ] `[EXT]` (Optional, future) SMTP — not implemented; notifications are
      in-app only. `[JC]` Payments — leave `PAYMENT_PROVIDER` unset/commented;
      online payments stay fail-closed (HTTP 503) until JazzCash is
      provisioned externally.

## 3. Domain / DNS setup `[OP]` `[EXT]`

- [ ] DNS A records: `api.<domain>` and `app.<domain>` → server IP; wait for
      propagation (`dig +short api.<domain>`).
- [ ] Edit `infrastructure/caddy/Caddyfile` — replace **exactly two lines**:
  - `api.example.com {` → `api.<domain> {`
  - `app.example.com {` → `app.<domain> {`
- [ ] Everything else in the Caddyfile stays as-is: Caddy obtains and renews
      **Let's Encrypt certificates automatically** (keep ports 80/443 open),
      adds security headers, proxies `/api/...` to `uniserve_api:8000`, and
      serves the static web export. Do not hand-edit TLS config.

## 4. Build `[OP]` `[REPO]`

- [ ] API image: `docker compose -f docker-compose.prod.yml build api`
- [ ] Web env: `cp apps/web/.env.production.example apps/web/.env.production.local`
      and set `NEXT_PUBLIC_API_URL=https://api.<domain>/api/v1`
      (**build-time** — baked into the bundle; wrong value = web app calls
      the wrong host; the committed repo contains no web artifact —
      `apps/web/out` is gitignored and must be built here).
- [ ] Web build: `( cd apps/web && npm run build )` — with `npm ci
      --ignore-scripts` already run from the repo root (see section 0).
- [ ] Confirm: `ls apps/web/out/index.html`

## 5. Database migration `[REPO]`

```bash
mkdir -p backups
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml ps                    # wait: postgres healthy
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm api alembic current
# Expected: 0009 (head)
```

- [ ] Migrations run **manually, never on startup**; take a backup before
      every migration on an existing database (§8).
- [ ] Do **not** run `alembic downgrade` in production (forward-fix first —
      §9).

## 6. Startup `[REPO]`

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps    # api+postgres "healthy", caddy "Up"
docker compose -f docker-compose.prod.yml restart caddy   # pick up web export
```

## 7. Verification — post-deployment smoke test

Run in order (details: `PRODUCTION_RUNBOOK.md` §11; first-time business
verification: `DEPLOYMENT_RUNBOOK.md` Steps 11–16):

1. [ ] DNS resolves to the server (`dig +short` both names).
2. [ ] HTTPS works — `curl -sI https://api.<domain>/api/v1/health` → 200;
      certificate issued by Let's Encrypt (Caddy logs).
3. [ ] Caddy running (`docker compose -f docker-compose.prod.yml ps`).
4. [ ] API container healthy; PostgreSQL container healthy.
5. [ ] Migrations at expected head (`alembic current` → `0009 (head)`).
6. [ ] Readiness succeeds — `curl -fsS https://api.<domain>/api/v1/health/ready`
      → `"status":"ready"`, `"schema":"present"`.
7. [ ] Web loads — `curl -fsS https://app.<domain>/` returns the app HTML.
8. [ ] Create first admin (`DEPLOYMENT_RUNBOOK.md` Step 11 — register + promote
      to `university_admin` via SQL).
9. [ ] Login works (admin via web; student/faculty via mobile or web where
      permitted).
10. [ ] Role separation works (student/faculty cannot reach the admin
       dashboard; 403s as expected).
11. [ ] Cafeteria isolation works (manager sees only assigned cafeteria).
12. [ ] Menu loads (publish a daily menu first — Step 13).
13. [ ] Immediate cash order works end-to-end.
14. [ ] Scheduled order works.
15. [ ] Staff view receives the order; confirm → ready → pickup lifecycle
       works.
16. [ ] Cancellation rules work (refund deadline enforced).
17. [ ] Notifications appear in-app where implemented.
18. [ ] Logs contain no secrets —
       `docker compose -f docker-compose.prod.yml logs api 2>&1 | grep -Eic "password|secret|token|bearer"` → 0.
19. [ ] Backup job exists (§8 cron installed) and produced a dump.
20. [ ] Restore procedure documented and understood (§8–§10).
21. [ ] Online payments remain **fail-closed**: initiating an online payment
       returns HTTP 503 ("no production payment provider is configured").
       A 2xx means the guard was weakened — stop and fix. `[JC]`
22. [ ] DB/API not reachable from the internet except via Caddy —
       `docker port uniserve_postgres` and `docker port uniserve_api`
       print nothing.

> Seeded-test-account E2E (`scripts/phase19_e2e_test.py`) targets
> staging/dev, **not** production. Against a production-guarded deploy the
> payment check fails with 503 by design (30/31 = expected).

## 8. Backup setup `[OP]` — **not automatic until you install the job**

**Backup (operator sequence):**

```bash
cd /opt/uniserve
./scripts/backup_database.sh /opt/uniserve/backups
# cron — daily 02:00 (install via `crontab -e`):
0 2 * * * cd /opt/uniserve && ./scripts/backup_database.sh /opt/uniserve/backups
```

- [ ] Script verified each dump (`pg_restore --list`) and prunes >30 days.
- [ ] Dumps copied **off the machine** (object storage / another host) —
      a backup that only lives on the DB server does not survive the server.

## 9. Rollback (pick the category — they are different things)

| Problem | Procedure |
|---|---|
| Application (code) rollback | `git checkout <last-good>` → rebuild api image → `up -d api` |
| Static web rollback | `git checkout <last-good>` → `npm ci --ignore-scripts` (repo root) → `npm run build` → `restart caddy` |
| Database migration issue | **Forward-fix first** (new corrective migration). `alembic downgrade` only with a verified backup + stopped API, understanding the data loss. |
| Database corruption/loss | Verified backup → controlled restore (§10) |
| Environment/config error | Restore previous `.env.production` (keep `.bak-<ts>` copies) → restart api |

- [ ] Read `UPDATE_ROLLBACK_PROCEDURE.md` before performing any rollback.

## 10. Emergency recovery `[OP]`

**Restore verification** (after any restore):

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic current   # -> 0009 (head)
docker compose -f docker-compose.prod.yml up -d api
curl -fsS https://api.<domain>/api/v1/health/ready                        # -> ready / schema present
```

**Full restore (disaster):**

```bash
./scripts/backup_database.sh /opt/uniserve/backups        # snapshot current state (forensics)
docker compose -f docker-compose.prod.yml stop api         # writes must not race
CONFIRM=yes ./scripts/restore_database.sh backups/uniserve_<ts>.pgdump
# then: alembic current -> 0009, up -d api, readiness -> ready (commands above)
```

- [ ] The restore script **refuses without `CONFIRM=yes`** and verifies the
      dump inside the container before touching the database.
- [ ] Keep a recent backup **before every migration** — that is what makes
      both rollback paths possible.

## 11. Known blockers & external requirements

| Dependency | `[REPO]` ready? | Operator action | External dependency | Verified? |
|---|---|---|---|---|
| VPS | provisioning scripts in `scripts/vps/` | Purchase + run provisioning | Hosting provider | **No** |
| Domain | Caddyfile placeholders | Buy + point DNS | Registrar | **No** |
| DNS | runbook Step 4 | Create A records | DNS provider | **No** |
| TLS | Caddy automatic HTTPS | Keep 80/443 open; replace placeholders | Let's Encrypt | **No** (requires real domains) |
| Production secrets | mechanism + guards ready | Generate on server (§2) | — | **No** (none created) |
| Expo/EAS build | config ready (`eas.json`, channel map) | Edit `apps/mobile/src/config.ts` prod URL; EAS account; build | Expo | **No** |
| SMTP | not implemented | Decide later | Email provider | **No** |
| Online payments (JazzCash) | fail-closed guard only | Official API contract + credentials | JazzCash | **No — blocked externally** `[JC]` |
| Backups | scripts ready | Install cron + off-machine copy (§8) | Storage | **No** |
| Monitoring | not configured | Uptime checks + log alerts | Monitoring provider | **No** |

Additional known limitations: Python runtime dependencies are pinned to the
exact tested versions via `apps/api/requirements.lock.txt` (installed with
`--no-deps` + `pip check` in the API image) and JS dependencies via the
committed root `package-lock.json` (`npm ci --ignore-scripts`). Remaining
gaps are documented in `PHASE_32_DEPENDENCY_REPRODUCIBILITY.md` (base-image
tooling, dev/test dependencies, and no byte-for-byte image claim).

**JazzCash restriction:** do not implement, invent, or weaken anything
around online payments. The production 503 fail-closed guard is intentional
and must remain until a real provider is officially provisioned and audited.
