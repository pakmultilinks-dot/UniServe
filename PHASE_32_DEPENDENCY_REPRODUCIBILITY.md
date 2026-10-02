# Phase 32 — Dependency Reproducibility & Release Locking

**Date:** Phase 32 (follows Phase 31, commit `561e67c`)
**Branch:** `main` · **Baseline commit:** `561e67c` · Working tree clean at start.
**Scope:** Reproducible production builds via deterministic dependency
resolution. No package upgrades, no package-manager migration, no application
refactoring, no deployment, no external services.

---

## 1. Baseline

| Item | Value |
|---|---|
| Baseline commit | `561e67c` (`fix: finalize deployment prerequisites`) |
| Working tree at start | clean |
| Python (host venv) | 3.13.7 (`.\.venv`) |
| Node / npm | v24.14.0 / 11.9.0 |
| Docker | 29.8.0 (rehearsal stack `uniserve-prod-*` left untouched) |
| Phase-31 validation baseline | 622 pytest passed · web type-check+build green (24 routes) · mobile type-check clean · alembic head `0009` no drift |

## 2. Current dependency architecture

- **API (Python):** `apps/api/pyproject.toml` declares `[project.dependencies]`
  with `>=` lower bounds (FastAPI, SQLAlchemy async, Alembic, python-jose,
  pydantic-settings, python-dotenv, cryptography, ...). Historically installed
  in Docker via `pip install .` — **resolver ran at every build** with no
  lockfile, so the image tracked whatever newest versions satisfied the bounds.
- **Web + Mobile + shared-types:** npm-workspaces monorepo. Root
  `package.json` (`workspaces: ["apps/web","apps/mobile","packages/shared-types"]`)
  with a **git-tracked root `package-lock.json`** (775,801 bytes, lockfileVersion 3)
  covering all three workspaces. No per-app lockfiles (correct for workspaces).
  `packages/shared-types/dist/` is gitignored → `npm run build:shared` precedes type-checks.
- **Mobile:** Expo SDK 51 (`~51.0.0` range), EAS config present but untouched.

## 3. Findings

1. **Python image had silently drifted from the tested venv.** Pre-Phase-32
   `pip install .` resolution produced: fastapi **0.142.2** (venv: 0.141.1),
   SQLAlchemy **2.1.2** (venv: 2.0.54), starlette **1.7.0** (venv: 1.6.0),
   uvicorn **0.54.0** (venv: 0.53.0), cryptography **50.0.2** (venv: 50.0.1),
   python-dotenv **1.2.4** (venv: 1.2.3), Mako **1.4.3** (venv: 1.4.1).
   Production therefore ran versions **no test had validated**.
2. **No Python lockfile existed.** `pip install .` re-resolved on every build;
   builds were time-dependent, not reproducible.
3. **Plain `npm ci` fails** in this repo: `react-native-screens@3.31.0` has
   `hasInstallScript: true` — its `prepare` script runs `bob build && husky install`,
   but `bob`/`husky` are its devDependencies and are never installed for
   dependency trees. 3 packages in the lockfile carry install scripts; none of
   them are in the web build chain.
4. **No git/URL/`file:` dependencies** in `package-lock.json` (audit clean).
   All version ranges (`^14.2.0` next, `~51.0.0` expo, `"*"` workspace refs)
   are intentional semver ranges — correctly locked by the committed lockfile.
5. **`packaging==26.3` appeared unpinned** in a first-pass image: it is
   required only by `wheel` (base-image tooling), not by any runtime
   dependency — proven via a metadata audit script scanning the image's
   installed distributions.
6. **Dead import masked by the dev venv:** `tests/test_auth_session_reliability.py`
   had an unused `import jwt` (PyJWT — undeclared in `pyproject.toml`). It
   passed on the host only because PyJWT happened to be installed in the dev
   venv; it broke test collection in any clean environment.

## 4. Changes made

