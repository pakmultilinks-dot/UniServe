# UniServe — Phase 9 D3 Production Build Remediation Report

**Scope:** Resolve the web production-build failure (`useContext` null on the static-exported
`/404` and `/500` pages) caused by dual React instances / a mis-hoisted `styled-jsx`. The goal was
the **smallest justified, reproducible, maintainable fix** that preserves existing application
behaviour, with no React / React-DOM / Next.js / Expo upgrade, no broad root React override, no
manual copy into `node_modules`, no edit of generated files under `.next`, no lockfile wipe or
full reinstall, and no suppression of the failing pages.

**Outcome:** ✅ Fixed. `next build` exits **0**; all 26 routes export clean; the static `/404`
renders without the `useContext` crash. Dev server restored on **:3010**.

---

## 1. Baseline

| Item | Value |
|---|---|
| Git HEAD | `bc967b3` (`main`) — *unchanged throughout* |
| Monorepo | npm workspaces: `apps/web` (Next 14.2.35, React 18.3.1), `apps/mobile` (Expo SDK 57, React 19.2.3, RN 0.86.3), `packages/shared-types`, `apps/api` (FastAPI) |
| Web dev port | 3010 |
| Lockfile SHA256 (baseline) | `3AE3D031F90A7608E854E4B34A147ECEE12C63634F96F9D7BB70EF9C4694C5D8` |
| Backups | `$env:TEMP\d3_backup\` — `package.json.bak`, `package-lock.json.bak`, `web-package.json.bak`, `package-lock.HEAD.json` |
| Baseline build log | `$env:TEMP\d3_baseline_build.log` |

## 2. Reproducing the failure

A genuine production build of `apps/web` (`next build`) reproduced the reported failure: the build
broke on the Next.js built-in error routes served under static export. Only the **built-in**
`/404` and `/500` pages were affected; the application's 24 real pages are Tailwind-based and
rendered fine — the crash was isolated to the pages that pull in `styled-jsx`.

## 3. Root cause (proven with dependency evidence)

`styled-jsx@5.1.1` — an exact-pinned dependency of `next@14.2.35` — was **npm-hoisted to the
workspace root** `node_modules`, where it binds the **root React 19.2.3** (the version pinned by
`apps/mobile`). Meanwhile `react-dom` resolved under `apps/web/node_modules` binds the **nested
React 18.3.1**. This produced **two physically different React instances**. The built-in error
pages (unlike the app's Tailwind pages) render through `styled-jsx`, whose `useContext` then read
from a React instance that did not match `react-dom`'s — returning `null` and crashing the page.

`styled-jsx@5.1.1` declares `peer.react = ">= 16.8.0 || 17.x.x || ^18.0.0-0"`. The **root React
19.2.3 violates that `^18` peer range**, which is precisely the mis-hoisting condition. Because
the conflict comes from root placement, adding the pin at the workspace root can never fix it —
`styled-jsx` must physically nest under `apps/web` so it binds `apps/web`'s React 18.3.1.

**Why the "obvious" fix is a no-op (proven):** Adding `"styled-jsx": "5.1.1"` to `apps/web`
dependencies changes nothing — npm **dedupes it back to the root copy** (same version), so the
physical layout is untouched. The Phase 7 attempt that "verified" a fix by manually copying the
package into `node_modules` was a **diagnostic only, not a real fix** (and is excluded as a
permanent remedy by the constraints).

## 4. The fix (minimal)

One line in `apps/web/package.json` — pin `styled-jsx` to **5.1.2**, a version the root does not
carry (root has 5.1.1). Because `5.1.2` is **unsatisfiable at the root**, npm is forced to
**nest `styled-jsx@5.1.2` under `apps/web`**, where it binds `apps/web`'s React 18.3.1. One-line
manifest change + the minimal corresponding lockfile record. No React/Next/Expo upgrade, no
`overrides`, no manual copy, no `.next` edit, no lockfile delete.

### Before / after dependency layout

| | Before (broken) | After (fixed) |
|---|---|---|
| Root `node_modules/styled-jsx` | `5.1.1` (binds React **19.2.3**) | **ABSENT** |
| `apps/web/node_modules/styled-jsx` | absent (resolved to root) | **5.1.2** (binds React **18.3.1**) |
| Root React | 19.2.3 | 19.2.3 (unchanged) |
| `apps/web` React | 18.3.1 | 18.3.1 (unchanged) |
| Same-instance probe | `false` | **`true`** |

### Files changed by this remediation

- `apps/web/package.json` — **only** the line `"styled-jsx": "5.1.2"` was added to `dependencies`
  by this task. (The file also carries pre-existing, unrelated Phase 42 edits to `scripts` and
  `devDependencies` that were already present in the baseline working tree — **not** introduced
  here.)
- `package-lock.json` — the minimal record for the nested `apps/web/node_modules/styled-jsx@5.1.2`
  (`resolved: …/styled-jsx-5.1.2.tgz`). All other lockfile churn in the working tree is
  pre-existing baseline content.

## 5. Validation (every command + result)

| Check | Command | Result |
|---|---|---|
| Dependency probe | same-instance resolution probe (`Module.createRequire`) | **SAME INSTANCE = true** |
| Web typecheck | `apps/web` pinned `tsc --noEmit` (TS **5.3.3**) | **exit 0** |
| Shared typecheck | `packages/shared-types` pinned `tsc --noEmit` (TS 5.3.3) | **exit 0** |
| Mobile typecheck | `tsc --noEmit` | **exit 0** |
| Web tests | `vitest run` | **43 / 43 passed** |
| Shared-types tests | `vitest run` | **13 / 13 passed** |
| Mobile tests | `jest --ci` | **51 / 51 passed** |
| Backend tests | `pytest tests -q` (in-memory SQLite) | **875 passed, 5 skipped** |
| Web lint | `next lint` | **exit 0** (warnings only, 0 errors — matches baseline) |
| **Production build** | `next build` | **BUILD_EXIT = 0**, 26 routes export clean |
| Dev server | `next dev -p 3010` | `/` **200**, `/login` **200**, `/404` **404** renders cleanly, no `useContext`/crash markers |

> **Note on the typecheck artifact:** invoking the *root-hoisted* `tsc` (a **TypeScript 6.0.3**
> picked up from the root) reports spurious lib/DOM errors that do **not** occur with each
> package's own pinned **TypeScript 5.3.3**. All typechecks above were run with each package's
> pinned `tsc`; all exit 0.

The genuine production build passes and the static error pages no longer crash. No failing page was
suppressed and static export was not disabled to obtain the green exit code.

## 6. Dev server restored (:3010)

`next dev` is running on **http://localhost:3010**. After clearing a stale `.next` (see §7), the
server came up and serves `/` and `/login` with HTTP 200; `/404` renders its content cleanly
(HTTP 404, ~7 KB, no crash keywords). The earlier stale-chunk (`997.js`) dev error was a leftover
`.next` artifact from the build/dev collision and was resolved by clearing `.next` before restart.

## 7. Remaining warnings / blockers (not defects in this fix)

- **Dev lockfile "patch" warning:** on startup Next prints `Failed to patch lockfile … ENOWORKSPACES`.
  This is a **benign, pre-existing** npm-workspaces interaction (Next's lockfile self-heal cannot
  run under workspaces); it does not affect the build or runtime.
- **`output: export` + rewrites/middleware warnings:** pre-existing configuration notes in dev,
  unrelated to this remediation; the production export completes cleanly (exit 0).

## 8. Final state

- **Git:** HEAD still `bc967b3` (`main`). **No commit, push, deploy, or amend** was performed.
- **Working tree:** the ~96 pre-existing modified files + Phase 8 evidence + `EXP0_API_DESTINATION_EVIDENCE.md`
  are preserved. The temporary `.d3probe.cjs` probe used for the same-instance check was **deleted**.
- **Protected assets untouched:** no dependency upgrade, no root React override, no manual
  `node_modules` copy, no `.next` edit, no lockfile wipe, no production-DB write. The production
  database `uniserve_prod` was not written (Docker was down; backend tests ran on in-memory SQLite).
- **Authoritative artifacts:** baseline build log `$env:TEMP\d3_baseline_build.log`; backups under
  `$env:TEMP\d3_backup\`.
