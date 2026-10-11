# Phase 7 — D3 Web Build Failure: Diagnosis

Date: 2026-10-10 · Reproduced with `npm run build` in `apps/web` (Next.js 14.2.35, `output: "export"`)

## Reproduction result

- `✓ Compiled successfully` — webpack compile, ESLint and type-check all pass.
- `✓ Generating static pages (26/26)` — all pages generated.
- **FAIL** during export of the built-in error pages:

```
TypeError: Cannot read properties of null (reading 'useContext')
    at exports.useContext (...\UniServe\node_modules\react\cjs\react.production.js:489:33)
    at StyleRegistry (...styled-jsx...)
    at Zc (...\UniServe\apps\web\node_modules\react-dom\cjs\react-dom-server.browser.production.min.js:74:209)

Error occurred prerendering page "/500"
Error occurred prerendering page "/404"

> Export encountered errors on following paths:
        /_error: /404
        /_error: /500
npm error code 1
```

Secondary (non-fatal) noise in the same log: `Found lockfile missing swc dependencies, patching...`
→ `npm error code ENOWORKSPACES` (Next's lockfile self-patch cannot run inside an npm workspace),
and `Failed to patch lockfile ... fetchPkgInfo`. These are warnings; the build fails on the
prerender/export error above.

## Root cause — dual React copies (confirmed by resolution tree)

| Module | Location | Resolves `react` to |
|---|---|---|
| `react` (mobile pin, hoisted) | `node_modules/react` | **19.2.3** |
| `react-dom` (hoisted) | `node_modules/react-dom` | 19.2.3 |
| `react` (web pin, nested) | `apps/web/node_modules/react` | **18.3.1** |
| `react-dom` (web pin, nested) | `apps/web/node_modules/react-dom` | 18.3.1 |
| `styled-jsx@5.1.1` (Next 14 dep) | `node_modules/styled-jsx` (**root only**) | **19.2.3** ← wrong |
| `next@14.2.35` | `apps/web/node_modules/next` | 18.3.1 |

Manifest facts:
- Root `package.json` declares **no** `react`/`react-dom` (workspaces: `apps/web`, `apps/mobile`, `packages/shared-types`).
- `apps/web` pins `react`/`react-dom` `^18.2.0` (installed 18.3.1, nested).
- `apps/mobile` pins `react`/`react-dom` `19.2.3` (installed 19.2.3, hoisted to root).
- `apps/web/node_modules/styled-jsx` is **ABSENT** — npm hoisted `styled-jsx` to the root.

Mechanism: `styled-jsx`'s `StyleRegistry` calls `useContext` on the **root React 19.2.3**, while
`react-dom-server` 18.3.1 (nested under `apps/web`) has installed its hook dispatcher on the
**nested React 18.3.1**. The React-19 dispatcher is `null` → `Cannot read properties of null
(reading 'useContext')`. This only manifests where Next's server-side renderer runs
styled-jsx — i.e. prerendering `/404` and `/500` — which is why compile/lint/types pass and
only `output: export` fails.

Origin of the split: the pre-existing Expo SDK 51→57 upgrade pinned React 19.2.3 in
`apps/mobile`, which npm hoisted to the root, while `apps/web` still requires React 18 for
Next 14. npm nested React 18 under `apps/web` but left `styled-jsx` at the root, stranding it
on React 19.

## Proposed minimal fix (NOT YET APPLIED — awaiting review)

Add the exact version Next 14.2.35 already uses as a **direct dependency of `apps/web`**:

```jsonc
// apps/web/package.json  →  "dependencies"
"styled-jsx": "5.1.1"
```

then `npm install` (updates `package-lock.json`).

Expected effect: npm places `styled-jsx` at `apps/web/node_modules/styled-jsx`, so it resolves
`apps/web/node_modules/react@18.3.1` — the same React instance as `react-dom` 18.3.1. Prerender
of `/404` and `/500` succeeds and `next build` exits 0.

Why this option:
- One line in one workspace manifest; no version bumps, no React downgrade (mobile/Expo 57
  requires React 19.2.3), no `overrides` that would affect the whole monorepo.
- `styled-jsx@5.1.1` is already the version installed and already required by `next@14.2.35`,
  so no new package version enters the tree.

Alternatives considered and rejected:
- Root `overrides` forcing `styled-jsx → react@18.3.1`: affects every workspace, still leaves
  two Reacts, more invasive.
- Downgrading mobile to React 18: breaks Expo SDK 57 / RN 0.86.3.
- Deleting root `node_modules/styled-jsx`: not durable (reappears on next install).

Constraint status: `package.json` and `package-lock.json` are **unchanged** by this diagnosis.
No manifest, lockfile, Compose, or container change has been made.

## Verification result (hypothesis CONFIRMED)

- Copied `node_modules/styled-jsx` → `apps/web/node_modules/styled-jsx` (additive; root copy left in place).
- Re-ran `npm run build --workspace apps/web` → **`BUILD_EXIT=0`**; `✓ Compiled successfully`,
  `✓ Generating static pages (26/26)`, no `useContext`/`prerender`/`Export encountered errors`.
  (The `ENOWORKSPACES` lockfile-patch warnings remain but are non-fatal.)
- Removed the copy → `apps/web/node_modules/styled-jsx` absent again, root copy present — original
  layout restored exactly.

## Change-safety audit after verification

- `apps/web/package.json`, `apps/mobile/package.json`, `package-lock.json` show as modified in
  `git status`, but their mtimes are `2026-10-04`/`2026-10-07` — i.e. **pre-existing** modifications
  (part of the 83-file baseline from the Expo SDK upgrade + vitest/testing-library additions), NOT
  produced by this build (today 2026-10-10). Verified via `git diff` (content = test-script/dependency
  additions unrelated to styled-jsx) and file timestamps.
- Production API `http://127.0.0.1:8000/api/v1/health` → **200** after all work; container untouched.

**Status: D3 diagnosed, minimal fix identified and empirically validated reversibly. Awaiting approval
to add `"styled-jsx": "5.1.1"` to `apps/web/package.json` + `npm install` (the only durable change).**