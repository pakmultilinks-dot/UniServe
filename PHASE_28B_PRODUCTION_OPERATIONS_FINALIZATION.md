# Phase 28B — Production Operations Finalization

**Scope:** Final audit of operational procedures and deployment documentation
against the repository. This is **not** an application feature audit; no
feature, payment, deployment, DNS, or HTTPS work was performed.

**Commit type:** `fix: finalize production operations` (one genuine code fix in
`scripts/phase19_e2e_test.py` plus documentation corrections).

---

## 1. Baseline

| Item | Value |
|---|---|
| Starting commit | `3d36478` — "fix: harden release engineering readiness" (Phase 28A final) |
| Branch / tree | `main`, clean |
| Committed Phase 28A deliverables | `PRODUCTION_RUNBOOK.md`, `PHASE_28A_RELEASE_ENGINEERING_REHEARSAL.md`, `scripts/restore_database.sh`, production config guards, readiness schema probe, web landing fix, pinned compose project name |
| Docker state at start | Dev stack stopped (volume `uniserve_postgres_data` preserved); Phase 28A prod rehearsal stack/volume (`uniserve-prod_postgres_data`) intact |
| Constraints in force | Inspect-only on payment code; no JazzCash; no VPS/DNS/HTTPS changes; no test weakening; no full-suite rerun unless a change requires it |

## 2. Runbook audit result

`PRODUCTION_RUNBOOK.md` (Phase 28A, 11 sections) was checked line-by-line
against the repository: every command, path, service name, volume name, env
template reference, script default, health endpoint, and migration revision
cited in it.

**Result: the runbook contained 8 factual documentation errors and 3
operational gaps.** None of the errors were security-critical, but several
would have produced failed deployments (wrong env template, `npm ci` failure,
misleading healthcheck criteria) or misleading recovery decisions
(`alembic downgrade` framing, JWT expiry). The user's instruction — "Do not
assume documentation is correct merely because it was written during Phase
28A" — was warranted.

Audited facts that **were** correct and left unchanged: compose project name
`uniserve-prod`; container names; port topology (Caddy-only exposure);
`apps/api/Dockerfile` build; `env_file: .env.production`; manual migration
policy (no auto-migrate on startup); head revision `0009`; backup script
defaults (`uniserve`/`uniserve_prod`/`uniserve_postgres`); readiness
`schema: present/missing` semantics; payment 503 guard semantics.

## 3. Environment contract (verified)