| File | Change |
|---|---|
| `apps/api/requirements.lock.txt` | **NEW** — 44 exact pins: the full transitive closure of `[project.dependencies]` at the known-good tested-venv versions, with Linux-only packages (uvloop) sourced from the production image freeze (`--image-freeze`). Header documents regeneration + validation. |
| `apps/api/scripts/generate_requirements_lock.py` | **NEW** — deterministic lock generator: reads `[project.dependencies]` via `tomllib`, BFS transitive closure from installed distributions, marker environment overridden to the Linux/py3.11 production target, optional `--image-freeze` for non-host-installable packages. |
| `apps/api/Dockerfile` | Dependency layer now installs from the lock: `pip install --no-cache-dir --no-deps -r requirements.lock.txt && pip check && pip install --no-cache-dir --no-deps . && pip check`. `--no-deps` = no resolver, no silent upgrades; `pip check` = build **fails** if the lock is incomplete. Everything else unchanged. |
| `apps/api/tests/test_auth_session_reliability.py` | Removed the dead `import jwt` (line 15) — no test logic touched; fixes collection in clean/production environments. |
| `DEPLOYMENT_RUNBOOK.md`, `PRODUCTION_RUNBOOK.md`, `PRODUCTION_DEPLOYMENT_CHECKLIST.md`, `UPDATE_ROLLBACK_PROCEDURE.md` | Replaced stale "no lockfile — use `npm install`" claims with the locked workflow (`npm ci --ignore-scripts` from repo root; build in `apps/web`), including rollback paths. |

**Explicitly not changed:** `package-lock.json` (already correct and committed),
package versions (no upgrades), package managers, JazzCash/payments/auth/RBAC/
migrations/Caddy/secrets/VPS/DNS/TLS/Expo/EAS, `.gitignore`, `.npmrc` (none exists).

## 5. Lockfile / pinning strategy

- **Python:** `requirements.lock.txt` pins the **exact transitive closure** of
  the declared runtime dependencies — to the versions the 622-test suite
  actually passed on (the venv), not to whatever a rebuild might resolve today.
  Target marker environment: `sys_platform=linux`, `python_version=3.11`
  (matches `python:3.11-slim-bookworm`). Linux-only packages (uvloop) are
  sourced from the production image's own freeze because they cannot install on
  the Windows dev host. Dev/test dependencies (pytest, httpx, aiosqlite, ...)
  are intentionally **not** production-locked.
- **JS:** the existing committed root `package-lock.json` (lockfileVersion 3)
  is the single source of truth for all workspaces — it already pins every
  transitive dependency by version + integrity hash. No new lockfile was
  created or migrated.
- **Consumption (API):** the Dockerfile installs strictly from the lock with
  `--no-deps` and validates with `pip check` before and after installing the
  app package itself.
- **Consumption (web/mobile):** `npm ci --ignore-scripts` from the repo root.

## 6. Clean-install evidence

- **JS:** fresh `npm ci --ignore-scripts` from repo root → **1480 packages**,
  no errors. `npm run build:shared` ✓ · `npm run type-check:web` ✓ ·
  `npm run type-check:mobile` ✓ · web production build → "Compiled
  successfully", all **24 routes** in `apps/web/out` ✓.
- **Why `--ignore-scripts`:** documented in §3.3 — plain `npm ci` aborts on
  `react-native-screens`' dev-tooling install script. `--ignore-scripts` is the
  standard, safer default; nothing in the web build chain needs install scripts
  (verified: the 3 `hasInstallScript` packages are mobile-pipeline tooling).
- **Python:** clean install validated inside the production image itself (§7)
  — the strongest possible clean-environment check for the API.

## 7. Docker evidence

- **Strict lock-driven build:** `docker compose -f docker-compose.prod.yml build api`
  → success. Install path: lock (`--no-deps`) → `pip check` → app (`--no-deps`)
  → `pip check`. Final in-image check: **"No broken requirements found."**
- **Image vs lock diff (`pip freeze --all`):** the image contains the lock
  **plus exactly** `pip==24.0`, `setuptools==79.0.1`, `wheel==0.46.3`,
  `packaging==26.3` — all base `python:3.11-slim-bookworm` image tooling, none
  required by any runtime dependency (metadata audit: only `wheel → packaging >= 24.0`;
  setuptools required by greenlet/wheel test extras). Two cosmetic name
  normalizations (`pydantic_core`/`typing_extensions` underscore vs hyphen) —
  same packages, same versions. **No unexplained packages.**
- **Double-build determinism:** a second `docker build --no-cache` from the
  same repository state produced an **identical freeze** (`IDENTICAL-FREEZE`)
  and a clean `pip check`. Dependency resolution is now build-reproducible.
