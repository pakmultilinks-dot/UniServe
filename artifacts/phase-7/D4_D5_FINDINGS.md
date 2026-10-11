# Phase 7 — D4 (CORS) & D5 (verify-email warning): Findings & Remediation

## D4 — CORS missing the Expo-web origin (MEDIUM)

**Authoritative source.** `Settings(BaseSettings)` (`apps/api/app/core/config.py`) loads `.env` and,
per pydantic-settings, **real env vars / the loaded env-file override the code default**. In the live
stack, `docker-compose.prod.yml` gives the api `env_file: .env.production`, so the running API uses
the value at `.env.production:34`, **not** the code default at `config.py:135`.

| Source | Value |
|---|---|
| Code default (`config.py:135`) | `["http://localhost:3000","http://localhost:8081"]` — **not authoritative in prod** |
| Live env (`.env.production:34`) | `["http://app.localhost","http://localhost","http://localhost:3000","http://localhost:8081","https://app.example.com"]` — **authoritative** |

**Gap.** The live allowlist does **not** contain `http://localhost:8082`, the port Expo's web dev
server used during Phase 6 testing. Requests from an Expo-web session on `:8082` are therefore
rejected by CORS.

**Is this a production defect?** No — it is a **local-dev/testing** gap only:
- The mobile app is a native client (no CORS preflight).
- The production web client is served by Caddy under `app.localhost` / `https://app.example.com`,
  both already in the allowlist.
- Only an Expo **web** dev server on a non-standard port (8082) is affected.

**Recommended remediation (no change applied).**
1. **Preferred, zero risk:** run the Expo web test server on **port 8081** (already allowed). This is
   what the project already standardizes on; no config edit, nothing to review.
2. Only if `:8082` must be supported: add the **specific** origin `http://localhost:8082` (non-wildcard)
   to `CORS_ORIGINS` in `.env.production` and restart the api. This is a **production-config change**
   and is therefore **not applied** here, per the constraint against changing production config
   before review. **No wildcard origin is added.**

## D5 — stray empty `<Text>` node on verify-email (LOW) — FIXED

**Defect.** `apps/mobile/app/(auth)/verify-email.tsx` rendered
`<Text style={...}>{email}</Text>` where `email = params.email ?? ""`. When the screen is opened
without an `email` query param, this renders an empty text node directly inside a `<View>`, which
triggers React Native's dev warning that text must be rendered within a `<Text>` component.

**Minimal fix (applied).** Guard the node so it only renders when non-empty:

```tsx
{email ? (
  <Text style={[styles.email, { color: brand }]}>{email}</Text>
) : null}
```

**Why applying was justified** (vs. leaving it as a proposal): it is a genuine rendering defect, the
guard is the idiomatic RN pattern, it has **zero functional risk** (it only suppresses rendering of an
empty element — no behavior change when `email` is present), and it edits **app source only**, which is
outside the protected set (production dependencies / lockfiles / Compose / running containers). It is
not a change made "to make a test pass."

**Verification.** `npm run type-check --workspace apps/mobile` (`tsc --noEmit`) → **exit 0**, zero TS
errors, none referencing `verify-email`.

## Change-safety audit

- D4: **no** config change made (`.env.production` untouched; proposal only).
- D5: one-line guard in `apps/mobile/app/(auth)/verify-email.tsx` only; mobile type-check clean.
- No production container, Compose file, lockfile, or dependency changed.