| Source | Status |
|---|---|
| `.env.example` | **Development** template (`APP_ENV=development`, localhost:5432, `uniserve_dev`). Runbook now warns explicitly. The `DATABASE_URL=${...}` line is inert — pydantic-settings reads discrete `POSTGRES_*` fields, not that interpolation form. |
| `.env.production.example` | Production template: `APP_ENV=production`, `APP_DEBUG=false`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS=7`, `CORS_ORIGINS=["https://app.example.com"]`, `POSTGRES_DB=uniserve_prod`, `PAYMENT_*` all commented. Runbook now requires creating `.env.production` from **this** file. |
| `apps/web/.env.production.example` | Instructs copying to `apps/web/.env.production.local` (git-ignored). Runbook previously said `.env.production` — corrected; noted that Next.js loads both names and that `NEXT_PUBLIC_API_URL` is baked at build time. |
| `apps/api/app/core/config.py` | Only the documented variable families are read: `APP_*`, `POSTGRES_*`, `JWT_*` (access 30 min / refresh **30 days** code default), `OTP_*`, `PIN_*`, rate limits, business rules (`REFUND_DEADLINE_HOURS`, `PICKUP_WINDOW_MINUTES`, `DEFAULT_*`, `NOSHOW_*`), `UNIVERSITY_EMAIL_PATTERNS`, `CORS_ORIGINS` (localhost-only default), `LOG_*`, `PAYMENT_*`. |
| SMTP placeholders | **Aspirational only** — `.env.production.example` carries commented SMTP lines, but `Settings` has no SMTP fields; the app never reads them. Not misrepresented as working anywhere in the runbook. |
| Startup validation | Fail-closed (Phase 28A): `reject_default_secrets` + `reject_debug_in_production` crash the API on boot when misconfigured. Documented in prerequisites. |
| Mobile / web configs | No backend secrets; mobile endpoint map keyed by EAS channel (development/staging/production). |

**JWT discrepancy resolved:** runbook §9 previously claimed "30 min access /
30 days refresh". With the provided production template the refresh window is
**7 days**; 30 days is only the code default when the variable is unset. The
runbook now states both precisely, and §10 checklist pins the template values.

## 4. Migration procedure (verified)

- Migrations are manual by design — `docker compose -f
  docker-compose.prod.yml run --rm api alembic upgrade head`; no auto-migrate
  on startup. Head: `0009` (`alembic upgrade head` is idempotent).
- All 10 revisions (`0000`–`0009`) implement `downgrade()`, but **every
  implementation is a destructive schema reversal** — `drop_table`/`drop_column`
  on data-bearing structures (`users`, `cafeterias`, enums, `payments` tables,
  `checkout_idempotency_key`). Downgrade is a dev/empty-DB tool only.
- Runbook now includes failure guidance: fresh DB → fix and re-run; existing
  DB → restore the pre-migration backup; downgrade explicitly documented as
  **not** a production rollback. Backup-before-migrate rule unchanged.

## 5. Backup & restore (verified)

- `scripts/backup_database.sh`: `pg_dump` custom format inside the container →
  `docker cp` to `./backups/`; 30-day retention; defaults match the production
  template (`uniserve`/`uniserve_prod`/`uniserve_postgres`). Rehearsed in
  Phase 28A.
- `scripts/restore_database.sh` (Phase 28A): `pg_restore --clean
  --if-exists`; same defaults. Runbook now documents the `DB_USER`/`DB_NAME`
  env overrides for renamed databases (previously undocumented — a real
  operator trap).
- Success criteria documented: `alembic current` = head, readiness `"ready"` +
  `"schema": "present"`, spot-check restored rows via `psql` in-container.

## 6. Rollback (clarified)

The runbook previously conflated application rollback with database recovery.
Now explicit:

- **Application rollback:** `git checkout <last-good>` → rebuild api image or
  web export → restart/reload Caddy. Env: restore a timestamped
  `.env.production.bak-<ts>` copy, then restart.
- **Database recovery:** restore the most recent acceptable backup
  (§6 script). Bad migration on a live DB → restore the pre-migration backup.
- `alembic downgrade` is explicitly excluded from the production rollback
  path (destructive — §4).

## 7. Health & readiness (verified)

- `GET /api/v1/health` — liveness, no DB dependency (Phase 28A).
- `GET /api/v1/health/ready` — readiness with schema probe (`SELECT 1`, then
  `SELECT 1 FROM users LIMIT 1`); returns `"schema": "present"/"missing"`;
  `missing` → degraded → execute restore (§6). Phase 28A behavior unchanged.
- `scripts/production_health_check.py --api-url <url>` helper supports any
  deployed base URL; treats absent OpenAPI as expected in production.
- Container health wording corrected throughout: **api + postgres show
  `healthy`; caddy has no healthcheck in the compose file — `Up/running` is
  its success state.** The previous "all three healthy" phrasing was
  unachievable as written.

## 8. Security checklist (now actionable)

Security posture in §10 was prose ("no new architecture"); it is now a
14-item pre-live checklist grounded in verified facts: generated secrets;
`APP_ENV=production`/`APP_DEBUG=false`; real-origin `CORS_ORIGINS`; INFO/JSON
logs; DB/API port exposure checks; Caddy-only reachability; HTTPS
prerequisites (real domains + DNS + ACME ports); session config review;
log secret-scan (rehearsal baseline: **0 matches**); off-machine backups;
`chmod 600 .env.production`; payments fail-closed (503); no secrets in web
export or mobile builds. The verified-posture summary below it is retained.

## 9. Deployment verification (new §11)

Added a 12-step post-deployment verification sequence, each step backed by an
existing tool — **no step ever creates fake payment success**:

1–2. `docker compose ... ps` — api/postgres healthy, caddy Up.
3. `alembic current` → `0009`.
4. `/api/v1/health` + `/api/v1/health/ready` (or `production_health_check.py`).
5. `curl https://<app-domain>/` → static HTML.
6–10. Login, role separation, cafeteria isolation, menu, order lifecycle —
      via `scripts/phase19_e2e_test.py` (31 checks; run against a seeded
      staging/dev environment, **not** production, because it uses fixture
      accounts and writes test data). Against a payment-guarded deployment the
      expected result is **30/31** — the "Online payment initiated" check
      failing with HTTP 503 **is** the fail-closed verification, not a
      regression.