- **Runtime smoke (all green):** fail-closed guards ×3 (dev password /
  empty secret / weak password each rejected) · `IMPORT-OK env= production` ·
  `NO-ENV-FILE` baked into image · 11 migration files · head `0009`.
- **In-container test suite:** the full backend suite run **inside the
  production image** (py3.11/Linux, locked runtime deps + pinned test deps):
  **622 passed** — identical to the host count. The drift found in §3.1 is
  eliminated: production now runs exactly the tested resolution.

## 8. Regression results

| Check | Result |
|---|---|
| Backend pytest (host venv, py3.13) | **622 passed** (224s) — zero skipped/xfailed/weakened |
| Backend pytest (production image, py3.11/Linux) | **622 passed** (137s) |
| Web type-check | ✓ clean |
| Web production build | ✓ Compiled successfully, 24/24 routes |
| Mobile type-check | ✓ clean |
| `docker compose -f docker-compose.prod.yml config -q` | ✓ valid |
| `docker compose config -q` (dev) | ✓ valid |
| `alembic current` (temp isolated PG 16) | `0009 (head)` |
| `alembic check` (temp isolated PG 16) | "No new upgrade operations detected." |
| Image smoke (guards/import/migrations) | ✓ all green (§7) |

## 9. Remaining limitations (documented, not hidden)

1. **No byte-for-byte image reproducibility is claimed.** Reproducibility here
   means *identical dependency resolution* (proven by the double-build freeze
   comparison), not identical image digests — base-image layers, timestamps,
   and apt packages still vary.
2. **Base-image tooling is unpinned:** `pip`, `setuptools`, `wheel`,
   `packaging` come from `python:3.11-slim-bookworm` (tag, not digest). They
   are not app dependencies (§7), but pinning the base image by digest would
   be a future hardening step.
3. **Dev/test dependencies are intentionally unpinned** (pytest, httpx,
   aiosqlite, ruff, etc. in `[project.optional-dependencies]`). They affect
   development and CI only, never the production image; production tests
   install pinned versions ad hoc (as done for the in-container run).
4. **npm install scripts are skipped globally** (`--ignore-scripts`). All 3
   affected packages are mobile-pipeline tooling; if a future dependency
   genuinely needs a build-time script, it must be allowlisted explicitly.
5. **Mobile production builds (EAS)** resolve from the same root lockfile but
   are executed by Expo's build service — outside this repo's direct control.
   EAS/bundle-ID configuration was untouched per Phase 32 scope.
6. **Windows vs Linux marker environments:** the Python lock targets the Linux
   production marker set; host (win32) dev installs continue to use
   `pip install -e ".[dev]"` and may include host-only packages (e.g. tzdata).

## 10. Exact final dependency workflow

**API (production):**
```bash
# No host step — the Docker build consumes the lock directly:
docker compose -f docker-compose.prod.yml build api
# Dockerfile: pip install --no-cache-dir --no-deps -r requirements.lock.txt
#             && pip check
#             && pip install --no-cache-dir --no-deps . && pip check
```

**Regenerate the Python lock (only when dependencies intentionally change):**
```bash
cd apps/api
../../.venv/Scripts/python.exe scripts/generate_requirements_lock.py \
    --image-freeze <freeze-from-production-image.txt>
# Re-run the full test suite, then rebuild + smoke the image.
```

**Web (production, on the server — from the repo root):**
```bash
npm ci --ignore-scripts                      # root lockfile covers all workspaces
( cd apps/web && NEXT_PUBLIC_API_URL=https://api.<domain>/api/v1 npm run build )
ls apps/web/out/index.html                   # static export emitted
```

**Mobile / type-checks (development):**
```bash
npm ci --ignore-scripts
npm run build:shared                         # packages/shared-types dist is gitignored
npm run type-check:web
npm run type-check:mobile
```

**Rollback:** `git checkout <last-good> && npm ci --ignore-scripts && (cd apps/web && npm run build) && docker compose -f docker-compose.prod.yml restart caddy`
(API image: rebuild from the last-good commit's locked state.)

---

**Outcome:** production dependency resolution is now deterministic and equals
the tested resolution. The Python image cannot silently drift again — any
incomplete lock fails the Docker build at `pip check`. JS builds were already
lockfile-reproducible; the workflow gap (`npm ci` install-script failure) is
resolved and documented. All limitations in §9 are explicit.