11. Log secret scan (`grep -Eic "password|secret|token|bearer"` → 0 matches
      rehearsal baseline).
12. Payment fail-closed confirmation: authenticated initiate must return 503;
      a 2xx means the guard was weakened — stop and fix.

## 10. Failure playbook (expanded §9)

Previously covered: health degraded, migration failure, HTTP 401/403, HTTP
503, backup restore. Added three rows grounded in repo facts:

- **Web pages error/blank** → stale/missing static export: rebuild
  `apps/web/out`, restart caddy, confirm `index.html` exists.
- **Caddy 502/504 for API calls** → upstream unreachable: `ps` (api healthy?),
  `logs --tail 100 caddy api`, restart api.
- **Login fails for everyone** → auth/DB issue or `JWT_SECRET_KEY` rotation
  (a change invalidates all sessions — users must re-login).

The 503-payment row now states explicitly that 503 is **expected fail-closed
behavior**, not an outage.

## 11. Issues discovered

| # | Type | Issue | Severity |
|---|---|---|---|
| 1 | Doc | Architecture table said volume `postgres_data`; actual Docker volume is `uniserve-prod_postgres_data` (`<project>_<key>`) | Low — operator confusion |
| 2 | Doc | Runbook implied `.env.example` was usable for production; it is the **development** template | High — wrong-config deployment |
| 3 | Doc | Web env file named `.env.production`; template instructs `.env.production.local` | Medium — build-time endpoint mismatch |
| 4 | Doc | `npm ci` in deploy steps — no `package-lock.json` committed in `apps/web`/`apps/mobile`; `npm ci` fails | High — deploy step failure |
| 5 | Doc | No migration-failure guidance; `alembic downgrade` not contextualized (all downgrades destructive) | Medium — dangerous recovery instinct |
| 6 | Doc | `restore_database.sh` `DB_USER`/`DB_NAME` overrides undocumented | Low — renamed-DB trap |
| 7 | Doc | "All three services healthy" — caddy has no healthcheck; criterion unachievable | Medium — false-deploy-blocker |
| 8 | Doc | "30 min access / 30 days refresh" — template sets 7 days; 30 days is the unset code default | Low — misleading session policy |
| 9 | Gap | No post-deployment verification section in the runbook | Medium — no standard deploy gate |
| 10 | Gap | Failure playbook thin (no web/Caddy-upstream/auth rows); rollback conflated app vs DB recovery | Medium |
| 11 | Code | `scripts/phase19_e2e_test.py` `BASE` hardcoded to `http://localhost:8000/api/v1` — no way to point the E2E suite at a deployed API for post-deploy verification | Medium — blocks §9 step 6–10 on staging |

## 12. Fixes applied

**Documentation — `PRODUCTION_RUNBOOK.md` (all corrections traceable to the
repo):**

1. Volume naming clarified (compose key vs actual Docker volume) in §1 table
   and key properties.
2. `.env.example` marked as the development template; production creation
   command now sources `.env.production.example`.
3. Web env file corrected to `apps/web/.env.production.local` with Next.js
   load semantics + build-time bake note + `DEPLOYMENT_RUNBOOK.md`
   cross-reference.
4. `npm ci` → `npm install` with a note to commit a lockfile for
   reproducibility (deploy step now works — no lockfile is committed).
5. Migration-failure subsection added (fresh DB / existing DB / downgrade
   destructive) in §4.
6. Restore-script override documentation added in §6.
7. Caddy health wording corrected in §1, §3 step 4, §7 (Up/running, not
   healthy; no healthcheck defined).
8. Token expiry corrected in §9 (7-day template value; 30-day code default
   when unset) + checklist item in §10.
9. Rollback section rewritten: application rollback vs database recovery vs
   destructive downgrade; `.env.production.bak-<ts>` env-copy pattern.
10. §10 security posture converted to a 14-item actionable pre-live
    checklist.
11. New §11: 12-step post-deployment verification sequence (containers →
    migrations → health → web → E2E flows → log scan → payment fail-closed),
    including the 30/31 production expectation for the E2E suite.
12. §9 playbook: web-error, Caddy→API-unreachable, and login-failure rows;
    503-payment row marked expected-fail-closed.

**Code — `scripts/phase19_e2e_test.py` (minimal, one behavior change):**

```python
BASE = os.environ.get("UNISERVE_E2E_BASE_URL", "http://localhost:8000/api/v1")
```

(+ `import os`). Default behavior is byte-identical to before; setting
`UNISERVE_E2E_BASE_URL` retargets every request. This makes the new §11
verification steps executable against any deployed environment. No test
logic, expectation, or threshold was touched — **no test weakening**.

## 13. Validation

| Check | Result |
|---|---|
| Default `BASE` (env unset) | `http://localhost:8000/api/v1` — unchanged ✓ |
| `UNISERVE_E2E_BASE_URL=https://api.example.com/api/v1` | Respected — every request retargets ✓ |
| Script diff | Exactly 2 lines (`import os` + BASE expression); request logic untouched ✓ |
| `git diff --check` | Clean (one trailing-whitespace caught and fixed) ✓ |
| Runbook structure | 12 sections; all internal cross-references consistent ✓ |
| Backend suite (608 tests) | **Not rerun** — per phase guidance (docs-only + one-line script change with no request-logic impact). Phase 28A baseline remains valid. |
| E2E 31/31 | **Not rerun** — the change only affects where `BASE` points; import-level verification proves both resolution paths, and no assertion changed. |
| Production readiness claim | **Not made** — JazzCash externally blocked (§15) |

## 14. Remaining limitations

- **No `package-lock.json`** committed for web/mobile — `npm install` (not
  `npm ci`) is required; builds are not bit-reproducible until a lockfile is
  committed (tracked as an operational follow-up, not a phase).
- **Caddy has no healthcheck** in `docker-compose.prod.yml` — its success
  state is `Up/running`; a compose-level healthcheck for Caddy remains an
  optional hardening item.
- **E2E suite against production is not recommended** — fixture accounts and
  test-data writes; the runbook directs it at seeded staging/dev and
  documents 30/31 as the fail-closed expectation on payment-guarded
  deployments.
- **SMTP placeholders are aspirational** — no SMTP fields exist in `Settings`;
  email delivery is not configured anywhere in the repo.
- **Local HTTPS rehearsal used placeholder domains** (`api.example.com`,
  `app.example.com`) — real deployment requires DNS records + real domains per
  `DEPLOYMENT_RUNBOOK.md`; this phase performed no VPS/DNS/HTTPS work.
- **JazzCash unresolved** — production online payments remain fail-closed
  (HTTP 503) by design. Full production readiness is **not** claimed.

## 15. JazzCash status — BLOCKED EXTERNALLY

JazzCash integration was **explicitly out of scope** for this phase and
remains blocked on external access (merchant credentials/onboarding response
from the external party). Nothing about the payment path changed in Phase 28B:
the test-only provider is still rejected in production with HTTP 503
(`guard_triggers_503 = True`, verified live in Phase 28A), no credentials
exist in the repository or in `.env.production.example`, and no payment
signing/webhook assumptions were modified. The failure playbook and the new
verification sequence both treat the 503 as the correct, expected state.
**Do not weaken the production payment guard, and do not implement JazzCash
without an external-access response and a dedicated, audited phase.**

## 16. Exact next phase

**Phase 28C — JazzCash online payment provider integration**, gated on
receipt of external access (merchant credentials + confirmed signing/webhook
contract). Scope would be: provider implementation behind the existing
production guard, credential validation, signing + webhook verification,
refund flow, dedicated tests, and a live fail-closed → fail-open transition
audit. **Do not start it until the user confirms external access.**

Per user instruction: **STOP after Phase 28B. Do not implement JazzCash.**

---

*Phase 28B complete. Operations documentation corrected (12 corrections), one
minimal code fix (E2E base-URL override), no application behavior changed,
payment guard untouched, production readiness not claimed.*
